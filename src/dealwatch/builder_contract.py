from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_SITE_ROOT = "https://xiaojiou176-open.github.io/dealwatch"
PUBLIC_GITHUB_BLOB_ROOT = "https://github.com/xiaojiou176-open/dealwatch/blob/main"
PUBLIC_GITHUB_TREE_ROOT = "https://github.com/xiaojiou176-open/dealwatch/tree/main"

_CLIENT_STARTER_SPECS: list[dict[str, Any]] = [
    {
        "client": "claude-code",
        "display_name": "Claude Code",
        "prompt_path": "docs/integrations/prompts/claude-code-starter.md",
        "skill_path": "docs/integrations/skills/claude-code-readonly-builder-skill.md",
        "recipe_path": "docs/integrations/recipes/claude-code.md",
        "config_wrapper_status": "official_wrapper_documented",
        "wrapper_example_kind": "official",
        "wrapper_surface": "project_.mcp.json_or_claude_mcp_add",
        "wrapper_source_url": "https://docs.anthropic.com/en/docs/claude-code/mcp",
        "wrapper_example_path": "docs/integrations/examples/claude-code.mcp.json",
        "recommended_transport": "stdio",
        "launch_command": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio",
        "safe_first_flow": [
            "get_runtime_readiness",
            "get_builder_starter_pack",
            "compare_preview",
            "list_watch_tasks or list_watch_groups",
            "get_recovery_inbox",
            "get_store_onboarding_cockpit",
        ],
        "distribution_surface_kind": "official_marketplace",
        "official_public_surface_label": "Claude Code official marketplace",
        "official_public_surface_url": "https://code.claude.com/docs/en/plugins",
        "distribution_candidate": "marketplace_submission_candidate",
        "listing_status": "not_officially_listed",
        "repo_distribution_artifacts": [
            "plugins/dealwatch-builder-pack/.claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "plugins/dealwatch-builder-pack/.mcp.json",
            "plugins/dealwatch-builder-pack/skills/dealwatch-readonly-builder/SKILL.md",
        ],
        "plugin_status": (
            "Repo-owned Claude Code plugin bundle plus builder pack. "
            "Marketplace-submission candidate only; not officially listed."
        ),
        "boundary_reminders": [
            "Do not assume write-side MCP exists.",
            "Do not present DealWatch as a hosted SaaS.",
            "Do not claim recommendation is available through builder or MCP surfaces.",
        ],
    },
    {
        "client": "codex",
        "display_name": "Codex",
        "prompt_path": "docs/integrations/prompts/codex-starter.md",
        "skill_path": "docs/integrations/skills/codex-readonly-builder-skill.md",
        "recipe_path": "docs/integrations/recipes/codex.md",
        "config_wrapper_status": "official_wrapper_documented",
        "wrapper_example_kind": "official",
        "wrapper_surface": "config_toml_mcp_servers",
        "wrapper_source_url": "https://developers.openai.com/codex/mcp/",
        "wrapper_example_path": "docs/integrations/examples/codex-mcp-config.toml",
        "recommended_transport": "streamable_http",
        "launch_command": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport streamable-http",
        "safe_first_flow": [
            "get_runtime_readiness",
            "get_builder_starter_pack",
            "compare_preview",
            "one watch or group detail read",
            "get_recovery_inbox",
            "get_store_onboarding_cockpit",
        ],
        "distribution_surface_kind": "official_plugin_directory_and_repo_marketplace",
        "official_public_surface_label": "Codex Plugin Directory",
        "official_public_surface_url": "https://developers.openai.com/codex/plugins",
        "distribution_candidate": "plugin_directory_candidate",
        "listing_status": "not_officially_listed",
        "repo_distribution_artifacts": [
            "plugins/dealwatch-builder-pack/.codex-plugin/plugin.json",
            "marketplace.json",
            "plugins/dealwatch-builder-pack/.mcp.json",
            "plugins/dealwatch-builder-pack/skills/dealwatch-readonly-builder/SKILL.md",
        ],
        "plugin_status": (
            "Repo-owned Codex plugin bundle plus repo marketplace entry. "
            "Plugin Directory candidate only; not officially listed."
        ),
        "boundary_reminders": [
            "Do not assume a hosted platform exists.",
            "Do not assume a packaged SDK exists.",
            "Do not use MCP for durable writes.",
        ],
    },
    {
        "client": "openhands",
        "display_name": "OpenHands",
        "prompt_path": "docs/integrations/prompts/openhands-starter.md",
        "skill_path": "docs/integrations/skills/openhands-readonly-builder-skill.md",
        "recipe_path": "docs/integrations/recipes/openhands.md",
        "config_wrapper_status": "official_wrapper_documented",
        "wrapper_example_kind": "official",
        "wrapper_surface": "config_toml_mcp_stdio_servers",
        "wrapper_source_url": "https://docs.openhands.dev/openhands/usage/cli/mcp-servers",
        "wrapper_example_path": "docs/integrations/examples/openhands-config.toml",
        "recommended_transport": "stdio",
        "launch_command": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio",
        "safe_first_flow": [
            "get_runtime_readiness",
            "get_builder_starter_pack",
            "compare_preview",
            "watch or group reads",
            "get_recovery_inbox",
            "get_store_onboarding_cockpit",
        ],
        "distribution_surface_kind": "official_skill_registry",
        "official_public_surface_label": "OpenHands global skill registry",
        "official_public_surface_url": "https://docs.openhands.dev/overview/skills/public",
        "distribution_candidate": "skill_registry_submission_pending",
        "listing_status": "submission_open",
        "repo_distribution_artifacts": [
            "docs/integrations/skills/openhands-readonly-builder-skill.md",
            "docs/integrations/prompts/openhands-starter.md",
            "docs/integrations/recipes/openhands.md",
        ],
        "plugin_status": (
            "Repo-owned OpenHands skill pack with a live submission receipt. "
            "OpenHands/extensions PR #152 is open; treat the listing as review-pending until it merges."
        ),
        "boundary_reminders": [
            "Do not assume destructive automation is safe.",
            "Do not assume hosted multi-tenant auth exists.",
            "Do not expose recommendation as a builder feature.",
        ],
    },
    {
        "client": "opencode",
        "display_name": "OpenCode",
        "prompt_path": "docs/integrations/prompts/opencode-starter.md",
        "skill_path": "docs/integrations/skills/opencode-readonly-builder-skill.md",
        "recipe_path": "docs/integrations/recipes/opencode.md",
        "config_wrapper_status": "official_wrapper_documented",
        "wrapper_example_kind": "official",
        "wrapper_surface": "opencode_jsonc_mcp_local_entry",
        "wrapper_source_url": "https://opencode.ai/docs/mcp-servers/",
        "wrapper_example_path": "docs/integrations/examples/opencode.jsonc",
        "recommended_transport": "stdio",
        "launch_command": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio",
        "safe_first_flow": [
            "get_runtime_readiness",
            "get_builder_starter_pack",
            "compare_preview",
            "watch or group detail reads",
            "get_recovery_inbox",
            "get_store_onboarding_cockpit",
        ],
        "distribution_surface_kind": "official_ecosystem_listing",
        "official_public_surface_label": "OpenCode ecosystem listing",
        "official_public_surface_url": "https://opencode.ai/docs/ecosystem/",
        "distribution_candidate": "ecosystem_listing_candidate",
        "listing_status": "not_officially_listed",
        "repo_distribution_artifacts": [
            "docs/integrations/examples/opencode.jsonc",
            "docs/integrations/prompts/opencode-starter.md",
            "docs/integrations/recipes/opencode.md",
        ],
        "plugin_status": (
            "Repo-owned OpenCode ecosystem candidate. "
            "The official public surface is the OpenCode ecosystem list; not officially listed."
        ),
        "boundary_reminders": [
            "Do not assume special write-side control exists.",
            "Do not assume hosted auth exists.",
            "Do not assume SDK semantics exist.",
        ],
    },
    {
        "client": "openclaw",
        "display_name": "OpenClaw",
        "prompt_path": "docs/integrations/prompts/openclaw-starter.md",
        "skill_path": "docs/integrations/skills/openclaw-readonly-builder-skill.md",
        "recipe_path": "docs/integrations/recipes/openclaw.md",
        "config_wrapper_status": "official_wrapper_documented",
        "wrapper_example_kind": "official",
        "wrapper_surface": "mcp_servers_registry_json",
        "wrapper_source_url": "https://docs.openclaw.ai/cli/mcp",
        "wrapper_example_path": "docs/integrations/examples/openclaw-mcp-servers.json",
        "recommended_transport": "stdio",
        "launch_command": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio",
        "safe_first_flow": [
            "get_runtime_readiness",
            "get_builder_starter_pack",
            "compare_preview",
            "watch or group reads",
            "get_recovery_inbox",
            "get_store_onboarding_cockpit",
        ],
        "distribution_surface_kind": "clawhub_public_registry",
        "official_public_surface_label": "OpenClaw ClawHub registry",
        "official_public_surface_url": "https://docs.openclaw.ai/tools/clawhub",
        "distribution_candidate": "clawhub_live",
        "listing_status": "live_on_clawhub",
        "repo_distribution_artifacts": [
            "docs/integrations/prompts/openclaw-starter.md",
            "docs/integrations/skills/openclaw-readonly-builder-skill.md",
            "docs/integrations/recipes/openclaw.md",
            "plugins/dealwatch-builder-pack/.claude-plugin/plugin.json",
            "plugins/dealwatch-builder-pack/.codex-plugin/plugin.json",
        ],
        "plugin_status": (
            "Repo-owned OpenClaw skill is live on ClawHub as dealwatch-readonly-builder. "
            "The official public surface is ClawHub, but the runtime story still stays local-first and read-only."
        ),
        "boundary_reminders": [
            "Do not treat DealWatch as an OpenClaw runtime base.",
            "Do not assume write-side MCP or operator automation is ready.",
            "Do not treat local-first proof surfaces as hosted control plane guarantees.",
        ],
    },
]


