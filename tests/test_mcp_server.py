from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dealwatch.application.services import ProductService
from dealwatch.builder_contract import (
    build_builder_client_configs_payload,
    build_public_builder_client_catalog_payload,
    build_public_builder_client_configs_payload,
    build_public_builder_client_starters_payload,
    build_public_builder_starter_pack_payload,
)
from dealwatch.core.models import Offer, PriceContext
from dealwatch.infra.config import Settings
from dealwatch.mcp import server as mcp_server_module
from dealwatch.persistence.session import get_session_factory, init_product_database
from dealwatch.persistence.store_bindings import sync_store_adapter_bindings
from dealwatch.providers.cashback.base import CashbackQuoteResult
from dealwatch.providers.email.base import EmailDispatchResult
from dealwatch.stores.manifest import STORE_CAPABILITY_REGISTRY


class _FakeCashbackProvider:
    async def fetch_quote(self, payload):
        return CashbackQuoteResult(
            provider="cashbackmonitor",
            merchant_key=payload.merchant_key,
            rate_type="percent",
            rate_value=10.0,
            conditions_text="fake",
            source_url="https://example.com/cashback",
            confidence=0.8,
        )


class _FakeEmailProvider:
    async def send(self, payload):
        return EmailDispatchResult(
            provider="smtp",
            status="sent",
            message_id="msg-1",
            payload={"recipient": payload.recipient},
        )


def test_mcp_tool_specs_are_read_only_wave4_mvp() -> None:
    specs = mcp_server_module.list_tool_specs()
    names = [item["name"] for item in specs]
    safe_first_names = [item["name"] for item in specs if item["safe_first"]]
    categories = {item["name"]: item["category"] for item in specs}

    assert "compare_preview" in names
    assert "get_builder_starter_pack" in names
    assert "get_builder_client_config" in names
    assert "list_builder_client_configs" in names
    assert "get_store_onboarding_cockpit" in names
    assert "run_watch_task" not in names
    assert "run_watch_group" not in names
    assert all(item["read_only"] is True for item in specs)
    assert safe_first_names == ["compare_preview", "get_runtime_readiness", "get_builder_starter_pack"]
    assert categories["compare_preview"] == "compare"
    assert categories["get_builder_starter_pack"] == "builder"
    assert categories["get_builder_client_config"] == "builder"
    assert categories["list_builder_client_configs"] == "builder"
    assert categories["get_store_onboarding_cockpit"] == "store"


def test_mcp_list_tools_response_snapshot_matches_current_registry() -> None:
    snapshot_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "integrations"
        / "examples"
        / "mcp-list-tools.response.json"
    )

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == mcp_server_module.list_tool_specs()


def test_mcp_client_starters_snapshot_matches_current_registry() -> None:
    snapshot_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "integrations"
        / "examples"
        / "mcp-client-starters.response.json"
    )

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == mcp_server_module.list_client_starter_specs()


def test_mcp_builder_client_config_examples_match_current_payload() -> None:
    root = Path(__file__).resolve().parents[1] / "docs" / "integrations" / "examples"
    expected_payload = mcp_server_module._builder_client_config_payload("codex")

    assert json.loads((root / "cli-builder-client-config.response.json").read_text(encoding="utf-8")) == expected_payload
    assert json.loads((root / "http-builder-client-config.response.json").read_text(encoding="utf-8")) == expected_payload
    assert json.loads((root / "mcp-builder-client-config.call.json").read_text(encoding="utf-8")) == {
        "tool": "get_builder_client_config",
        "arguments": {"client": "codex"},
    }
    expected_bundle = build_builder_client_configs_payload()
    assert json.loads((root / "cli-builder-client-configs.response.json").read_text(encoding="utf-8")) == expected_bundle
    assert json.loads((root / "http-builder-client-configs.response.json").read_text(encoding="utf-8")) == expected_bundle
    assert json.loads((root / "mcp-builder-client-configs.call.json").read_text(encoding="utf-8")) == {
        "tool": "list_builder_client_configs",
        "arguments": {},
    }


def test_builder_client_config_examples_snapshot_match_current_payload() -> None:
    root = Path(__file__).resolve().parents[1] / "docs" / "integrations" / "examples"
    expected_payload = mcp_server_module._builder_client_config_payload("codex")

    assert json.loads((root / "cli-builder-client-config.response.json").read_text(encoding="utf-8")) == expected_payload
    assert json.loads((root / "http-builder-client-config.response.json").read_text(encoding="utf-8")) == expected_payload
    assert json.loads((root / "mcp-builder-client-config.call.json").read_text(encoding="utf-8")) == {
        "tool": "get_builder_client_config",
        "arguments": {"client": "codex"},
    }


