from __future__ import annotations

from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any

from dealwatch.infra.config import PROJECT_ROOT
from dealwatch.stores import (
    STORE_CAPABILITY_REGISTRY,
    STORE_REGISTRY,
    build_next_onboarding_step,
    build_runtime_binding_summary,
    build_store_support_summary,
    derive_missing_capabilities,
    derive_runtime_binding_blockers,
)

_RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "store-onboarding-contract.md"
_ADAPTER_CONTRACT_TEST_PATH = PROJECT_ROOT / "tests" / "test_adapter_contracts.py"
_SECTION_HEADING_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_MARKDOWN_LINK_RE = re.compile(r"\((?P<path>[^)]+)\)")
_LIMITED_SUPPORT_TRUTH_SOURCES = [
    "docs/runbooks/store-onboarding-contract.md",
    "src/dealwatch/application/urls.py",
    "src/dealwatch/application/services.py",
    "src/dealwatch/api/schemas.py",
    "frontend/src/pages/ComparePage.tsx",
    "frontend/src/pages/compare/copy.ts",
    "frontend/src/pages/compare/helpers.ts",
    "tests/test_product_api.py",
    "tests/test_product_providers.py",
]


def build_store_onboarding_cockpit(
    *,
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    binding_by_key = {item["store_key"]: item for item in bindings}
    registry_keys = set(STORE_REGISTRY)
    capability_keys = set(STORE_CAPABILITY_REGISTRY)
    all_store_keys = sorted(registry_keys | capability_keys | set(binding_by_key))
    contract_test_content = _ADAPTER_CONTRACT_TEST_PATH.read_text(encoding="utf-8")
    runbook_truth = _load_runbook_truth(all_store_keys)

    capability_matrix: list[dict[str, Any]] = []
    enabled_count = 0
    disabled_count = 0
    official_full_count = 0
    official_partial_count = 0
    official_in_progress_count = 0
    default_enabled_count = 0
    compare_intake_supported_count = 0
    cashback_supported_count = 0
    watch_task_supported_count = 0
    watch_group_supported_count = 0
    recovery_supported_count = 0
    region_sensitive_count = 0
    store_id_mismatches: list[str] = []

    for store_key in all_store_keys:
        binding = binding_by_key.get(store_key)
        adapter_cls = STORE_REGISTRY.get(store_key)
        capability = STORE_CAPABILITY_REGISTRY.get(store_key)
        adapter_module = adapter_cls.__module__ if adapter_cls is not None else None
        adapter_file_path = _module_to_repo_path(adapter_module)
        adapter_file_exists = adapter_file_path.is_file() if adapter_file_path is not None else False
        capability_store_id_matches = capability.store_id == store_key if capability is not None else False
        contract_test_paths = list(capability.contract_test_paths) if capability is not None else ["tests/test_adapter_contracts.py"]
        source_of_truth_files = _build_store_truth_sources(
            store_key=store_key,
            adapter_file_path=adapter_file_path,
            contract_test_paths=contract_test_paths,
        )
        if capability is not None and not capability_store_id_matches:
            store_id_mismatches.append(store_key)

        enabled = bool(binding["enabled"]) if binding is not None else False
        runtime_binding_blockers = list(derive_runtime_binding_blockers(capability))
        if enabled:
            enabled_count += 1
        else:
            disabled_count += 1
        if capability is not None and capability.support_tier == "official_full":
            official_full_count += 1
        if capability is not None and capability.support_tier == "official_partial":
            official_partial_count += 1
        if capability is not None and capability.support_tier == "official_in_progress":
            official_in_progress_count += 1
        if capability is not None and capability.default_enabled:
            default_enabled_count += 1
        if capability is not None and capability.supports_compare_intake:
            compare_intake_supported_count += 1
        if capability is not None and capability.cashback_supported:
            cashback_supported_count += 1
        if capability is not None and capability.supports_watch_task:
            watch_task_supported_count += 1
        if capability is not None and capability.supports_watch_group:
            watch_group_supported_count += 1
        if capability is not None and capability.supports_recovery:
            recovery_supported_count += 1
        if capability is not None and capability.region_sensitive:
            region_sensitive_count += 1

        contract_gaps: list[str] = []
        if store_key not in registry_keys:
            contract_gaps.append("missing_store_registry_entry")
        if capability is None:
            contract_gaps.append("manifest_entry")
        if binding is None:
            contract_gaps.append("missing_store_binding")
        if not adapter_file_exists:
            contract_gaps.append("missing_live_adapter_file")
        if store_key not in contract_test_content:
            contract_gaps.append("missing_adapter_contract_reference")
        if capability is not None and not capability_store_id_matches:
            contract_gaps.append("manifest_store_id_mismatch")
        if enabled and runtime_binding_blockers:
            contract_gaps.append("runtime_binding_contract_drift")
        missing_capabilities = list(derive_missing_capabilities(capability))

        capability_matrix.append(
            {
                "store_key": store_key,
                "enabled": enabled,
                "binding_present": binding is not None,
                "registered": store_key in registry_keys,
                "capability_declared": capability is not None,
                "support_channel": "official" if capability is not None else None,
                "adapter_class": binding["adapter_class"] if binding is not None else None,
                "adapter_module": adapter_module,
                "adapter_file_path": _project_relative_path(adapter_file_path) if adapter_file_path is not None else None,
                "adapter_file_exists": adapter_file_exists,
                "support_tier": capability.support_tier if capability is not None else None,
                "default_enabled": capability.default_enabled if capability is not None else None,
                "support_reason_codes": list(capability.support_reason_codes) if capability is not None else [],
                "support_summary": build_store_support_summary(capability, enabled=enabled),
                "next_step_codes": list(capability.next_step_codes) if capability is not None else [],
                "next_onboarding_step": build_next_onboarding_step(capability, enabled=enabled),
                "runtime_binding_summary": build_runtime_binding_summary(capability, enabled=enabled),
                "discovery_mode": capability.discovery_mode if capability is not None else None,
                "parse_mode": capability.parse_mode if capability is not None else None,
                "region_sensitive": capability.region_sensitive if capability is not None else None,
                "cashback_supported": capability.cashback_supported if capability is not None else None,
                "supports_compare_intake": capability.supports_compare_intake if capability is not None else None,
                "supports_watch_task": capability.supports_watch_task if capability is not None else None,
                "supports_watch_group": capability.supports_watch_group if capability is not None else None,
                "supports_recovery": capability.supports_recovery if capability is not None else None,
                "contract_test_reference_present": store_key in contract_test_content,
                "manifest_store_id_matches": capability_store_id_matches,
                "contract_status": "ready" if not contract_gaps else "attention_needed",
                "missing_capabilities": missing_capabilities,
                "contract_gaps": contract_gaps,
                "contract_test_paths": contract_test_paths,
                "source_of_truth_files": source_of_truth_files,
                "required_files": [
                    {
                        "kind": "store_adapter",
                        "path": _project_relative_path(adapter_file_path) if adapter_file_path is not None else None,
                        "exists": adapter_file_exists,
                    },
                    {
                        "kind": "capability_manifest",
                        "path": "src/dealwatch/stores/manifest.py",
                        "exists": capability is not None,
                    },
                    {
                        "kind": "store_registry",
                        "path": "src/dealwatch/stores/__init__.py",
                        "exists": store_key in registry_keys,
                    },
                    {
                        "kind": "adapter_contract_test",
                        "path": "tests/test_adapter_contracts.py",
                        "exists": store_key in contract_test_content,
                    },
                ],
            }
        )

    capability_matrix.sort(key=lambda item: item["store_key"])
    registry_matches_capability_registry = registry_keys == capability_keys and not store_id_mismatches
    onboarding_checklist = [
        {
            "key": f"check_{index + 1}",
            "label": item,
            "detail": item,
        }
        for index, item in enumerate(runbook_truth["checklist"])
    ]
    verification_commands = list(runbook_truth["verification_commands"])
    truth_sources = [
        "src/dealwatch/stores/manifest.py",
        "src/dealwatch/stores/__init__.py",
        "src/dealwatch/persistence/store_bindings.py",
        "src/dealwatch/application/urls.py",
        "src/dealwatch/application/services.py",
        "src/dealwatch/api/schemas.py",
        "frontend/src/pages/ComparePage.tsx",
        "frontend/src/pages/compare/copy.ts",
        "frontend/src/pages/compare/helpers.ts",
        "docs/runbooks/store-onboarding-contract.md",
        "tests/test_adapter_contracts.py",
        "scripts/verify_store_capability_registry.py",
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "supported_store_count": len(all_store_keys),
            "official_full_count": official_full_count,
            "official_partial_count": official_partial_count,
            "official_in_progress_count": official_in_progress_count,
            "default_enabled_store_count": default_enabled_count,
            "enabled_store_count": enabled_count,
            "disabled_store_count": disabled_count,
            "compare_intake_supported_count": compare_intake_supported_count,
            "cashback_supported_count": cashback_supported_count,
            "watch_task_supported_count": watch_task_supported_count,
            "watch_group_supported_count": watch_group_supported_count,
            "recovery_supported_count": recovery_supported_count,
            "region_sensitive_count": region_sensitive_count,
        },
        "consistency": {
            "registry_matches_capability_registry": registry_matches_capability_registry,
            "missing_in_registry": sorted(capability_keys - registry_keys),
            "missing_in_capability_registry": sorted(registry_keys - capability_keys),
            "store_id_mismatches": sorted(store_id_mismatches),
        },
        "registry_health": {
            "registry_store_count": len(registry_keys),
            "capability_store_count": len(capability_keys),
            "binding_store_count": len(binding_by_key),
            "registry_parity_ok": registry_matches_capability_registry,
            "registry_only_store_keys": sorted(registry_keys - capability_keys),
            "manifest_only_store_keys": sorted(capability_keys - registry_keys),
            "binding_only_store_keys": sorted(set(binding_by_key) - (registry_keys | capability_keys)),
        },
        "capability_matrix": capability_matrix,
        "stores": [
            {
                "store_key": item["store_key"],
                "enabled": item["enabled"],
                "binding_present": item["binding_present"],
                "registered": item["registered"],
                "capability_declared": item["capability_declared"],
                "adapter_class": item["adapter_class"],
                "adapter_module": item["adapter_module"],
                "adapter_file_path": item["adapter_file_path"],
                "adapter_file_exists": item["adapter_file_exists"],
                "support_channel": item["support_channel"],
                "support_tier": item["support_tier"],
                "default_enabled": item["default_enabled"],
                "support_reason_codes": item["support_reason_codes"],
                "support_summary": item["support_summary"],
                "next_step_codes": item["next_step_codes"],
                "next_onboarding_step": item["next_onboarding_step"],
                "runtime_binding_summary": item["runtime_binding_summary"],
                "discovery_mode": item["discovery_mode"],
                "parse_mode": item["parse_mode"],
                "region_sensitive": item["region_sensitive"],
                "cashback_supported": item["cashback_supported"],
                "supports_compare_intake": item["supports_compare_intake"],
                "supports_watch_task": item["supports_watch_task"],
                "supports_watch_group": item["supports_watch_group"],
                "supports_recovery": item["supports_recovery"],
                "contract_test_reference_present": item["contract_test_reference_present"],
                "manifest_store_id_matches": item["manifest_store_id_matches"],
                "contract_status": item["contract_status"],
                "missing_capabilities": item["missing_capabilities"],
                "contract_gaps": item["contract_gaps"],
                "contract_test_paths": item["contract_test_paths"],
                "source_of_truth_files": item["source_of_truth_files"],
                "required_files": item["required_files"],
            }
            for item in capability_matrix
        ],
        "onboarding_checklist": onboarding_checklist,
        "verification_commands": verification_commands,
        "truth_sources": truth_sources,
        "limited_support_lane": _build_limited_support_lane(runbook_truth),
        "onboarding_contract": runbook_truth,
    }