def list_client_starter_specs() -> list[dict[str, Any]]:
    return deepcopy(_CLIENT_STARTER_SPECS)


def list_client_ids() -> list[str]:
    return [item["client"] for item in _CLIENT_STARTER_SPECS]


def get_client_starter_spec(client: str) -> dict[str, Any]:
    normalized = str(client).strip().lower()
    for item in _CLIENT_STARTER_SPECS:
        if item["client"] == normalized:
            return deepcopy(item)
    raise ValueError("unknown_builder_client")


def build_builder_client_config_payload(client: str) -> dict[str, Any]:
    starter = get_client_starter_spec(client)
    example_path = PROJECT_ROOT / starter["wrapper_example_path"]
    example_text = example_path.read_text(encoding="utf-8")
    recipe_text = (PROJECT_ROOT / starter["recipe_path"]).read_text(encoding="utf-8")
    payload = {
        "client": starter["client"],
        "display_name": starter["display_name"],
        "recipe_path": starter["recipe_path"],
        "recipe_markdown": recipe_text,
        "prompt_path": starter["prompt_path"],
        "skill_path": starter["skill_path"],
        "config_wrapper_status": starter["config_wrapper_status"],
        "wrapper_example_kind": starter["wrapper_example_kind"],
        "wrapper_surface": starter["wrapper_surface"],
        "wrapper_source_url": starter["wrapper_source_url"],
        "wrapper_example_path": starter["wrapper_example_path"],
        "wrapper_example_language": example_path.suffix.lstrip(".") or "text",
        "wrapper_example_content": example_text,
        "recommended_transport": starter["recommended_transport"],
        "launch_command": starter["launch_command"],
        "safe_first_flow": list(starter["safe_first_flow"]),
        "boundary_reminders": list(starter["boundary_reminders"]),
        "plugin_status": starter["plugin_status"],
        "distribution_surface_kind": starter["distribution_surface_kind"],
        "official_public_surface": {
            "label": starter["official_public_surface_label"],
            "url": starter["official_public_surface_url"],
        },
        "distribution_candidate": starter["distribution_candidate"],
        "listing_status": starter["listing_status"],
        "repo_distribution_artifacts": list(starter["repo_distribution_artifacts"]),
        "read_surfaces": {
            "cli": f"PYTHONPATH=src uv run python -m dealwatch builder-client-config {starter['client']} --json",
            "http": f"GET /api/runtime/builder-client-config/{starter['client']}",
            "mcp_tool": "get_builder_client_config",
        },
        "docs": {
            "builder_pack": "docs/integrations/README.md",
            "config_recipes": "docs/integrations/config-recipes.md",
            "examples": "docs/integrations/examples/README.md",
            "prompt_starters": "docs/integrations/prompt-starters.md",
            "skills": "docs/integrations/skills/README.md",
        },
        "warning": (
            "This per-client export describes a repo-owned distribution candidate. "
            "It does not prove an official listing, hosted control plane, or write-capable MCP surface."
        ),
    }
    if starter["client"] == "codex":
        payload["runtime_endpoint"] = "http://127.0.0.1:8000/mcp"
    return payload