def test_public_builder_client_catalog_snapshot_matches_current_payload() -> None:
    snapshot_path = Path(__file__).resolve().parents[1] / "site" / "data" / "builder-client-catalog.json"

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == build_public_builder_client_catalog_payload()


def test_public_builder_client_starters_snapshot_matches_current_payload() -> None:
    snapshot_path = Path(__file__).resolve().parents[1] / "site" / "data" / "builder-client-starters.json"

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == build_public_builder_client_starters_payload()


def test_public_builder_starter_pack_snapshot_matches_current_payload() -> None:
    snapshot_path = Path(__file__).resolve().parents[1] / "site" / "data" / "builder-starter-pack.json"

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == build_public_builder_starter_pack_payload()


def test_public_builder_client_configs_snapshot_matches_current_payload() -> None:
    snapshot_path = Path(__file__).resolve().parents[1] / "site" / "data" / "builder-client-configs.json"

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == build_public_builder_client_configs_payload()


def test_mcp_client_config_cli_prints_json(capsys) -> None:
    exit_code = mcp_server_module.main(["client-config", "--client", "codex", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["client"] == "codex"
    assert payload["read_surfaces"]["mcp_tool"] == "get_builder_client_config"
    assert payload["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert "http://127.0.0.1:8000/mcp" in payload["wrapper_example_content"]


def test_mcp_client_config_cli_rejects_client_and_all(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        mcp_server_module.main(["client-config", "--client", "codex", "--all", "--json"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 2
    assert "not allowed with argument" in captured.err


def test_mcp_list_tools_snapshot_matches_current_registry() -> None:
    snapshot_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "integrations"
        / "examples"
        / "mcp-list-tools.response.json"
    )

    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == mcp_server_module.list_tool_specs()


def test_mcp_client_starters_include_openclaw_without_plugin_claim() -> None:
    starters = {item["client"]: item for item in mcp_server_module.list_client_starter_specs()}

    assert "openclaw" in starters
    assert starters["openclaw"]["prompt_path"] == "docs/integrations/prompts/openclaw-starter.md"
    assert starters["openclaw"]["skill_path"] == "docs/integrations/skills/openclaw-readonly-builder-skill.md"
    assert starters["openclaw"]["recipe_path"] == "docs/integrations/recipes/openclaw.md"
    assert starters["openclaw"]["wrapper_example_path"] == "docs/integrations/examples/openclaw-mcp-servers.json"
    assert starters["openclaw"]["config_wrapper_status"] == "official_wrapper_documented"
    assert "ClawHub" in starters["openclaw"]["plugin_status"]
    assert starters["openclaw"]["distribution_surface_kind"] == "clawhub_public_registry"
    assert starters["openclaw"]["listing_status"] == "no_fresh_public_evidence"
    assert "fresh listing proof" in starters["openclaw"]["plugin_status"]


def test_mcp_client_starters_keep_platform_specific_distribution_wording() -> None:
    starters = {item["client"]: item for item in mcp_server_module.list_client_starter_specs()}

    assert starters["claude-code"]["distribution_surface_kind"] == "official_marketplace"
    assert "Marketplace-submission candidate" in starters["claude-code"]["plugin_status"]
    assert starters["codex"]["distribution_surface_kind"] == "official_plugin_directory_and_repo_marketplace"
    assert "Plugin Directory candidate" in starters["codex"]["plugin_status"]
    assert starters["openhands"]["distribution_surface_kind"] == "official_skill_registry"
    assert "skill registry" in starters["openhands"]["official_public_surface_label"].lower()
    assert "#151" in starters["openhands"]["plugin_status"]
    assert "retired predecessor" in starters["openhands"]["plugin_status"]
    assert starters["opencode"]["distribution_surface_kind"] == "official_ecosystem_listing"
    assert "ecosystem list" in starters["opencode"]["plugin_status"]
    assert starters["openclaw"]["distribution_surface_kind"] == "clawhub_public_registry"
    assert "ClawHub" in starters["openclaw"]["plugin_status"]
    assert starters["claude-code"]["listing_status"] == "not_officially_listed"
    assert starters["codex"]["listing_status"] == "not_officially_listed"
    assert starters["openhands"]["listing_status"] == "closed_unmerged_not_accepted"
    assert starters["opencode"]["listing_status"] == "not_officially_listed"
    assert starters["openclaw"]["listing_status"] == "no_fresh_public_evidence"


def test_mcp_client_starters_include_recipe_paths_and_wrapper_status() -> None:
    starters = mcp_server_module.list_client_starter_specs()
    recipe_root = Path(__file__).resolve().parents[1]
    allowed_statuses = {"official_wrapper_documented", "official_local_config_documented"}

    assert starters
    for item in starters:
        assert item["config_wrapper_status"] in allowed_statuses
        recipe_path = recipe_root / item["recipe_path"]
        assert recipe_path.exists(), f"missing recipe file for {item['client']}: {recipe_path}"
        wrapper_example_path = item["wrapper_example_path"]
        if wrapper_example_path is not None:
            assert (recipe_root / wrapper_example_path).exists(), (
                f"missing wrapper example for {item['client']}: {wrapper_example_path}"
            )
        for path in item["repo_distribution_artifacts"]:
            assert (recipe_root / path).exists(), (
                f"missing repo distribution artifact for {item['client']}: {path}"
            )


def test_mcp_client_starters_expose_wrapper_examples_where_the_repo_freezes_them() -> None:
    starters = {item["client"]: item for item in mcp_server_module.list_client_starter_specs()}
    repo_root = Path(__file__).resolve().parents[1]

    assert starters["claude-code"]["wrapper_source_url"].rstrip("/") == "https://docs.anthropic.com/en/docs/claude-code/mcp"
    assert starters["claude-code"]["wrapper_example_path"] == "docs/integrations/examples/claude-code.mcp.json"
    assert (repo_root / starters["claude-code"]["wrapper_example_path"]).exists()
    assert starters["codex"]["wrapper_source_url"].rstrip("/") == "https://developers.openai.com/codex/mcp"
    assert starters["codex"]["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert (repo_root / starters["codex"]["wrapper_example_path"]).exists()
    assert starters["openhands"]["wrapper_source_url"] == "https://docs.openhands.dev/openhands/usage/cli/mcp-servers"
    assert starters["openhands"]["wrapper_example_path"] == "docs/integrations/examples/openhands-config.toml"
    assert (repo_root / starters["openhands"]["wrapper_example_path"]).exists()
    assert starters["opencode"]["wrapper_source_url"] == "https://opencode.ai/docs/mcp-servers/"
    assert starters["opencode"]["wrapper_example_path"] == "docs/integrations/examples/opencode.jsonc"
    assert (repo_root / starters["opencode"]["wrapper_example_path"]).exists()
    assert starters["openclaw"]["wrapper_source_url"] == "https://docs.openclaw.ai/cli/mcp"
    assert starters["openclaw"]["wrapper_example_path"] == "docs/integrations/examples/openclaw-mcp-servers.json"
    assert (repo_root / starters["openclaw"]["wrapper_example_path"]).exists()


def test_client_prompt_files_keep_builder_starter_pack_in_safe_first_order() -> None:
    root = Path(__file__).resolve().parents[1]

    for item in mcp_server_module.list_client_starter_specs():
        prompt_text = (root / item["prompt_path"]).read_text(encoding="utf-8")
        assert re.search(r"builder starter pack|get_builder_starter_pack", prompt_text, re.I), (
            f"prompt missing builder starter pack step: {item['prompt_path']}"
        )


def test_mcp_client_config_cli_prints_json_snapshot(capsys) -> None:
    assert mcp_server_module.main(["client-config", "--client", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["client"] == "codex"
    assert payload["read_surfaces"]["mcp_tool"] == "get_builder_client_config"
    assert payload["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"


@pytest.mark.asyncio
async def test_mcp_runtime_reads_compare_and_store_cockpit(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'mcp-runtime.db'}"
    await init_product_database(db_url)
    session_factory = get_session_factory(db_url)
    app_settings = Settings(
        DATABASE_URL=db_url,
        OWNER_EMAIL="owner@example.com",
        OWNER_BOOTSTRAP_TOKEN="real-bootstrap-token",
        APP_BASE_URL="http://127.0.0.1:8000",
        WEBUI_DEV_URL="http://127.0.0.1:5173",
        ZIP_CODE="98004",
        ENABLED_STORES=["weee", "ranch99"],
        SMTP_HOST="",
    )
    await sync_store_adapter_bindings(session_factory, app_settings)
    service = ProductService(
        session_factory=session_factory,
        settings=app_settings,
        cashback_provider=_FakeCashbackProvider(),
        email_provider=_FakeEmailProvider(),
    )

    async def _fake_fetch_offer(product_url: str, store_key: str, *, zip_code: str):
        return Offer(
            store_id=store_key,
            product_key=f"{store_key}-1",
            title="Asian Honey Pears 3ct",
            url=product_url,
            price=4.2 if store_key == "weee" else 4.49,
            original_price=5.5,
            fetch_at=datetime.now(timezone.utc),
            context=PriceContext(region=zip_code),
            unit_price_info={"raw": "3 ct", "brand": "Golden Orchard"},
        )

    async def _noop_prepare() -> None:
        return None

    monkeypatch.setattr(service, "_fetch_offer", _fake_fetch_offer)
    monkeypatch.setattr(mcp_server_module, "prepare_product_runtime", _noop_prepare)
    monkeypatch.setattr(mcp_server_module, "get_product_service", lambda: service)

    runtime = mcp_server_module.DealWatchMcpRuntime()
    compare_payload = await runtime.compare_preview(
        submitted_urls=[
            "https://www.sayweee.com/zh/product/Asian-Honey-Pears-3ct/5869",
            "https://www.99ranch.com/product-details/1615424/8899/078895126389",
        ],
        zip_code="98004",
    )
    builder_payload = await runtime.get_builder_starter_pack()
    config_payload = await runtime.get_builder_client_config(client="codex")
    bundle_payload = await runtime.list_builder_client_configs()
    cockpit_payload = await runtime.get_store_onboarding_cockpit()

    assert compare_payload["recommended_next_step_hint"]["action"] == "create_watch_group"
    assert compare_payload["compare_evidence"]["successful_candidate_count"] == 2
    assert builder_payload["client_starters"]["openclaw"] == "docs/integrations/prompts/openclaw-starter.md"
    assert (
        builder_payload["client_skill_cards"]["openclaw"]
        == "docs/integrations/skills/openclaw-readonly-builder-skill.md"
    )
    assert builder_payload["client_adapter_recipes"]["claude_code"] == "docs/integrations/recipes/claude-code.md"
    assert builder_payload["client_wrapper_status"]["claude_code"] == "official_wrapper_documented"
    assert builder_payload["client_wrapper_status"]["codex"] == "official_wrapper_documented"
    assert builder_payload["client_wrapper_status"]["openhands"] == "official_wrapper_documented"
    assert builder_payload["client_wrapper_status"]["openclaw"] == "official_wrapper_documented"
    assert builder_payload["client_wrapper_examples"]["claude_code"] == "docs/integrations/examples/claude-code.mcp.json"
    assert builder_payload["client_wrapper_examples"]["openhands"] == "docs/integrations/examples/openhands-config.toml"
    assert builder_payload["client_wrapper_examples"]["openclaw"] == "docs/integrations/examples/openclaw-mcp-servers.json"
    assert (
        builder_payload["client_wrapper_sources"]["openhands"]
        == "https://docs.openhands.dev/openhands/usage/cli/mcp-servers"
    )
    assert builder_payload["client_wrapper_sources"]["opencode"] == "https://opencode.ai/docs/mcp-servers/"
    assert config_payload["client"] == "codex"
    assert config_payload["wrapper_example_path"] == "docs/integrations/examples/codex-mcp-config.toml"
    assert config_payload["recommended_transport"] == "streamable_http"
    assert "http://127.0.0.1:8000/mcp" in config_payload["wrapper_example_content"]
    assert bundle_payload["export_kind"] == "builder_client_configs"
    assert bundle_payload["client_count"] == 5
    assert bundle_payload["read_surfaces"]["mcp_tool"] == "list_builder_client_configs"
    assert builder_payload["client_wrapper_surfaces"]["openhands"] == "config_toml_mcp_stdio_servers"
    assert builder_payload["launch_contract"]["mcp_streamable_http"].endswith(
        "dealwatch.mcp serve --transport streamable-http"
    )
    assert builder_payload["launch_contract"]["mcp_streamable_http_endpoint"] == "http://127.0.0.1:8000/mcp"
    assert "get_builder_starter_pack" in builder_payload["safe_first_loops"]["mcp"]
    assert builder_payload["docs"]["config_recipes"] == "docs/integrations/config-recipes.md"
    assert builder_payload["skill_pack"]["path"] == "docs/integrations/skills/dealwatch-readonly-builder-skill.md"
    assert cockpit_payload["summary"]["supported_store_count"] == len(STORE_CAPABILITY_REGISTRY)
    assert cockpit_payload["summary"]["enabled_store_count"] == 2
    assert cockpit_payload["consistency"]["registry_matches_capability_registry"] is True
    assert cockpit_payload["onboarding_contract"]["source_runbook_path"] == "docs/runbooks/store-onboarding-contract.md"
