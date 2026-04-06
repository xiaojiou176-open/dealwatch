from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from dealwatch.api.deps import get_product_service, prepare_product_runtime, shutdown_product_runtime
from dealwatch.application import ProductService
from dealwatch.builder_contract import (
    build_builder_client_config_payload,
    build_builder_client_configs_payload,
    list_client_ids,
    list_client_starter_specs as list_builder_client_starter_specs,
)

_TOOL_SPECS = [
    {
        "name": "compare_preview",
        "description": "Preview compare-first pricing truth across multiple submitted product URLs without persisting tasks.",
        "read_only": True,
        "category": "compare",
        "stability": "stable_now",
        "safe_first": True,
        "recommended_order": 2,
        "arguments": [
            {
                "name": "submitted_urls",
                "type": "list[str]",
                "required": True,
                "description": "Product URLs to compare without persisting durable state.",
            },
            {
                "name": "zip_code",
                "type": "str",
                "required": False,
                "default": "00000",
                "description": "ZIP code used for compare context.",
            },
        ],
    },
    {
        "name": "list_watch_tasks",
        "description": "List current watch tasks with their runtime truth summary.",
        "read_only": True,
        "category": "watch-task",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 4,
        "arguments": [],
    },
    {
        "name": "get_watch_task_detail",
        "description": "Get one watch task detail, including observations, runs, and recovery truth.",
        "read_only": True,
        "category": "watch-task",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 5,
        "arguments": [
            {
                "name": "task_id",
                "type": "str",
                "required": True,
                "description": "Watch-task identifier returned by list or create flows.",
            }
        ],
    },
    {
        "name": "list_watch_groups",
        "description": "List current watch groups with their compare-first runtime summary.",
        "read_only": True,
        "category": "watch-group",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 4,
        "arguments": [],
    },
    {
        "name": "get_watch_group_detail",
        "description": "Get one watch group detail, including decision explain and delivery truth.",
        "read_only": True,
        "category": "watch-group",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 5,
        "arguments": [
            {
                "name": "group_id",
                "type": "str",
                "required": True,
                "description": "Watch-group identifier returned by list or create flows.",
            }
        ],
    },
    {
        "name": "get_runtime_readiness",
        "description": "Inspect runtime readiness truth for database, stores, startup preflight, and smoke evidence.",
        "read_only": True,
        "category": "runtime",
        "stability": "stable_now",
        "safe_first": True,
        "recommended_order": 1,
        "arguments": [],
    },
    {
        "name": "get_builder_starter_pack",
        "description": "Return the read-only builder contract: launch commands, stable/deferred/internal-only surfaces, and starter docs for coding agents.",
        "read_only": True,
        "category": "builder",
        "stability": "stable_now",
        "safe_first": True,
        "recommended_order": 3,
        "arguments": [],
    },
    {
        "name": "get_recovery_inbox",
        "description": "Inspect the recovery inbox that separates task and group attention items.",
        "read_only": True,
        "category": "recovery",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 6,
        "arguments": [],
    },
    {
        "name": "list_notifications",
        "description": "List recent notification delivery events without exposing provider secrets.",
        "read_only": True,
        "category": "notification",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 6,
        "arguments": [
            {
                "name": "limit",
                "type": "int",
                "required": False,
                "default": 50,
                "description": "Maximum number of delivery events to return.",
            }
        ],
    },
    {
        "name": "get_notification_settings",
        "description": "Read the effective notification settings without bootstrapping or mutating owner records.",
        "read_only": True,
        "category": "notification",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 6,
        "arguments": [],
    },
    {
        "name": "list_store_bindings",
        "description": "List store binding runtime switches together with capability metadata.",
        "read_only": True,
        "category": "store",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 6,
        "arguments": [],
    },
    {
        "name": "get_store_onboarding_cockpit",
        "description": "Return the store onboarding cockpit truth surface: capability matrix, checklist, required files, commands, and registry consistency.",
        "read_only": True,
        "category": "store",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 7,
        "arguments": [],
    },
    {
        "name": "get_builder_client_config",
        "description": "Return one repo-owned builder client config export, including wrapper metadata and the copyable example content.",
        "read_only": True,
        "category": "builder",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 4,
        "arguments": [
            {
                "name": "client",
                "type": "str",
                "required": True,
                "description": "Builder client key such as claude-code, codex, openhands, opencode, or openclaw.",
            }
        ],
    },
    {
        "name": "list_builder_client_configs",
        "description": "Return the repo-owned bundle of all builder client config exports in one read-only payload.",
        "read_only": True,
        "category": "builder",
        "stability": "stable_now",
        "safe_first": False,
        "recommended_order": 5,
        "arguments": [],
    },
]

_CLIENT_STARTER_SPECS = list_builder_client_starter_specs()