def build_builder_client_configs_payload() -> dict[str, Any]:
    clients = [build_builder_client_config_payload(item["client"]) for item in _CLIENT_STARTER_SPECS]
    return {
        "surface_version": "phase1",
        "export_kind": "builder_client_configs",
        "client_count": len(clients),
        "clients": clients,
        "client_ids": [item["client"] for item in _CLIENT_STARTER_SPECS],
        "read_surfaces": {
            "cli": "PYTHONPATH=src uv run python -m dealwatch builder-client-config --all --json",
            "http": "GET /api/runtime/builder-client-configs",
            "mcp_tool": "list_builder_client_configs",
        },
        "warning": (
            "This bundle is a read-only builder helper. "
            "It describes repo-owned distribution candidates, not official listings, hosted control planes, "
            "or write-capable MCP surfaces."
        ),
    }


def _github_blob_url(path: str) -> str:
    normalized = str(path).strip()
    if normalized.startswith("./"):
        normalized = normalized.removeprefix("./")
    normalized = normalized.lstrip("/")
    return f"{PUBLIC_GITHUB_BLOB_ROOT}/{normalized}"


def _github_repo_url(path: str) -> str:
    normalized = str(path).strip()
    if normalized.startswith("./"):
        normalized = normalized.removeprefix("./")
    normalized = normalized.lstrip("/")
    target = PROJECT_ROOT / normalized
    root = PUBLIC_GITHUB_TREE_ROOT if target.is_dir() else PUBLIC_GITHUB_BLOB_ROOT
    return f"{root}/{normalized}"


