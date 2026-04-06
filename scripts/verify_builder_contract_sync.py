#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dealwatch.builder_contract import (
    build_builder_client_config_payload,
    build_builder_client_configs_payload,
    build_public_builder_client_catalog_payload,
    build_public_builder_client_configs_payload,
    build_public_builder_client_starters_payload,
    build_public_builder_starter_pack_payload,
    build_builder_starter_pack_payload,
    list_client_starter_specs,
)

EXAMPLES = ROOT / "docs" / "integrations" / "examples"


def _load_json(relative_path: str):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def main() -> int:
    checks = [
        (
            "docs/integrations/examples/mcp-client-starters.response.json",
            list_client_starter_specs(),
        ),
        (
            "docs/integrations/examples/cli-builder-starter-pack.response.json",
            build_builder_starter_pack_payload(),
        ),
        (
            "docs/integrations/examples/http-builder-starter-pack.response.json",
            build_builder_starter_pack_payload(),
        ),
        (
            "docs/integrations/examples/cli-builder-client-config.response.json",
            build_builder_client_config_payload("codex"),
        ),
        (
            "docs/integrations/examples/http-builder-client-config.response.json",
            build_builder_client_config_payload("codex"),
        ),
        (
            "docs/integrations/examples/mcp-builder-client-config.call.json",
            {"tool": "get_builder_client_config", "arguments": {"client": "codex"}},
        ),
        (
            "docs/integrations/examples/cli-builder-client-configs.response.json",
            build_builder_client_configs_payload(),
        ),
        (
            "docs/integrations/examples/http-builder-client-configs.response.json",
            build_builder_client_configs_payload(),
        ),
        (
            "docs/integrations/examples/mcp-builder-client-configs.call.json",
            {"tool": "list_builder_client_configs", "arguments": {}},
        ),
        (
            "site/data/builder-client-catalog.json",
            build_public_builder_client_catalog_payload(),
        ),
        (
            "site/data/builder-client-starters.json",
            build_public_builder_client_starters_payload(),
        ),
        (
            "site/data/builder-starter-pack.json",
            build_public_builder_starter_pack_payload(),
        ),
        (
            "site/data/builder-client-configs.json",
            build_public_builder_client_configs_payload(),
        ),
    ]

    failures: list[str] = []
    for relative_path, expected in checks:
        current = _load_json(relative_path)
        if current != expected:
            failures.append(relative_path)

    if failures:
        print("Builder contract sync verification failed:")
        for failure in failures:
            print(f" - snapshot drift: {failure}")
        return 1

    print("Builder contract sync verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