def _load_runbook_truth(all_store_keys: list[str]) -> dict[str, Any]:
    content = _RUNBOOK_PATH.read_text(encoding="utf-8")
    sections = _split_markdown_sections(content)
    minimum_contract = _parse_markdown_list(sections.get("Minimum contract", []))
    official_support_tiers = _parse_markdown_list(sections.get("Official support tiers", []))
    runtime_binding_truth = _parse_markdown_list(sections.get("Runtime binding truth", []))
    limited_support_contract = _parse_markdown_list(sections.get("Limited support contract", []))
    rollout_rule = _parse_markdown_list(sections.get("Rollout rule", []))
    verification_commands = _parse_code_blocks(sections.get("Required tests", []))
    related_files = _parse_related_files(sections.get("Related files", []))
    adapter_missing_store_keys = [
        store_key
        for store_key in all_store_keys
        if not (PROJECT_ROOT / "src" / "dealwatch" / "stores" / store_key / "adapter.py").is_file()
    ]
    required_files = [
        {
            "kind": "store_adapter",
            "path_template": "src/dealwatch/stores/<store>/adapter.py",
            "exists_for_all_supported_stores": not adapter_missing_store_keys,
            "missing_store_keys": adapter_missing_store_keys,
        },
        *related_files,
    ]
    return {
        "source_runbook_path": _project_relative_path(_RUNBOOK_PATH),
        "checklist": minimum_contract,
        "required_files": required_files,
        "verification_commands": verification_commands,
        "rollout_rule": rollout_rule,
        "official_support_tiers": official_support_tiers,
        "runtime_binding_truth": runtime_binding_truth,
        "limited_support_contract": limited_support_contract,
    }