def _with_public_doc_urls(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, str]:
    docs = payload.get("docs", {})
    return {key: _github_blob_url(docs[key]) for key in keys if key in docs}


def build_public_builder_client_catalog_payload() -> dict[str, Any]:
    clients = []
    for starter in list_client_starter_specs():
        client = starter["client"]
        clients.append(
            {
                "client": client,
                "display_name": starter["display_name"],
                "page_fragment": f"#client-{client}",
                "page_url": f"{PUBLIC_SITE_ROOT}/builders.html#client-{client}",
                "config_wrapper_status": starter["config_wrapper_status"],
                "wrapper_example_kind": starter["wrapper_example_kind"],
                "wrapper_surface": starter["wrapper_surface"],
                "wrapper_source_url": starter["wrapper_source_url"],
                "wrapper_example_path": starter["wrapper_example_path"],
                "wrapper_example_url": _github_blob_url(starter["wrapper_example_path"]),
                "recommended_transport": starter["recommended_transport"],
                "launch_command": starter["launch_command"],
                "safe_first_flow": list(starter["safe_first_flow"]),
                "plugin_status": starter["plugin_status"],
                "distribution_surface_kind": starter["distribution_surface_kind"],
                "official_public_surface": {
                    "label": starter["official_public_surface_label"],
                    "url": starter["official_public_surface_url"],
                },
                "distribution_candidate": starter["distribution_candidate"],
                "listing_status": starter["listing_status"],
                "repo_distribution_artifacts": list(starter["repo_distribution_artifacts"]),
                "repo_distribution_artifact_urls": [
                    _github_repo_url(path) for path in starter["repo_distribution_artifacts"]
                ],
                "boundary_reminders": list(starter["boundary_reminders"]),
                "docs": {
                    "prompt_path": starter["prompt_path"],
                    "prompt_url": _github_blob_url(starter["prompt_path"]),
                    "skill_path": starter["skill_path"],
                    "skill_url": _github_blob_url(starter["skill_path"]),
                    "recipe_path": starter["recipe_path"],
                    "recipe_url": _github_blob_url(starter["recipe_path"]),
                },
                "read_surfaces": {
                    "cli": f"PYTHONPATH=src uv run python -m dealwatch builder-client-config {client} --json",
                    "http": f"GET /api/runtime/builder-client-config/{client}",
                    "mcp_tool": "get_builder_client_config",
                },
            }
        )

    return {
        "surface_version": "phase1",
        "export_kind": "public_builder_client_catalog",
        "static_surface": "github_pages_proof",
        "page_url": f"{PUBLIC_SITE_ROOT}/builders.html",
        "catalog_url": f"{PUBLIC_SITE_ROOT}/data/builder-client-catalog.json",
        "client_count": len(clients),
        "client_ids": [item["client"] for item in clients],
        "docs": {
            "builder_pack_url": _github_blob_url("docs/integrations/README.md"),
            "config_recipes_url": _github_blob_url("docs/integrations/config-recipes.md"),
            "examples_url": _github_blob_url("docs/integrations/examples/README.md"),
            "llms_url": f"{PUBLIC_SITE_ROOT}/llms.txt",
        },
        "warning": (
            "This static catalog mirrors repo-owned builder starter metadata and distribution-candidate metadata "
            "for the public proof surface. It does not prove a hosted runtime, official listing, or write-capable MCP surface."
        ),
        "clients": clients,
    }


