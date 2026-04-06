from __future__ import annotations

from pathlib import Path

import scripts.verify_builder_public_boundary as verify_script


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_builder_public_boundary_main_passes_for_honest_surface(monkeypatch, tmp_path: Path, capsys) -> None:
    readme = tmp_path / "README.md"
    integrations = tmp_path / "docs" / "integrations" / "README.md"
    config_recipes = tmp_path / "docs" / "integrations" / "config-recipes.md"
    prompt_starters = tmp_path / "docs" / "integrations" / "prompt-starters.md"
    examples_readme = tmp_path / "docs" / "integrations" / "examples" / "README.md"
    builders = tmp_path / "site" / "builders.html"
    llms = tmp_path / "site" / "llms.txt"

    _write(readme, "DealWatch is not a hosted multi-tenant builder platform today.\nThe current repo does **not** ship a formal SDK.\n")
    _write(integrations, "This is not a hosted multi-tenant control plane guide.\nThis is not a write-side automation guide.\n")
    _write(config_recipes, "These recipes do not mean:\n- DealWatch now ships a published marketplace listing\n- write-side MCP is ready\n")
    _write(prompt_starters, "- deferred: write-side MCP, hosted auth, SDK packaging, multi-tenant control plane\n")
    _write(examples_readme, "They are **not**:\n- frozen SDK schemas\n- hosted API guarantees\n")
    _write(builders, "Bundle candidates only.\nNo hosted control plane.\nNo write-side MCP promise.\nNo official listing.\n")
    _write(llms, "Not a hosted SaaS.\nNot a hosted plugin runtime for Claude Code or Codex.\n")

    monkeypatch.setattr(
        verify_script,
        "TARGET_GLOBS",
        (
            "README.md",
            "docs/integrations/README.md",
            "docs/integrations/config-recipes.md",
            "docs/integrations/prompt-starters.md",
            "docs/integrations/examples/README.md",
            "site/builders.html",
            "site/llms.txt",
        ),
    )
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 0
    captured = capsys.readouterr()
    assert "Builder public boundary verification passed." in captured.out


def test_builder_public_boundary_collects_positive_overclaim(monkeypatch, tmp_path: Path, capsys) -> None:
    readme = tmp_path / "README.md"
    integrations = tmp_path / "docs" / "integrations" / "README.md"
    config_recipes = tmp_path / "docs" / "integrations" / "config-recipes.md"
    prompt_starters = tmp_path / "docs" / "integrations" / "prompt-starters.md"
    examples_readme = tmp_path / "docs" / "integrations" / "examples" / "README.md"
    builders = tmp_path / "site" / "builders.html"
    llms = tmp_path / "site" / "llms.txt"

    _write(readme, "DealWatch is the hosted platform for Codex agents.\n")
    _write(integrations, "This is not a hosted multi-tenant control plane guide.\nThis is not a write-side automation guide.\n")
    _write(config_recipes, "These recipes do not mean:\n- DealWatch now ships a published marketplace listing\n")
    _write(prompt_starters, "- deferred: write-side MCP, hosted auth, SDK packaging, multi-tenant control plane\n")
    _write(examples_readme, "They are **not**:\n- frozen SDK schemas\n")
    _write(builders, "Bundle candidates only.\nNo hosted control plane.\nNo write-side MCP promise.\nNo official listing.\n")
    _write(llms, "Not a hosted SaaS.\nNot a hosted plugin runtime for Claude Code or Codex.\n")

    monkeypatch.setattr(
        verify_script,
        "TARGET_GLOBS",
        (
            "README.md",
            "docs/integrations/README.md",
            "docs/integrations/config-recipes.md",
            "docs/integrations/prompt-starters.md",
            "docs/integrations/examples/README.md",
            "site/builders.html",
            "site/llms.txt",
        ),
    )
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 1
    captured = capsys.readouterr()
    assert "contains builder public overclaim pattern" in captured.out