def _build_store_truth_sources(
    *,
    store_key: str,
    adapter_file_path: Path | None,
    contract_test_paths: list[str],
) -> list[str]:
    sources = [
        "src/dealwatch/stores/manifest.py",
        "src/dealwatch/stores/__init__.py",
        "src/dealwatch/persistence/store_bindings.py",
        "docs/runbooks/store-onboarding-contract.md",
    ]
    if adapter_file_path is not None:
        sources.append(_project_relative_path(adapter_file_path))
    roadmap_path = PROJECT_ROOT / "docs" / "roadmaps" / f"dealwatch-{store_key}-c1.md"
    if roadmap_path.is_file():
        sources.append(_project_relative_path(roadmap_path))
    elif store_key == "walmart":
        sources.append("docs/roadmaps/dealwatch-next-store-decision-packet.md")
    sources.extend(contract_test_paths)
    return list(dict.fromkeys(sources))


def _build_limited_support_lane(runbook_truth: dict[str, Any]) -> dict[str, Any]:
    return {
        "support_channel": "limited",
        "support_tier": "limited_guidance_only",
        "summary": (
            "Non-onboarded or unsupported-path URLs can still enter compare review and local evidence,"
            " but they cannot claim live watch or notification support."
        ),
        "supported_actions": [
            "accept_url_into_compare_preview",
            "show_compare_guidance",
            "save_compare_evidence",
        ],
        "blocked_actions": [
            "create_watch_task",
            "create_watch_group",
            "cashback_tracking",
            "notification_delivery",
        ],
        "contract_lines": list(runbook_truth["limited_support_contract"]),
        "source_of_truth_files": list(_LIMITED_SUPPORT_TRUTH_SOURCES),
    }