def build_public_builder_client_starters_payload() -> dict[str, Any]:
    starters_payload = []
    for starter in list_client_starter_specs():
        prompt_path = PROJECT_ROOT / starter["prompt_path"]
        skill_path = PROJECT_ROOT / starter["skill_path"]
        starters_payload.append(
            {
                "client": starter["client"],
                "display_name": starter["display_name"],
                "prompt_path": starter["prompt_path"],
                "prompt_url": _github_blob_url(starter["prompt_path"]),
                "prompt_markdown": prompt_path.read_text(encoding="utf-8"),
                "skill_path": starter["skill_path"],
                "skill_url": _github_blob_url(starter["skill_path"]),
                "skill_markdown": skill_path.read_text(encoding="utf-8"),
                "recipe_path": starter["recipe_path"],
                "recipe_url": _github_blob_url(starter["recipe_path"]),
                "wrapper_example_path": starter["wrapper_example_path"],
                "wrapper_example_url": _github_blob_url(starter["wrapper_example_path"]),
                "config_wrapper_status": starter["config_wrapper_status"],
                "wrapper_example_kind": starter["wrapper_example_kind"],
                "wrapper_surface": starter["wrapper_surface"],
                "wrapper_source_url": starter["wrapper_source_url"],
                "recommended_transport": starter["recommended_transport"],
                "launch_command": starter["launch_command"],
                "safe_first_flow": list(starter["safe_first_flow"]),
                "plugin_status": starter["plugin_status"],
                "distribution_surface_kind": starter["distribution_surface_kind"],
                "official_public_surface": {
                    "label": starter["official_public_surface_label"],
                    "url": starter["official_public_surface_url"],
                },
                "distribution_candidate": starter["distribution_candidate"],
                "listing_status": starter["listing_status"],
                "repo_distribution_artifacts": list(starter["repo_distribution_artifacts"]),
                "repo_distribution_artifact_urls": [
                    _github_repo_url(path) for path in starter["repo_distribution_artifacts"]
                ],
                "boundary_reminders": list(starter["boundary_reminders"]),
                "page_fragment": f"#client-{starter['client']}",
                "page_url": f"{PUBLIC_SITE_ROOT}/builders.html#client-{starter['client']}",
            }
        )

    return {
        "surface_version": "phase1",
        "export_kind": "public_builder_client_starters",
        "static_surface": "github_pages_proof",
        "page_url": f"{PUBLIC_SITE_ROOT}/builders.html",
        "mirror_url": f"{PUBLIC_SITE_ROOT}/data/builder-client-starters.json",
        "client_count": len(starters_payload),
        "client_ids": [item["client"] for item in starters_payload],
        "warning": (
            "This static client-starters mirror exposes prompt starters, skill cards, and distribution-candidate "
            "metadata as public proof assets. It does not prove a hosted runtime, official listing, or write-capable MCP surface."
        ),
        "docs_urls": {
            "builder_pack_url": _github_blob_url("docs/integrations/README.md"),
            "prompt_starters_url": _github_blob_url("docs/integrations/prompt-starters.md"),
            "skills_url": _github_blob_url("docs/integrations/skills/README.md"),
            "config_recipes_url": _github_blob_url("docs/integrations/config-recipes.md"),
        },
        "clients": starters_payload,
    }