class ReadonlyProductMcpBridge:
    def __init__(self, service_factory: Callable[[], ProductService]) -> None:
        self._service_factory = service_factory

    async def _with_session(
        self,
        operation: Callable[[ProductService, AsyncSession], Awaitable[Any]],
    ) -> Any:
        service = self._service_factory()
        async with service.session_factory() as session:
            try:
                return await operation(service, session)
            finally:
                await session.rollback()

    async def compare_preview(self, *, submitted_urls: list[str], zip_code: str = "00000") -> dict[str, Any]:
        return await self._with_session(
            lambda service, session: service.compare_product_urls(
                submitted_urls=submitted_urls,
                zip_code=zip_code,
                session=session,
            )
        )

    async def list_watch_tasks(self) -> list[dict[str, Any]]:
        return await self._with_session(lambda service, session: service.list_watch_tasks(session))

    async def get_watch_task_detail(self, *, task_id: str) -> dict[str, Any]:
        return await self._with_session(lambda service, session: service.get_watch_task_detail(session, task_id))

    async def list_watch_groups(self) -> list[dict[str, Any]]:
        return await self._with_session(lambda service, session: service.list_watch_groups(session))

    async def get_watch_group_detail(self, *, group_id: str) -> dict[str, Any]:
        return await self._with_session(lambda service, session: service.get_watch_group_detail(session, group_id))

    async def get_runtime_readiness(self) -> dict[str, Any]:
        return await self._with_session(lambda service, session: service.get_runtime_readiness(session))

    async def get_builder_starter_pack(self) -> dict[str, Any]:
        service = self._service_factory()
        return await service.get_builder_starter_pack()

    async def get_builder_client_config(self, *, client: str) -> dict[str, Any]:
        service = self._service_factory()
        return await service.get_builder_client_config(client)

    async def list_builder_client_configs(self) -> dict[str, Any]:
        service = self._service_factory()
        return await service.get_builder_client_configs()

    async def get_recovery_inbox(self) -> dict[str, Any]:
        return await self._with_session(lambda service, session: service.get_recovery_inbox(session))

    async def list_notifications(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return await self._with_session(lambda service, session: service.list_notification_events(session, limit=limit))

    async def get_notification_settings(self) -> dict[str, Any]:
        return await self._with_session(lambda service, session: service.get_notification_settings_readonly(session))

    async def list_store_bindings(self) -> list[dict[str, Any]]:
        return await self._with_session(lambda service, session: service.list_store_bindings(session))

    async def get_store_onboarding_cockpit(self) -> dict[str, Any]:
        return await self._with_session(lambda service, session: service.get_store_onboarding_cockpit(session))


class DealWatchMcpRuntime(ReadonlyProductMcpBridge):
    def __init__(self, service_factory: Callable[[], ProductService] | None = None) -> None:
        super().__init__(service_factory or get_product_service)


@asynccontextmanager
async def _runtime_lifespan(_: FastMCP):
    await prepare_product_runtime()
    try:
        yield
    finally:
        await shutdown_product_runtime()


def create_mcp_server(bridge: ReadonlyProductMcpBridge | None = None) -> FastMCP:
    readonly_bridge = bridge or DealWatchMcpRuntime()
    server = FastMCP(
        name="dealwatch",
        instructions=(
            "Read-only DealWatch MCP server. It exposes compare, watch, runtime, notification, "
            "store-binding, and store-onboarding cockpit truth without maintenance, cleanup, "
            "legacy import, or write-side operator actions."
        ),
        lifespan=_runtime_lifespan,
    )

    @server.tool(
        description=_TOOL_SPECS[0]["description"]
    )
    async def compare_preview(submitted_urls: list[str], zip_code: str = "00000") -> dict[str, Any]:
        return await readonly_bridge.compare_preview(submitted_urls=submitted_urls, zip_code=zip_code)

    @server.tool(description=_TOOL_SPECS[1]["description"])
    async def list_watch_tasks() -> list[dict[str, Any]]:
        return await readonly_bridge.list_watch_tasks()

    @server.tool(description=_TOOL_SPECS[2]["description"])
    async def get_watch_task_detail(task_id: str) -> dict[str, Any]:
        return await readonly_bridge.get_watch_task_detail(task_id=task_id)

    @server.tool(description=_TOOL_SPECS[3]["description"])
    async def list_watch_groups() -> list[dict[str, Any]]:
        return await readonly_bridge.list_watch_groups()

    @server.tool(description=_TOOL_SPECS[4]["description"])
    async def get_watch_group_detail(group_id: str) -> dict[str, Any]:
        return await readonly_bridge.get_watch_group_detail(group_id=group_id)

    @server.tool(description=_TOOL_SPECS[5]["description"])
    async def get_runtime_readiness() -> dict[str, Any]:
        return await readonly_bridge.get_runtime_readiness()

    @server.tool(description=_TOOL_SPECS[6]["description"])
    async def get_builder_starter_pack() -> dict[str, Any]:
        return await readonly_bridge.get_builder_starter_pack()

    @server.tool(description=_TOOL_SPECS[7]["description"])
    async def get_recovery_inbox() -> dict[str, Any]:
        return await readonly_bridge.get_recovery_inbox()

    @server.tool(description=_TOOL_SPECS[8]["description"])
    async def list_notifications(limit: int = 50) -> list[dict[str, Any]]:
        return await readonly_bridge.list_notifications(limit=limit)

    @server.tool(description=_TOOL_SPECS[9]["description"])
    async def get_notification_settings() -> dict[str, Any]:
        return await readonly_bridge.get_notification_settings()

    @server.tool(description=_TOOL_SPECS[10]["description"])
    async def list_store_bindings() -> list[dict[str, Any]]:
        return await readonly_bridge.list_store_bindings()

    @server.tool(description=_TOOL_SPECS[11]["description"])
    async def get_store_onboarding_cockpit() -> dict[str, Any]:
        return await readonly_bridge.get_store_onboarding_cockpit()

    @server.tool(description=_TOOL_SPECS[12]["description"])
    async def get_builder_client_config(client: str) -> dict[str, Any]:
        return await readonly_bridge.get_builder_client_config(client=client)

    @server.tool(description=_TOOL_SPECS[13]["description"])
    async def list_builder_client_configs() -> dict[str, Any]:
        return await readonly_bridge.list_builder_client_configs()

    return server


def list_tool_specs() -> list[dict[str, Any]]:
    return [dict(item) for item in _TOOL_SPECS]


def list_client_starter_specs() -> list[dict[str, Any]]:
    return [dict(item) for item in _CLIENT_STARTER_SPECS]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DealWatch read-only MCP server")
    subcommands = parser.add_subparsers(dest="command", required=True)

    list_tools_parser = subcommands.add_parser("list-tools", help="Print the registered DealWatch MCP tools.")
    list_tools_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a plain-text list.")

    client_starters_parser = subcommands.add_parser(
        "client-starters",
        help="Print repo-owned DealWatch starter metadata for local MCP/API clients.",
    )
    client_starters_parser.add_argument(
        "--client",
        choices=tuple(item["client"] for item in _CLIENT_STARTER_SPECS),
        help="Filter to one named client starter.",
    )
    client_starters_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a plain-text list.")

    client_config_parser = subcommands.add_parser(
        "client-config",
        help="Print one repo-owned DealWatch client config export.",
    )
    client_config_target = client_config_parser.add_mutually_exclusive_group(required=True)
    client_config_target.add_argument(
        "--client",
        choices=tuple(list_client_ids()),
        help="Named client config export to print.",
    )
    client_config_target.add_argument(
        "--all",
        action="store_true",
        help="Emit the repo-owned config export bundle for every supported client.",
    )
    client_config_parser.add_argument("--json", action="store_true", help="Emit JSON instead of the raw config body.")

    serve_parser = subcommands.add_parser("serve", help="Run the DealWatch MCP server.")
    serve_parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to use.",
    )
    return parser