def _split_markdown_sections(content: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_title: str | None = None
    for raw_line in content.splitlines():
        match = _SECTION_HEADING_RE.match(raw_line)
        if match is not None:
            current_title = match.group("title")
            sections[current_title] = []
            continue
        if current_title is not None:
            sections[current_title].append(raw_line)
    return sections


def _parse_markdown_list(lines: list[str]) -> list[str]:
    results: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            results.append(line[2:].strip())
            continue
        match = re.match(r"^\d+\.\s+(?P<item>.+)$", line)
        if match is not None:
            results.append(match.group("item").strip())
    return results


def _parse_code_blocks(lines: list[str]) -> list[str]:
    commands: list[str] = []
    inside_block = False
    for raw_line in lines:
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            inside_block = not inside_block
            continue
        if inside_block and line.strip():
            commands.append(line.strip())
    return commands


def _parse_related_files(lines: list[str]) -> list[dict[str, Any]]:
    related_files: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        match = _MARKDOWN_LINK_RE.search(line)
        if match is None:
            continue
        path = (_RUNBOOK_PATH.parent / match.group("path")).resolve()
        related_files.append(
            {
                "kind": "runbook_related_file",
                "path": _project_relative_path(path),
                "exists": path.is_file(),
            }
        )
    return related_files


def _module_to_repo_path(module_name: str | None) -> Path | None:
    if module_name is None or not module_name.startswith("dealwatch."):
        return None
    return PROJECT_ROOT / "src" / Path(module_name.replace(".", "/")).with_suffix(".py")


def _project_relative_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))