def build_public_builder_starter_pack_payload() -> dict[str, Any]:
    payload = deepcopy(build_builder_starter_pack_payload())
    payload["docs_urls"] = _with_public_doc_urls(
        payload,
        ("builder_pack", "config_recipes", "prompt_starters", "examples", "skills", "substrate_phase1"),
    )
    payload["public_builder_page_url"] = f"{PUBLIC_SITE_ROOT}/builders.html"
    payload["client_starter_urls"] = {
        key: _github_blob_url(path) for key, path in payload["client_starters"].items()
    }
    payload["client_skill_card_urls"] = {
        key: _github_blob_url(path) for key, path in payload["client_skill_cards"].items()
    }
    payload["client_adapter_recipe_urls"] = {
        key: _github_blob_url(path) for key, path in payload["client_adapter_recipes"].items()
    }
    payload["client_wrapper_example_urls"] = {
        key: _github_blob_url(path) for key, path in payload["client_wrapper_examples"].items()
    }
    payload.update(
        {
            "export_kind": "public_builder_starter_pack",
            "static_surface": "github_pages_proof",
            "page_url": f"{PUBLIC_SITE_ROOT}/builders.html",
            "mirror_url": f"{PUBLIC_SITE_ROOT}/data/builder-starter-pack.json",
            "repo_distribution_artifacts": {
                "claude_code_bundle": "plugins/dealwatch-builder-pack/.claude-plugin/plugin.json",
                "codex_bundle": "plugins/dealwatch-builder-pack/.codex-plugin/plugin.json",
                "claude_marketplace": ".claude-plugin/marketplace.json",
                "codex_marketplace": "marketplace.json",
            },
            "repo_distribution_artifact_urls": {
                "claude_code_bundle": _github_repo_url("plugins/dealwatch-builder-pack/.claude-plugin/plugin.json"),
                "codex_bundle": _github_repo_url("plugins/dealwatch-builder-pack/.codex-plugin/plugin.json"),
                "claude_marketplace": _github_repo_url(".claude-plugin/marketplace.json"),
                "codex_marketplace": _github_repo_url("marketplace.json"),
            },
            "warning": (
                "This static builder starter pack mirrors repo-owned starter and distribution-candidate metadata "
                "for the public proof surface. It does not prove a hosted runtime, official listing, or write-capable MCP surface."
            ),
        }
    )
    return payload


def build_public_builder_client_configs_payload() -> dict[str, Any]:
    payload = deepcopy(build_builder_client_configs_payload())
    payload["docs_urls"] = {
        "builder_pack_url": _github_blob_url("docs/integrations/README.md"),
        "config_recipes_url": _github_blob_url("docs/integrations/config-recipes.md"),
        "examples_url": _github_blob_url("docs/integrations/examples/README.md"),
        "prompt_starters_url": _github_blob_url("docs/integrations/prompt-starters.md"),
        "skills_url": _github_blob_url("docs/integrations/skills/README.md"),
    }
    for client_payload in payload["clients"]:
        client_payload["prompt_url"] = _github_blob_url(client_payload["prompt_path"])
        client_payload["skill_url"] = _github_blob_url(client_payload["skill_path"])
        client_payload["recipe_url"] = _github_blob_url(client_payload["recipe_path"])
        client_payload["wrapper_example_url"] = _github_blob_url(client_payload["wrapper_example_path"])
    payload.update(
        {
            "export_kind": "public_builder_client_configs",
            "static_surface": "github_pages_proof",
            "page_url": f"{PUBLIC_SITE_ROOT}/builders.html",
            "mirror_url": f"{PUBLIC_SITE_ROOT}/data/builder-client-configs.json",
            "warning": (
                "This static client-config bundle mirrors repo-owned builder client exports and distribution-candidate "
                "metadata for the public proof surface. It does not prove a hosted runtime, official listing, or write-capable MCP surface."
            ),
        }
    )
    return payload


