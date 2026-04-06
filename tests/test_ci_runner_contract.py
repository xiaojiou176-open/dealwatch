from __future__ import annotations

from pathlib import Path

import scripts.verify_ci_runner_contract as verify_script


def test_verify_ci_runner_contract_rejects_self_hosted(monkeypatch, tmp_path: Path, capsys) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "ci.yml").write_text("jobs:\n  test:\n    runs-on: self-hosted\n", encoding="utf-8")

    monkeypatch.setattr(verify_script, "ROOT", tmp_path)
    monkeypatch.setattr(verify_script, "WORKFLOWS_DIR", workflows)

    assert verify_script.main() == 1
    assert "self-hosted" in capsys.readouterr().out


def test_verify_ci_runner_contract_accepts_hosted_runner(monkeypatch, tmp_path: Path, capsys) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "ci.yml").write_text("jobs:\n  test:\n    runs-on: ubuntu-latest\n", encoding="utf-8")

    monkeypatch.setattr(verify_script, "ROOT", tmp_path)
    monkeypatch.setattr(verify_script, "WORKFLOWS_DIR", workflows)

    assert verify_script.main() == 0
    assert "passed" in capsys.readouterr().out
