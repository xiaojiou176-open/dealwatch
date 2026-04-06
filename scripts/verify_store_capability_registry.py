#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = ROOT / "src/dealwatch/stores/__init__.py"
MANIFEST_FILE = ROOT / "src/dealwatch/stores/manifest.py"
REQUIRED_FIELDS = {
    "store_id",
    "support_tier",
    "default_enabled",
    "support_reason_codes",
    "next_step_codes",
    "contract_test_paths",
    "discovery_mode",
    "parse_mode",
    "region_sensitive",
    "cashback_supported",
    "supports_compare_intake",
    "supports_watch_task",
    "supports_watch_group",
    "supports_recovery",
}
ALLOWED_SUPPORT_TIERS = {
    "official_full",
    "official_partial",
    "official_in_progress",
}
PRODUCT_PATH_FIELDS = (
    "supports_compare_intake",
    "supports_watch_task",
    "supports_watch_group",
    "supports_recovery",
    "cashback_supported",
)
RUNTIME_BINDING_FIELDS = (
    "supports_compare_intake",
    "supports_watch_task",
)


def parse_store_registry_keys() -> set[str]:
    tree = ast.parse(INIT_FILE.read_text(encoding="utf-8"), filename=str(INIT_FILE))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STORE_REGISTRY" and isinstance(node.value, ast.Dict):
                    keys: set[str] = set()
                    for key in node.value.keys:
                        if isinstance(key, ast.Attribute) and key.attr == "store_id":
                            if isinstance(key.value, ast.Name):
                                name = key.value.id
                                keys.add(
                                    {
                                        "TargetAdapter": "target",
                                        "Ranch99Adapter": "ranch99",
                                        "WeeeAdapter": "weee",
                                    }.get(name, name.removesuffix("Adapter").lower())
                                )
                    return keys
    raise RuntimeError("STORE_REGISTRY definition not found")


def parse_manifest_entries() -> dict[str, dict[str, object]]:
    tree = ast.parse(MANIFEST_FILE.read_text(encoding="utf-8"), filename=str(MANIFEST_FILE))
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STORE_CAPABILITY_REGISTRY":
                    value = node.value
                    break
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "STORE_CAPABILITY_REGISTRY":
                value = node.value
        if isinstance(value, ast.Dict):
            entries: dict[str, dict[str, object]] = {}
            for key_node, value_node in zip(value.keys, value.values):
                if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                    continue
                if not isinstance(value_node, ast.Call):
                    continue
                entry_fields: dict[str, object] = {}
                for kw in value_node.keywords:
                    if kw.arg is None:
                        continue
                    entry_fields[kw.arg] = ast.literal_eval(kw.value)
                entries[key_node.value] = entry_fields
            return entries
    raise RuntimeError("STORE_CAPABILITY_REGISTRY definition not found")


def main() -> int:
    try:
        registry_keys = parse_store_registry_keys()
        manifest_entries = parse_manifest_entries()
    except Exception as exc:
        print(f"Store capability registry verification failed: {exc}", file=sys.stderr)
        return 1

    manifest_keys = set(manifest_entries)
    if registry_keys != manifest_keys:
        print("Store capability registry does not match live store registry.", file=sys.stderr)
        print(f"registry={sorted(registry_keys)}", file=sys.stderr)
        print(f"manifest={sorted(manifest_keys)}", file=sys.stderr)
        return 1

    for store_id, entry in manifest_entries.items():
        fields = set(entry)
        missing = sorted(REQUIRED_FIELDS - fields)
        if missing:
            print(f"{store_id}: missing required capability fields: {', '.join(missing)}", file=sys.stderr)
            return 1
        support_tier = entry.get("support_tier")
        if support_tier not in ALLOWED_SUPPORT_TIERS:
            print(
                f"{store_id}: invalid support_tier {support_tier!r}; expected one of {sorted(ALLOWED_SUPPORT_TIERS)}",
                file=sys.stderr,
            )
            return 1
        if entry.get("store_id") != store_id:
            print(f"{store_id}: store_id must match the manifest key", file=sys.stderr)
            return 1
        if not isinstance(entry.get("default_enabled"), bool):
            print(f"{store_id}: default_enabled must be an explicit boolean", file=sys.stderr)
            return 1

        contract_test_paths = entry.get("contract_test_paths")
        if not isinstance(contract_test_paths, tuple) or not contract_test_paths:
            print(f"{store_id}: contract_test_paths must be a non-empty tuple", file=sys.stderr)
            return 1
        if "tests/test_adapter_contracts.py" not in contract_test_paths:
            print(f"{store_id}: contract_test_paths must include tests/test_adapter_contracts.py", file=sys.stderr)
            return 1
        missing_test_paths = [path for path in contract_test_paths if not (ROOT / path).is_file()]
        if missing_test_paths:
            print(
                f"{store_id}: contract_test_paths contain missing files: {', '.join(missing_test_paths)}",
                file=sys.stderr,
            )
            return 1

        runtime_binding_eligible = all(bool(entry[field]) for field in RUNTIME_BINDING_FIELDS) and support_tier != "official_in_progress"
        if entry["default_enabled"] and not runtime_binding_eligible:
            print(
                f"{store_id}: default_enabled stores must also be runtime-binding eligible",
                file=sys.stderr,
            )
            return 1
        missing_product_capabilities = [field for field in PRODUCT_PATH_FIELDS if not bool(entry[field])]
        support_reason_codes = entry.get("support_reason_codes")
        next_step_codes = entry.get("next_step_codes")

        if support_tier == "official_full":
            if missing_product_capabilities:
                print(
                    f"{store_id}: official_full cannot miss product-path capabilities: {', '.join(missing_product_capabilities)}",
                    file=sys.stderr,
                )
                return 1
            if support_reason_codes:
                print(f"{store_id}: official_full must keep support_reason_codes empty", file=sys.stderr)
                return 1
            if next_step_codes:
                print(f"{store_id}: official_full must keep next_step_codes empty", file=sys.stderr)
                return 1
            if not runtime_binding_eligible:
                print(f"{store_id}: official_full must remain runtime-binding eligible", file=sys.stderr)
                return 1
            continue

        if support_tier == "official_partial":
            if not runtime_binding_eligible:
                print(
                    f"{store_id}: official_partial must support compare intake and single-watch runtime binding",
                    file=sys.stderr,
                )
                return 1
            if not any(not bool(entry[field]) for field in ("supports_watch_group", "supports_recovery", "cashback_supported")):
                print(
                    f"{store_id}: official_partial must still miss at least one larger product-path capability",
                    file=sys.stderr,
                )
                return 1
            if not support_reason_codes:
                print(f"{store_id}: official_partial requires support_reason_codes", file=sys.stderr)
                return 1
            if not next_step_codes:
                print(f"{store_id}: official_partial requires next_step_codes", file=sys.stderr)
                return 1
            continue

        if runtime_binding_eligible:
            print(f"{store_id}: official_in_progress must not be runtime-binding eligible", file=sys.stderr)
            return 1
        if not support_reason_codes:
            print(f"{store_id}: official_in_progress requires support_reason_codes", file=sys.stderr)
            return 1
        if not next_step_codes:
            print(f"{store_id}: official_in_progress requires next_step_codes", file=sys.stderr)
            return 1
        if not missing_product_capabilities:
            print(
                f"{store_id}: official_in_progress cannot claim the full current product path yet",
                file=sys.stderr,
            )
            return 1

    print("Store capability registry verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