def build_builder_starter_pack_payload() -> dict[str, Any]:
    starters = list_client_starter_specs()

    def _client_key(client: str) -> str:
        return client.replace("-", "_")

    return {
        "surface_version": "phase1",
        "product_shape": {
            "name": "DealWatch",
            "positioning": "AI-enhanced, compare-first grocery price intelligence",
            "runtime": "local-first",
            "builder_posture": "read-only-first",
        },
        "launch_contract": {
            "cli_discovery": "PYTHONPATH=src uv run python -m dealwatch --help",
            "cli_builder_starter_pack": "PYTHONPATH=src uv run python -m dealwatch builder-starter-pack --json",
            "cli_builder_client_config": "PYTHONPATH=src uv run python -m dealwatch builder-client-config <client> --json",
            "cli_builder_client_configs": "PYTHONPATH=src uv run python -m dealwatch builder-client-config --all --json",
            "http_server": "PYTHONPATH=src uv run python -m dealwatch server",
            "mcp_inventory": "PYTHONPATH=src uv run python -m dealwatch.mcp list-tools --json",
            "mcp_client_starters": "PYTHONPATH=src uv run python -m dealwatch.mcp client-starters --json",
            "mcp_stdio": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport stdio",
            "mcp_streamable_http": "PYTHONPATH=src uv run python -m dealwatch.mcp serve --transport streamable-http",
            "mcp_streamable_http_endpoint": "http://127.0.0.1:8000/mcp",
            "http_builder_client_config": "GET /api/runtime/builder-client-config/{client}",
            "http_builder_client_configs": "GET /api/runtime/builder-client-configs",
            "mcp_builder_client_config": "get_builder_client_config",
            "mcp_builder_client_configs": "list_builder_client_configs",
        },
        "safe_first_loops": {
            "http": [
                "GET /api/health",
                "GET /api/runtime/readiness",
                "GET /api/runtime/builder-starter-pack",
                "POST /api/compare/preview",
                "GET /api/watch-tasks or GET /api/watch-groups",
            ],
            "mcp": [
                "list_tools",
                "get_runtime_readiness",
                "get_builder_starter_pack",
                "compare_preview",
                "list_watch_tasks or list_watch_groups",
            ],
        },
        "stable_now": [
            "read-only MCP tool inventory",
            "runtime readiness reads",
            "builder starter pack reads",
            "builder client config reads",
            "builder client config bundle reads",
            "compare preview",
            "watch task and watch group reads",
            "recovery inbox reads",
            "notification settings reads",
            "store onboarding cockpit reads",
        ],
        "deferred": [
            "write-side MCP",
            "hosted auth",
            "formal SDK packaging",
            "generic remote operator automation",
            "public recommendation surface",
        ],
        "internal_only": [
            "maintenance",
            "bootstrap-owner",
            "legacy bridge commands",
            "provider webhook paths",
            "maintainer-only browser debug commands",
        ],
        "client_starters": {_client_key(item["client"]): item["prompt_path"] for item in starters},
        "client_skill_cards": {_client_key(item["client"]): item["skill_path"] for item in starters},
        "client_adapter_recipes": {_client_key(item["client"]): item["recipe_path"] for item in starters},
        "client_wrapper_status": {
            _client_key(item["client"]): item["config_wrapper_status"] for item in starters
        },
        "client_wrapper_example_kind": {
            _client_key(item["client"]): item["wrapper_example_kind"] for item in starters
        },
        "client_wrapper_examples": {
            _client_key(item["client"]): item["wrapper_example_path"] for item in starters
        },
        "client_wrapper_sources": {
            _client_key(item["client"]): item["wrapper_source_url"] for item in starters
        },
        "client_wrapper_surfaces": {
            _client_key(item["client"]): item["wrapper_surface"] for item in starters
        },
        "skill_pack": {
            "path": "docs/integrations/skills/dealwatch-readonly-builder-skill.md",
            "intent": "Copyable builder skill card for coding agents that should stay inside the current read-only DealWatch contract.",
        },
        "docs": {
            "builder_pack": "docs/integrations/README.md",
            "config_recipes": "docs/integrations/config-recipes.md",
            "prompt_starters": "docs/integrations/prompt-starters.md",
            "examples": "docs/integrations/examples/README.md",
            "skills": "docs/integrations/skills/README.md",
            "substrate_phase1": "docs/roadmaps/dealwatch-api-mcp-substrate-phase1.md",
        },
        "public_builder_page": "site/builders.html",
        "warning": (
            "Treat DealWatch as a local-first read-only decision backend. "
            "Do not present it as a hosted SaaS, formal SDK, official listing, "
            "or write-capable remote control plane."
        ),
        "repo_distribution_artifacts": {
            "claude_code_bundle": "plugins/dealwatch-builder-pack/.claude-plugin/plugin.json",
            "codex_bundle": "plugins/dealwatch-builder-pack/.codex-plugin/plugin.json",
            "claude_marketplace": ".claude-plugin/marketplace.json",
            "codex_marketplace": "marketplace.json",
        },
    }
