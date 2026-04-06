from __future__ import annotations

import contextlib
import io
import sys

import pytest
from pydantic import SecretStr

from dealwatch import cli


def test_parse_bootstrap_args_accepts_token() -> None:
    args = cli._parse_bootstrap_args(["--email", "owner@example.com", "--token", "secret-token"])
    assert args.email == "owner@example.com"
    assert args.token == "secret-token"


def test_parse_legacy_args_accepts_store_and_zip() -> None:
    args = cli._parse_legacy_args(["--store", "weee", "--zip", "98004"])
    assert args.store == ["weee"]
    assert args.zip == "98004"


@pytest.mark.asyncio
async def test_bootstrap_owner_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr(cli.settings, "OWNER_BOOTSTRAP_TOKEN", SecretStr("expected-token"))
    with pytest.raises(RuntimeError, match="owner_bootstrap_token_invalid"):
        await cli._bootstrap_owner(["--email", "owner@example.com", "--token", "wrong-token"])


def test_cli_help_flag_prints_main_help(monkeypatch) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["python", "--help"])
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        cli.main()
    assert "Usage: python -m dealwatch <command> [...]." in stdout.getvalue()
    assert "Runtime commands:" in stdout.getvalue()
    assert "Builder discovery commands:" in stdout.getvalue()
    assert "Operator-only maintainer commands:" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_help_command_prints_main_help(monkeypatch) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["python", "help"])
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        cli.main()
    assert "Legacy bridge commands:" in stdout.getvalue()
    assert stderr.getvalue() == ""