def test_builder_public_boundary_allows_negative_context(monkeypatch, tmp_path: Path, capsys) -> None:
    readme = tmp_path / "README.md"
    integrations = tmp_path / "docs" / "integrations" / "README.md"
    config_recipes = tmp_path / "docs" / "integrations" / "config-recipes.md"
    prompt_starters = tmp_path / "docs" / "integrations" / "prompt-starters.md"
    examples_readme = tmp_path / "docs" / "integrations" / "examples" / "README.md"
    builders = tmp_path / "site" / "builders.html"
    llms = tmp_path / "site" / "llms.txt"

    _write(
        readme,
        "DealWatch is not a hosted multi-tenant builder platform today.\n"
        "The current repo does **not** ship a formal SDK.\n"
        "Do not present DealWatch as an official plugin marketplace surface.\n",
    )
    _write(integrations, "This is not a hosted multi-tenant control plane guide.\nThis is not a write-side automation guide.\n")
    _write(config_recipes, "These recipes do not mean:\n- DealWatch now ships a published marketplace listing\n- write-side MCP is ready\n")
    _write(prompt_starters, "- deferred: write-side MCP, hosted auth, SDK packaging, multi-tenant control plane\n")
    _write(examples_readme, "They are **not**:\n- frozen SDK schemas\n- hosted API guarantees\n")
    _write(builders, "Bundle candidates only.\nNo hosted control plane.\nNo write-side MCP promise.\nNo official listing.\n")
    _write(llms, "Not a hosted SaaS.\nNot a hosted plugin runtime for Claude Code or Codex.\n")

    monkeypatch.setattr(
        verify_script,
        "TARGET_GLOBS",
        (
            "README.md",
            "docs/integrations/README.md",
            "docs/integrations/config-recipes.md",
            "docs/integrations/prompt-starters.md",
            "docs/integrations/examples/README.md",
            "site/builders.html",
            "site/llms.txt",
        ),
    )
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 0
    captured = capsys.readouterr()
    assert "passed" in captured.out