async def _list_tools_payload() -> list[dict[str, Any]]:
    return list_tool_specs()


def _builder_client_config_payload(client: str) -> dict[str, Any]:
    return build_builder_client_config_payload(client)


def _builder_client_configs_payload() -> dict[str, Any]:
    return build_builder_client_configs_payload()


def _select_client_starters(client: str | None) -> list[dict[str, Any]]:
    starters = list_client_starter_specs()
    if client is None:
        return starters
    return [item for item in starters if item["client"] == client]


def _print_client_starters(starters: list[dict[str, Any]]) -> None:
    for item in starters:
        flow = " -> ".join(item["safe_first_flow"])
        print(f"{item['display_name']} ({item['client']})")
        print(f"  prompt_path: {item['prompt_path']}")
        print(f"  skill_path: {item['skill_path']}")
        print(f"  recipe_path: {item['recipe_path']}")
        print(f"  config_wrapper_status: {item['config_wrapper_status']}")
        print(f"  wrapper_example_kind: {item['wrapper_example_kind']}")
        print(f"  wrapper_surface: {item['wrapper_surface']}")
        print(f"  wrapper_source_url: {item['wrapper_source_url']}")
        print(f"  wrapper_example_path: {item['wrapper_example_path']}")
        print(f"  recommended_transport: {item['recommended_transport']}")
        print(f"  launch_command: {item['launch_command']}")
        print(f"  safe_first_flow: {flow}")
        print(f"  plugin_status: {item['plugin_status']}")
        print("  boundary_reminders:")
        for reminder in item["boundary_reminders"]:
            print(f"    - {reminder}")
        print("")


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "list-tools":
        payload = asyncio.run(_list_tools_payload())
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for item in payload:
                print(f"{item['name']}: {item['description']}")
        return 0

    if args.command == "client-starters":
        payload = _select_client_starters(args.client)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            _print_client_starters(payload)
        return 0

    if args.command == "client-config":
        payload = _builder_client_configs_payload() if args.all else _builder_client_config_payload(args.client)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            if args.all:
                print("DealWatch builder client config bundle")
                print(f"client_count: {payload['client_count']}")
                print(f"cli: {payload['read_surfaces']['cli']}")
                print(f"http: {payload['read_surfaces']['http']}")
                print(f"mcp_tool: {payload['read_surfaces']['mcp_tool']}")
            else:
                print(payload["wrapper_example_content"], end="")
                if not payload["wrapper_example_content"].endswith("\n"):
                    print("")
        return 0

    create_mcp_server().run(transport=args.transport)
    return 0
