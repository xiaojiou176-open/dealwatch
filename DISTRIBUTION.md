# Distribution

This file is the shortest truthful distribution ledger for DealWatch.

## Current repo-owned distribution reality

| Surface | Exact public receipt today | Repo state now | Honest public claim |
| --- | --- | --- | --- |
| GitHub repo | [`github.com/xiaojiou176-open/dealwatch`](https://github.com/xiaojiou176-open/dealwatch) | public canonical repo under `xiaojiou176-open/dealwatch` | live |
| GitHub Pages | [`xiaojiou176-open.github.io/dealwatch/`](https://xiaojiou176-open.github.io/dealwatch/) | homepage, compare preview, proof, FAQ, builders, comparison, community | live |
| GitHub release/tag | [`releases/latest`](https://github.com/xiaojiou176-open/dealwatch/releases/latest) | one canonical public release `v0.1.2` | live |
| Python package | [`pypi.org/project/dealwatch/`](https://pypi.org/project/dealwatch/) | `dealwatch==1.0.1` is published on PyPI and matches the current MCP package surface | live |
| Official MCP Registry | [`registry.modelcontextprotocol.io/v0.1/servers?search=dealwatch`](https://registry.modelcontextprotocol.io/v0.1/servers?search=dealwatch) | `io.github.xiaojiou176-open/dealwatch` is published and searchable | live |
| ClawHub skill | [`clawhub.ai/xiaojiou176/dealwatch-readonly-builder`](https://clawhub.ai/xiaojiou176/dealwatch-readonly-builder) | `dealwatch-readonly-builder` is published under the OpenClaw skill registry | live |
| Cline MCP Marketplace | submission receipt [`cline/mcp-marketplace#1325`](https://github.com/cline/mcp-marketplace/issues/1325) | repo-side reviewer cargo already landed on `main` via [`dealwatch#29`](https://github.com/xiaojiou176-open/dealwatch/pull/29); external intake is now waiting on maintainer review | review-pending |
| OpenHands/extensions | active public skill submission is PR [`OpenHands/extensions#151`](https://github.com/OpenHands/extensions/pull/151); PR [`#152`](https://github.com/OpenHands/extensions/pull/152) is the retired predecessor | active public skill submission is PR `#151`; `#152` is retired predecessor | submission_done_platform_not_accepted_yet (`#151` still carries maintainer-requested changes) |
| MCP.so submission | submission receipt [`chatmcp/mcpso#1558`](https://github.com/chatmcp/mcpso/issues/1558); guessed public page [`mcp.so/server/dealwatch`](https://mcp.so/server/dealwatch) still renders `Project not found` today | server intake issue `#1558` is filed, but there is still no public listing receipt | submission_done_platform_not_accepted_yet |
| Builder pack | repo-owned pack only | starter prompts, skill cards, config exports, native bundle candidates, and listing-prep copy are all repo-owned | repo-owned pack is live; official host truth is mixed by platform |
| Chrome companion extension | no public item URL tracked yet | `browser-extension/` package, icons, build script, listing notes | submit-ready for dashboard upload, **not published** |

## What still remains manual / external

- wait for maintainer review on `cline/mcp-marketplace#1325`; do not claim the Cline lane is listed live before a public marketplace read-back exists
- respond on the active OpenHands line `OpenHands/extensions#151` until the requested changes are accepted; do not send reviewers to `#152`
- wait for the public host listing to exist on `chatmcp/mcpso#1558`
- upload the Chrome companion extension package through the Chrome Web Store dashboard

## Read next

- [`README.md`](./README.md)
- [`INTEGRATIONS.md`](./INTEGRATIONS.md)
- [`docs/integrations/README.md`](./docs/integrations/README.md)
- [`browser-extension/README.md`](./browser-extension/README.md)
