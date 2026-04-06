from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dealwatch import cli


def test_cli_help_flag_is_a_stable_discovery_path(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["python", "--help"])

    cli.main()

    captured = capsys.readouterr()
    expected = (
        Path(__file__).resolve().parents[1] / "docs" / "integrations" / "examples" / "cli-root-help.txt"
    ).read_text(encoding="utf-8")

    assert captured.out.rstrip("\n") == expected.rstrip("\n")
    assert captured.err == ""


def test_cli_builder_starter_pack_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["python", "builder-starter-pack", "--json"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert excinfo.value.code == 0
    assert payload["surface_version"] == "phase1"
    assert payload["launch_contract"]["cli_builder_starter_pack"].endswith("dealwatch builder-starter-pack --json")
    assert payload["launch_contract"]["mcp_client_starters"].endswith("dealwatch.mcp client-starters --json")
    assert payload["launch_contract"]["mcp_streamable_http"].endswith("dealwatch.mcp serve --transport streamable-http")
    assert payload["launch_contract"]["mcp_streamable_http_endpoint"] == "http://127.0.0.1:8000/mcp"
    assert payload["client_starters"]["openclaw"] == "docs/integrations/prompts/openclaw-starter.md"
    assert payload["client_adapter_recipes"]["claude_code"] == "docs/integrations/recipes/claude-code.md"
    assert payload["client_wrapper_status"]["claude_code"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["codex"] == "official_wrapper_documented"
    assert payload["client_wrapper_status"]["openhands"] == "official_wrapper_documented"
    assert payload["client_wrapper_sources"]["claude_code"] == "https://docs.anthropic.com/en/docs/claude-code/mcp"
    assert payload["client_wrapper_sources"]["codex"] == "https://developers.openai.com/codex/mcp/"
    assert payload["client_wrapper_examples"]["claude_code"] == "docs/integrations/examples/claude-code.mcp.json"
    assert payload["client_wrapper_examples"]["codex"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert payload["client_wrapper_examples"]["openhands"] == "docs/integrations/examples/openhands-config.toml"
    assert payload["client_wrapper_examples"]["opencode"] == "docs/integrations/examples/opencode.jsonc"
    assert payload["client_wrapper_examples"]["openclaw"] == "docs/integrations/examples/openclaw-mcp-servers.json"
    assert payload["client_wrapper_surfaces"]["openhands"] == "config_toml_mcp_stdio_servers"
    assert payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert payload["skill_pack"]["path"] == "docs/integrations/skills/dealwatch-readonly-builder-skill.md"
    assert captured.err == ""


def test_cli_builder_client_config_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["python", "builder-client-config", "codex", "--json"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert excinfo.value.code == 0
    assert payload["client"] == "codex"
    assert payload["recommended_transport"] == "streamable_http"
    assert payload["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert payload["recipe_markdown"].startswith("# DealWatch Recipe For Codex")
    assert payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert payload["read_surfaces"]["cli"].endswith("dealwatch builder-client-config codex --json")
    assert payload["read_surfaces"]["http"] == "GET /api/runtime/builder-client-config/codex"
    assert "http://127.0.0.1:8000/mcp" in payload["wrapper_example_content"]
    assert captured.err == ""


def test_cli_builder_client_config_all_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["python", "builder-client-config", "--all", "--json"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert excinfo.value.code == 0
    assert payload["export_kind"] == "builder_client_configs"
    assert payload["client_count"] == 5
    assert payload["client_ids"] == ["claude-code", "codex", "openhands", "opencode", "openclaw"]
    assert payload["read_surfaces"]["cli"].endswith("dealwatch builder-client-config --all --json")
    assert payload["read_surfaces"]["http"] == "GET /api/runtime/builder-client-configs"
    assert payload["read_surfaces"]["mcp_tool"] == "list_builder_client_configs"
    assert captured.err == ""


def test_cli_builder_client_config_rejects_client_and_all(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["python", "builder-client-config", "codex", "--all"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    captured = capsys.readouterr()

    assert excinfo.value.code == 2
    assert "requires exactly one of <client> or --all" in captured.err