def test_builder_public_boundary_allows_bullet_after_negative_heading(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    readme = tmp_path / "README.md"
    integrations = tmp_path / "docs" / "integrations" / "README.md"
    config_recipes = tmp_path / "docs" / "integrations" / "config-recipes.md"
    prompt_starters = tmp_path / "docs" / "integrations" / "prompt-starters.md"
    examples_readme = tmp_path / "docs" / "integrations" / "examples" / "README.md"
    builders = tmp_path / "site" / "builders.html"
    llms = tmp_path / "site" / "llms.txt"

    _write(
        readme,
        "DealWatch is not a hosted multi-tenant builder platform today.\n"
        "The current repo does **not** ship a formal SDK.\n",
    )
    _write(
        integrations,
        "Codex should not treat DealWatch as:\n"
        "- a hosted platform\n"
        "- a packaged SDK\n"
        "This is not a write-side automation guide.\n"
        "This is not a hosted multi-tenant control plane guide.\n",
    )
    _write(config_recipes, "These recipes do not mean:\n- DealWatch now ships a published marketplace listing\n- write-side MCP is ready\n")
    _write(prompt_starters, "- deferred: write-side MCP, hosted auth, SDK packaging, multi-tenant control plane\n")
    _write(examples_readme, "They are **not**:\n- frozen SDK schemas\n- hosted API guarantees\n")
    _write(builders, "Bundle candidates only.\nNo hosted control plane.\nNo write-side MCP promise.\nNo official listing.\n")
    _write(llms, "Not a hosted SaaS.\nNot a hosted plugin runtime for Claude Code or Codex.\n")

    monkeypatch.setattr(
        verify_script,
        "TARGET_GLOBS",
        (
            "README.md",
            "docs/integrations/README.md",
            "docs/integrations/config-recipes.md",
            "docs/integrations/prompt-starters.md",
            "docs/integrations/examples/README.md",
            "site/builders.html",
            "site/llms.txt",
        ),
    )
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 0
    captured = capsys.readouterr()
    assert "passed" in captured.out


def test_builder_public_boundary_collects_overclaim_from_added_frontdoor_file(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    readme = tmp_path / "README.md"
    integrations = tmp_path / "docs" / "integrations" / "README.md"
    config_recipes = tmp_path / "docs" / "integrations" / "config-recipes.md"
    prompt_starters = tmp_path / "docs" / "integrations" / "prompt-starters.md"
    examples_readme = tmp_path / "docs" / "integrations" / "examples" / "README.md"
    builders = tmp_path / "site" / "builders.html"
    llms = tmp_path / "site" / "llms.txt"

    _write(readme, "DealWatch is not a hosted multi-tenant builder platform today.\nThe current repo does **not** ship a formal SDK.\n")
    _write(integrations, "This is not a hosted multi-tenant control plane guide.\nThis is not a write-side automation guide.\n")
    _write(config_recipes, "These recipes do not mean:\n- DealWatch now ships a published marketplace listing\n")
    _write(prompt_starters, "DealWatch runs on Codex.\n")
    _write(examples_readme, "They are **not**:\n- frozen SDK schemas\n")
    _write(builders, "Bundle candidates only.\nNo hosted control plane.\nNo write-side MCP promise.\nNo official listing.\n")
    _write(llms, "Not a hosted SaaS.\nNot a hosted plugin runtime for Claude Code or Codex.\n")

    monkeypatch.setattr(
        verify_script,
        "TARGET_GLOBS",
        (
            "README.md",
            "docs/integrations/README.md",
            "docs/integrations/config-recipes.md",
            "docs/integrations/prompt-starters.md",
            "docs/integrations/examples/README.md",
            "site/builders.html",
            "site/llms.txt",
        ),
    )
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 1
    captured = capsys.readouterr()
    assert "prompt-starters.md:1 contains builder public overclaim pattern" in captured.out


def test_builder_public_boundary_fails_when_required_phrase_is_missing(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    readme = tmp_path / "README.md"
    integrations = tmp_path / "docs" / "integrations" / "README.md"
    config_recipes = tmp_path / "docs" / "integrations" / "config-recipes.md"
    prompt_starters = tmp_path / "docs" / "integrations" / "prompt-starters.md"
    examples_readme = tmp_path / "docs" / "integrations" / "examples" / "README.md"
    builders = tmp_path / "site" / "builders.html"
    llms = tmp_path / "site" / "llms.txt"

    _write(readme, "DealWatch is not a hosted multi-tenant builder platform today.\n")
    _write(integrations, "This is not a hosted multi-tenant control plane guide.\nThis is not a write-side automation guide.\n")
    _write(config_recipes, "These recipes do not mean:\n- DealWatch now ships a published marketplace listing\n")
    _write(prompt_starters, "- deferred: write-side MCP, hosted auth, SDK packaging, multi-tenant control plane\n")
    _write(examples_readme, "They are **not**:\n- frozen SDK schemas\n- hosted API guarantees\n")
    _write(builders, "<p>Bundle candidates only.</p><p>No hosted control plane.</p><p>No write-side MCP promise.</p><p>No official listing.</p>")
    _write(llms, "Not a hosted plugin runtime for Claude Code or Codex.\n")

    monkeypatch.setattr(
        verify_script,
        "TARGET_GLOBS",
        (
            "README.md",
            "docs/integrations/README.md",
            "docs/integrations/config-recipes.md",
            "docs/integrations/prompt-starters.md",
            "docs/integrations/examples/README.md",
            "site/builders.html",
            "site/llms.txt",
        ),
    )
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 1
    captured = capsys.readouterr()
    assert "site/llms.txt missing required boundary phrase: Not a hosted SaaS." in captured.out


def test_builder_public_boundary_rejects_official_listing_phrase_in_generated_mirror(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    mirror = tmp_path / "site" / "data" / "builder-client-starters.json"

    _write(
        mirror,
        '{"warning":"Repo-owned distribution candidate only.","clients":[{"plugin_status":"Officially listed on Codex Plugin Directory."}]}',
    )

    monkeypatch.setattr(verify_script, "TARGET_GLOBS", ("site/data/builder-*.json",))
    monkeypatch.setattr(verify_script, "ROOT", tmp_path)

    assert verify_script.main() == 1
    captured = capsys.readouterr()
    assert "contains builder public overclaim pattern" in captured.out
