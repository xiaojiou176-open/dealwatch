from __future__ import annotations

import json
import os
import socket
import socketserver
import subprocess
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "open_dealwatch_account_pages.py"


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def _reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_env(env_file: Path, *, root: Path, port: int) -> None:
    env_file.write_text(
        "\n".join(
            [
                f'CHROME_USER_DATA_DIR="{root}"',
                "CHROME_PROFILE_NAME=dealwatch",
                "CHROME_PROFILE_DIRECTORY=Profile 21",
                f"CHROME_CDP_URL=http://127.0.0.1:{port}",
                f"CHROME_REMOTE_DEBUG_PORT={port}",
                "DEALWATCH_BROWSER_IDENTITY_LABEL=DealWatch Lane",
                "DEALWATCH_BROWSER_IDENTITY_ACCENT=#2563eb",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_open_dealwatch_account_pages_writes_identity_and_creates_targets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    port = _reserve_local_port()
    _write_env(env_file, root=target_root, port=port)

    state = {"targets": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/json/list":
                body = json.dumps(state["targets"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def do_PUT(self):  # noqa: N802
            if self.path.startswith("/json/new?"):
                url = unquote(self.path.split("?", 1)[1])
                state["targets"].append({"type": "page", "url": url})
                body = json.dumps({"url": url}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    with ReusableTCPServer(("127.0.0.1", port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--env-file",
                    str(env_file),
                    "--repo-root",
                    str(tmp_path),
                    "--json",
                ],
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["identity_label"] == "DealWatch Lane"
    assert payload["identity_accent"] == "#2563eb"
    assert payload["identity_page_path"].endswith(".runtime-cache/browser-identity/index.html")
    assert payload["identity_page_url"].startswith("file://")
    actions = {item["key"]: item["action"] for item in payload["targets"]}
    assert actions["identity"] == "created"
    assert actions["target"] == "created"
    assert actions["safeway"] == "created"
    assert actions["walmart"] == "created"
    assert actions["weee"] == "created"


def test_open_dealwatch_account_pages_reuses_safeway_sign_in_gate_when_no_account_tab_exists(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    port = _reserve_local_port()
    _write_env(env_file, root=target_root, port=port)

    state = {
        "targets": [
            {
                "id": "existing-safeway-signin",
                "type": "page",
                "url": "https://www.safeway.com/account/sign-in.html",
            }
        ]
    }
    created_count = {"value": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/json/list":
                body = json.dumps(state["targets"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def do_PUT(self):  # noqa: N802
            if self.path.startswith("/json/new?"):
                url = unquote(self.path.split("?", 1)[1])
                created_count["value"] += 1
                state["targets"].append(
                    {
                        "id": f"created-{created_count['value']}",
                        "type": "page",
                        "url": url,
                    }
                )
                body = json.dumps({"id": f"created-{created_count['value']}", "url": url}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    with ReusableTCPServer(("127.0.0.1", port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--env-file",
                    str(env_file),
                    "--repo-root",
                    str(tmp_path),
                    "--json",
                ],
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    safeway = next(item for item in payload["targets"] if item["key"] == "safeway")
    assert safeway["action"] == "reused"
    assert safeway["matched_url"] == "https://www.safeway.com/account/sign-in.html"


def test_open_dealwatch_account_pages_prefers_safeway_account_target_over_sign_in_gate(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    port = _reserve_local_port()
    _write_env(env_file, root=target_root, port=port)

    state = {
        "targets": [
            {
                "id": "existing-safeway-signin",
                "type": "page",
                "url": "https://www.safeway.com/account/sign-in.html",
            },
            {
                "id": "existing-safeway-account",
                "type": "page",
                "url": "https://www.safeway.com/customer-account/account-dashboard",
            },
        ]
    }
    safeway_create_attempts = {"value": 0}
    created_count = {"value": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/json/list":
                body = json.dumps(state["targets"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def do_PUT(self):  # noqa: N802
            if self.path.startswith("/json/new?"):
                url = unquote(self.path.split("?", 1)[1])
                if "safeway.com/customer-account/account-dashboard" in url:
                    safeway_create_attempts["value"] += 1
                created_count["value"] += 1
                state["targets"].append(
                    {
                        "id": f"created-{created_count['value']}",
                        "type": "page",
                        "url": url,
                    }
                )
                body = json.dumps({"id": f"created-{created_count['value']}", "url": url}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A003
            return

    with ReusableTCPServer(("127.0.0.1", port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--env-file",
                    str(env_file),
                    "--repo-root",
                    str(tmp_path),
                    "--json",
                ],
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    safeway = next(item for item in payload["targets"] if item["key"] == "safeway")
    assert safeway["action"] == "reused"
    assert safeway["matched_url"] == "https://www.safeway.com/customer-account/account-dashboard"
    assert safeway_create_attempts["value"] == 0


def test_open_dealwatch_account_pages_rejects_legacy_shared_root(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'CHROME_USER_DATA_DIR="<default-macos-chrome-user-data-root>"',
                "CHROME_PROFILE_NAME=dealwatch",
                "CHROME_PROFILE_DIRECTORY=Profile 21",
                "CHROME_CDP_URL=http://127.0.0.1:9333",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--env-file",
            str(env_file),
            "--repo-root",
            str(tmp_path),
            "--write-only",
        ],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must not point at the legacy shared Chrome root" in result.stderr
