from __future__ import annotations

import json
import os
import socket
import socketserver
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "launch_dealwatch_chrome.sh"


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def _reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_env(env_file: Path, *, root: Path, profile_directory: str = "Profile 21", port: int = 9333) -> None:
    env_file.write_text(
        "\n".join(
            [
                f'CHROME_USER_DATA_DIR="{root}"',
                "CHROME_PROFILE_NAME=dealwatch",
                f"CHROME_PROFILE_DIRECTORY={profile_directory}",
                f"CHROME_REMOTE_DEBUG_PORT={port}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_ps_stub(path: Path, output: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\ncat <<'EOF'\n{output}\nEOF\n", encoding="utf-8")
    path.chmod(0o755)


def _browser_ps_lines(*, count: int, prefix: Path) -> str:
    lines = []
    for index in range(count):
        lines.append(
            "Google "
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
            f"--user-data-dir={prefix / f'other-{index}'} "
            f"--profile-directory=Profile {index}"
        )
    return "\n".join(lines)


def _wait_for_listener(port: int, *, retries: int = 20) -> None:
    for _ in range(retries):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.05)
    raise AssertionError(f"listener on port {port} did not become ready")


def _build_cdp_handler(*, port: int):
    state = {"targets": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/json/version":
                payload = {
                    "Browser": "Chrome/146.0.7680.178",
                    "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/browser/test",
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
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

    return Handler, state


def test_launch_script_rejects_missing_contract(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CHROME_USER_DATA_DIR=\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={**os.environ, "DEALWATCH_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must all be configured" in result.stderr


def test_launch_script_rejects_legacy_shared_root(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'CHROME_USER_DATA_DIR="<default-macos-chrome-user-data-root>"',
                "CHROME_PROFILE_NAME=dealwatch",
                "CHROME_PROFILE_DIRECTORY=Profile 21",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={**os.environ, "DEALWATCH_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "must not point at the legacy shared Chrome root" in result.stderr


def test_launch_script_reuses_existing_instance(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    port = _reserve_local_port()
    _write_env(env_file, root=target_root, port=port)
    ps_stub = tmp_path / "ps"
    _write_ps_stub(
        ps_stub,
        f"Google /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir={target_root} --profile-directory=Profile 21",
    )

    Handler, _state = _build_cdp_handler(port=port)

    with ReusableTCPServer(("127.0.0.1", port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _wait_for_listener(port)
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT)],
                env={
                    **os.environ,
                    "DEALWATCH_ENV_FILE": str(env_file),
                    "DEALWATCH_PS_BIN": str(ps_stub),
                },
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0
    assert "reusing existing dedicated Chrome instance" in result.stdout
    assert "identity_page_path=" in result.stdout
    assert "target=Browser identity" in result.stdout


def test_launch_script_rejects_matching_process_without_listener(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    _write_env(env_file, root=target_root, port=19446)
    ps_stub = tmp_path / "ps"
    _write_ps_stub(
        ps_stub,
        f"1234 Google /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir={target_root} --profile-directory=Profile 21",
    )

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "DEALWATCH_ENV_FILE": str(env_file),
            "DEALWATCH_PS_BIN": str(ps_stub),
            "DEALWATCH_READY_RETRIES": "1",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "CDP listener 19446 is not reachable" in result.stderr


def test_launch_script_fails_when_listener_never_appears(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    _write_env(env_file, root=target_root, port=19444)
    ps_stub = tmp_path / "ps"
    _write_ps_stub(ps_stub, "")

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "DEALWATCH_ENV_FILE": str(env_file),
            "DEALWATCH_PS_BIN": str(ps_stub),
            "DEALWATCH_OPEN_BIN": "/usr/bin/true",
            "DEALWATCH_READY_RETRIES": "1",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "did not expose a CDP listener" in result.stderr


def test_launch_script_rejects_new_launch_when_browser_limit_is_exceeded(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    _write_env(env_file, root=target_root, port=19445)
    ps_stub = tmp_path / "ps"
    _write_ps_stub(ps_stub, _browser_ps_lines(count=7, prefix=tmp_path / "browser-fleet"))

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "DEALWATCH_ENV_FILE": str(env_file),
            "DEALWATCH_PS_BIN": str(ps_stub),
            "DEALWATCH_OPEN_BIN": "/usr/bin/true",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "above DealWatch limit 6" in result.stderr


def test_launch_script_succeeds_when_listener_is_already_ready(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    target_root = tmp_path / "chrome-user-data"
    target_root.mkdir(parents=True)
    port = _reserve_local_port()
    _write_env(env_file, root=target_root, port=port)
    ps_stub = tmp_path / "ps"
    _write_ps_stub(ps_stub, "")

    Handler, _state = _build_cdp_handler(port=port)

    with ReusableTCPServer(("127.0.0.1", port), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _wait_for_listener(port)
        try:
            result = subprocess.run(
                ["bash", str(SCRIPT)],
                env={
                    **os.environ,
                    "DEALWATCH_ENV_FILE": str(env_file),
                    "DEALWATCH_PS_BIN": str(ps_stub),
                    "DEALWATCH_OPEN_BIN": "/usr/bin/true",
                    "DEALWATCH_READY_RETRIES": "2",
                },
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0
    assert "launched dedicated Chrome instance" in result.stdout
    assert "identity_page_path=" in result.stdout
    assert "target=Target account" in result.stdout
