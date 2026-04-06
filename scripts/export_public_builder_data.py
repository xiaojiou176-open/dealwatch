#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dealwatch.builder_contract import (  # noqa: E402
    build_public_builder_client_catalog_payload,
    build_public_builder_client_configs_payload,
    build_public_builder_client_starters_payload,
    build_public_builder_starter_pack_payload,
)


def _write_json(relative_path: str, payload: dict) -> None:
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path.relative_to(ROOT))


def main() -> int:
    _write_json("site/data/builder-client-catalog.json", build_public_builder_client_catalog_payload())
    _write_json("site/data/builder-client-starters.json", build_public_builder_client_starters_payload())
    _write_json("site/data/builder-starter-pack.json", build_public_builder_starter_pack_payload())
    _write_json("site/data/builder-client-configs.json", build_public_builder_client_configs_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
