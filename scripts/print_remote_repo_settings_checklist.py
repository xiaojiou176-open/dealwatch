#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from verify_remote_github_state import (
    BASE,
    EXPECTED_DESCRIPTION,
    EXPECTED_DISCUSSION_ENTRYPOINTS,
    EXPECTED_HOMEPAGE,
    EXPECTED_LABELS,
    EXPECTED_LATEST_RELEASE,
    EXPECTED_REQUIRED_CHECKS,
    EXPECTED_TOPICS,
    EXPECTED_WORKFLOWS,
    TOKEN,
    fetch_graphql,
    fetch_json,
)


ROOT = Path(__file__).resolve().parents[1]
SOCIAL_PREVIEW = ROOT / "assets" / "social" / "social-preview-1280x640.png"
SOCIAL_PREVIEW_RELATIVE = SOCIAL_PREVIEW.relative_to(ROOT)


def format_csv(values: set[str]) -> str:
    return ", ".join(sorted(values)) if values else "(none)"


def format_status(ok: bool) -> str:
    return "ok" if ok else "drift"


def main() -> int:
    repo_status, repo = fetch_json(BASE)
    branch_status, branch = fetch_json(f"{BASE}/branches/main")
    workflows_status, workflows = fetch_json(f"{BASE}/actions/workflows")
    labels_status, labels = fetch_json(f"{BASE}/labels?per_page=100")
    issues_status, issues = fetch_json(f"{BASE}/issues?state=open&per_page=100")
    pulls_status, pulls = fetch_json(f"{BASE}/pulls?state=open&per_page=100")
    latest_release_status, latest_release = fetch_json(f"{BASE}/releases/latest")
    code_scanning_status, code_scanning = fetch_json(f"{BASE}/code-scanning/alerts?state=open&per_page=100")
    secret_scanning_status, secret_scanning = fetch_json(f"{BASE}/secret-scanning/alerts?state=open&per_page=100")
    dependabot_status, dependabot = fetch_json(f"{BASE}/dependabot/alerts?state=open&per_page=100")
    discussions_status = 0
    discussions_payload: object = {}
    if TOKEN:
        discussions_status, discussions_payload = fetch_graphql(
            """
            query {
              repository(owner: "xiaojiou176", name: "dealwatch") {
                discussions(first: 20, orderBy: {field: UPDATED_AT, direction: DESC}) {
                  nodes {
                    url
                  }
                }
              }
            }
            """
        )

    print("DealWatch Remote Repository Settings Checklist")
    print("")
    print(f"authenticated={'yes' if bool(TOKEN) else 'no'}")
    print("")
    print("Expected contract (what the repo says should be true)")
    print("")
    print("1. About section")
    print(f"   - Description: {EXPECTED_DESCRIPTION}")
    print(f"   - Homepage: {EXPECTED_HOMEPAGE}")
    print(f"   - Topics: {format_csv(EXPECTED_TOPICS)}")
    print("")
    print("2. Features")
    print("   - Discussions: enabled")
    print("   - GitHub Pages: enabled")
    print("   - Private vulnerability reporting: enabled")
    print("")
    print("3. Branch protection contract")
    print("   - Default branch: main")
    print(f"   - Required checks: {format_csv(EXPECTED_REQUIRED_CHECKS)}")
    print(f"   - Expected workflows: {format_csv(EXPECTED_WORKFLOWS)}")
    print(f"   - Expected labels: {format_csv(EXPECTED_LABELS)}")
    print("")
    print("4. Public remote surface contract")
    print("   - README public entrypoints present: #start-here and #roadmap")
    print("   - Pages entrypoints present: Home, Proof, Community")
    print(f"   - Latest release object resolves to: {EXPECTED_LATEST_RELEASE}")
    print(f"   - Public release set on the rebuilt repo should now be: {EXPECTED_LATEST_RELEASE} only")
    print(f"   - Expected discussion entrypoints: {format_csv(EXPECTED_DISCUSSION_ENTRYPOINTS)}")
    print("   - Repo-side social preview asset file exists and should pass the asset verifier")
    print("")
    print("Current remote facts (what GitHub says right now)")
    print("")
    print("5. About section current")
    if repo_status == 200 and isinstance(repo, dict):
        current_topics = set(repo.get("topics") or [])
        repo_ok = (
            repo.get("description") == EXPECTED_DESCRIPTION
            and repo.get("homepage") == EXPECTED_HOMEPAGE
            and current_topics == EXPECTED_TOPICS
        )
        print(f"   - Status: {format_status(repo_ok)}")
        print(f"   - Description current: {repo.get('description')}")
        print(f"   - Homepage current: {repo.get('homepage')}")
        print(f"   - Topics current: {format_csv(current_topics)}")
    else:
        print(f"   - Status: unavailable (repo_status={repo_status})")
    print("")
    print("6. Branch protection current")
    if branch_status == 200 and isinstance(branch, dict):
        protection = branch.get("protection") or {}
        current_checks = set(((protection.get("required_status_checks") or {}).get("contexts") or []))
        branch_ok = branch.get("protected") is True and current_checks == EXPECTED_REQUIRED_CHECKS
        print(f"   - Status: {format_status(branch_ok)}")
        print(f"   - Main protected: {branch.get('protected')}")
        print(f"   - Required checks current: {format_csv(current_checks)}")
        print(f"   - Missing expected checks: {format_csv(EXPECTED_REQUIRED_CHECKS.difference(current_checks))}")
    else:
        print(f"   - Status: unavailable (branch_status={branch_status})")
    print("")
    print("7. Workflow, label, and issue surface current")
    if workflows_status == 200 and isinstance(workflows, dict):
        workflow_names = {
            item.get("name", "")
            for item in workflows.get("workflows", [])
            if isinstance(item, dict) and item.get("name")
        }
        print(f"   - Workflow status: {format_status(EXPECTED_WORKFLOWS.issubset(workflow_names))}")
        print(f"   - Workflows visible now: {format_csv(workflow_names)}")
    else:
        print(f"   - Workflow status: unavailable (workflows_status={workflows_status})")
    if labels_status == 200 and isinstance(labels, list):
        current_labels = {item.get("name", "") for item in labels if isinstance(item, dict) and item.get("name")}
        missing_labels = EXPECTED_LABELS.difference(current_labels)
        print(f"   - Label status: {format_status(not missing_labels)}")
        print(f"   - Labels current: {format_csv(current_labels)}")
        print(f"   - Missing expected labels: {format_csv(missing_labels)}")
    else:
        print(f"   - Label status: unavailable (labels_status={labels_status})")
    if issues_status == 200 and isinstance(issues, list):
        issue_items = [
            item for item in issues if isinstance(item, dict) and not item.get("pull_request")
        ]
        print(f"   - Open issue count: {len(issue_items)}")
    else:
        print(f"   - Open issue count: unavailable (issues_status={issues_status})")
    if pulls_status == 200 and isinstance(pulls, list):
        print(f"   - Open pull request count: {len(pulls)}")
    else:
        print(f"   - Open pull request count: unavailable (pulls_status={pulls_status})")
    if code_scanning_status == 200 and isinstance(code_scanning, list):
        print(f"   - Code scanning alert count: {len(code_scanning)}")
    elif code_scanning_status in {401, 403}:
        print("   - Code scanning alert count: requires authenticated GitHub API access")
    else:
        print(f"   - Code scanning alert count: unavailable (code_scanning_status={code_scanning_status})")
    if secret_scanning_status == 200 and isinstance(secret_scanning, list):
        print(f"   - Secret scanning alert count: {len(secret_scanning)}")
    elif secret_scanning_status in {401, 403}:
        print("   - Secret scanning alert count: requires authenticated GitHub API access")
    else:
        print(f"   - Secret scanning alert count: unavailable (secret_scanning_status={secret_scanning_status})")
    if dependabot_status == 200 and isinstance(dependabot, list):
        print(f"   - Dependabot alert count: {len(dependabot)}")
    elif dependabot_status in {401, 403}:
        print("   - Dependabot alert count: requires authenticated GitHub API access")
    else:
        print(f"   - Dependabot alert count: unavailable (dependabot_status={dependabot_status})")
    if latest_release_status == 200 and isinstance(latest_release, dict):
        current_latest = latest_release.get("tag_name") or ""
        print(f"   - Latest release status: {format_status(current_latest == EXPECTED_LATEST_RELEASE)}")
        print(f"   - Latest release current: {current_latest}")
    else:
        print(f"   - Latest release status: unavailable (latest_release_status={latest_release_status})")
    if TOKEN and discussions_status == 200 and isinstance(discussions_payload, dict):
        repo_payload = ((discussions_payload.get("data") or {}).get("repository") or {})
        nodes = ((repo_payload.get("discussions") or {}).get("nodes") or [])
        current_discussions = {
            item.get("url", "")
            for item in nodes
            if isinstance(item, dict) and item.get("url")
        }
        print("   - Discussion entrypoint status: manual-review")
        print(f"   - Stable entrypoints expected: {format_csv(EXPECTED_DISCUSSION_ENTRYPOINTS)}")
        print(f"   - Discussion threads current: {format_csv(current_discussions)}")
    elif TOKEN:
        print(f"   - Discussion entrypoint status: unavailable (discussions_status={discussions_status})")
    else:
        print("   - Discussion entrypoint status: requires authenticated GraphQL access")
    print("")
    print("Manual/admin-only GitHub UI checks")
    print("")
    print("8. Social preview selection")
    print(f"   - Upload or confirm asset in GitHub UI: {SOCIAL_PREVIEW_RELATIVE}")
    print("   - Expected qualities: PNG, 2:1 ratio, at least 1280x640, under 1 MB")
    print("   - Note: the repo can verify the asset file, but cannot prove GitHub is currently using it as the active social preview image")
    print("")
    print("9. Credentialed or admin review")
    print("   - If you export GITHUB_TOKEN, the remote verifier can confirm current code-scanning, secret-scanning, and Dependabot alert counts")
    print("   - Without credentials, GitHub security alert counts remain a blind spot and still need GitHub UI review")
    print("")
    print("10. Community surface")
    print("   - Confirm no stale open issues remain after repository closure")
    print("   - Review discussion content quality if the public updates/store-request/compare-story threads become stale")
    print("")
    print("11. Verification commands")
    print("   - python3 scripts/print_remote_repo_settings_checklist.py")
    print("   - python3 scripts/verify_remote_github_state.py")
    print("   - GITHUB_TOKEN=... python3 scripts/verify_remote_github_state.py")
    print("   - python3 scripts/verify_social_preview_asset.py")
    print("   - Note: expected contract, current remote facts, and manual-only checks stay separate so the checklist does not pretend ideals are already live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
