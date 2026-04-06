#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE = "https://api.github.com/repos/xiaojiou176/dealwatch"
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
EXPECTED_OWNER_LOGIN = "xiaojiou176"
EXPECTED_OWNER_TYPE = "User"
EXPECTED_HTML_URL = "https://github.com/xiaojiou176/dealwatch"
EXPECTED_DESCRIPTION = "Open-source compare-first grocery price tracking with compare-aware watch groups, effective price, health, and alert history."
EXPECTED_HOMEPAGE = "https://xiaojiou176.github.io/dealwatch/"
EXPECTED_TOPICS = {
    "apscheduler",
    "cashback",
    "deal-finder",
    "dealwatch",
    "fastapi",
    "grocery",
    "notifications",
    "playwright",
    "postgresql",
    "preact",
    "price-monitoring",
    "price-tracking",
}
EXPECTED_REQUIRED_CHECKS = {
    "governance",
    "test",
    "frontend",
    "product-smoke",
    "secret-hygiene",
    "CodeQL",
    "Dependency Review",
    "workflow-hygiene",
    "trivy",
}
EXPECTED_WORKFLOWS = {"CI", "CodeQL", "Pages", "Dependabot Updates", "Dependency Review", "Workflow Hygiene", "Trivy"}
EXPECTED_LABELS = {"store-request", "compare-preview", "public-surface", "release"}
EXPECTED_LATEST_RELEASE = "v0.1.2"
EXPECTED_PUBLIC_RELEASES = {"v0.1.2"}
EXPECTED_DISCUSSION_ENTRYPOINTS = {
    "https://github.com/xiaojiou176/dealwatch/discussions",
    "https://github.com/xiaojiou176/dealwatch/discussions/categories/announcements",
    "https://github.com/xiaojiou176/dealwatch/discussions/categories/q-a",
    "https://github.com/xiaojiou176/dealwatch/discussions/categories/show-and-tell",
}
EXPECTED_DISCUSSION_CATEGORY_SLUGS = {"announcements", "q-a", "show-and-tell"}
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


def build_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "dealwatch-remote-verifier",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return headers


def fetch_json(url: str) -> tuple[int, object]:
    request = Request(url, headers=build_headers())
    try:
        with urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        return exc.code, payload
    except URLError as exc:
        return 0, {"error": str(exc)}


def fetch_graphql(query: str) -> tuple[int, object]:
    payload = json.dumps({"query": query}).encode("utf-8")
    request = Request(GRAPHQL_ENDPOINT, headers=build_headers(), data=payload, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        return exc.code, payload
    except URLError as exc:
        return 0, {"error": str(exc)}


def main() -> int:
    auth_enabled = bool(TOKEN)
    repo_status, repo = fetch_json(BASE)
    branch_status, branch = fetch_json(f"{BASE}/branches/main")
    workflows_status, workflows = fetch_json(f"{BASE}/actions/workflows")
    labels_status, labels = fetch_json(f"{BASE}/labels?per_page=100")
    issues_status, issues = fetch_json(f"{BASE}/issues?state=open&per_page=100")
    pulls_status, pulls = fetch_json(f"{BASE}/pulls?state=open&per_page=100")
    releases_status, releases = fetch_json(f"{BASE}/releases?per_page=10")
    latest_release_status, latest_release = fetch_json(f"{BASE}/releases/latest")
    pvr_status, pvr = fetch_json(f"{BASE}/private-vulnerability-reporting")
    code_scanning_status, code_scanning = fetch_json(f"{BASE}/code-scanning/alerts?state=open&per_page=100")
    secret_scanning_status, secret_scanning = fetch_json(f"{BASE}/secret-scanning/alerts?state=open&per_page=100")
    dependabot_status, dependabot = fetch_json(f"{BASE}/dependabot/alerts?state=open&per_page=100")
    discussions_status = 0
    discussions_payload: object = {}
    if auth_enabled:
        discussions_status, discussions_payload = fetch_graphql(
            """
            query {
              repository(owner: "xiaojiou176", name: "dealwatch") {
                discussionCategories(first: 20) {
                  nodes {
                    slug
                  }
                }
              }
            }
            """
        )
    findings: list[str] = []
    manual_checks: list[str] = []

    print("DealWatch Remote GitHub State")
    print(f"authenticated={'yes' if auth_enabled else 'no'}")
    print(f"repo_status={repo_status}")
    print(f"branch_status={branch_status}")
    print(f"workflows_status={workflows_status}")
    print(f"labels_status={labels_status}")
    print(f"issues_status={issues_status}")
    print(f"pulls_status={pulls_status}")
    print(f"releases_status={releases_status}")
    print(f"latest_release_status={latest_release_status}")
    print(f"private_vulnerability_reporting_status={pvr_status}")
    print(f"code_scanning_status={code_scanning_status}")
    print(f"secret_scanning_status={secret_scanning_status}")
    print(f"dependabot_status={dependabot_status}")
    if auth_enabled:
        print(f"discussions_graphql_status={discussions_status}")
    print("")

    if repo_status == 200 and isinstance(repo, dict):
        print(f"visibility={repo.get('visibility')}")
        print(f"default_branch={repo.get('default_branch')}")
        print(f"html_url={repo.get('html_url')}")
        print(f"description={repo.get('description')}")
        print(f"homepage={repo.get('homepage')}")
        print(f"has_discussions={repo.get('has_discussions')}")
        print(f"has_pages={repo.get('has_pages')}")
        owner = repo.get("owner") or {}
        print(f"owner_login={owner.get('login')}")
        print(f"owner_type={owner.get('type')}")
        if owner.get("login") != EXPECTED_OWNER_LOGIN:
            findings.append(f"owner.login must be {EXPECTED_OWNER_LOGIN}")
        if owner.get("type") != EXPECTED_OWNER_TYPE:
            findings.append(f"owner.type must be {EXPECTED_OWNER_TYPE}")
        if repo.get("html_url") != EXPECTED_HTML_URL:
            findings.append(f"html_url must be {EXPECTED_HTML_URL}")
        if repo.get("default_branch") != "main":
            findings.append("default_branch must be main")
        if repo.get("description") != EXPECTED_DESCRIPTION:
            findings.append("repository description drifted from the expected public narrative")
        if repo.get("homepage") != EXPECTED_HOMEPAGE:
            findings.append(f"homepage must be {EXPECTED_HOMEPAGE}")
        if repo.get("has_discussions") is not True:
            findings.append("discussions must be enabled")
        if repo.get("has_pages") is not True:
            findings.append("GitHub Pages must be enabled")
        topics = set(repo.get("topics") or [])
        missing_topics = sorted(EXPECTED_TOPICS.difference(topics))
        if missing_topics:
            findings.append(f"topics missing: {', '.join(missing_topics)}")
    elif repo_status in {401, 403} and not auth_enabled:
        manual_checks.append("repo metadata requires authenticated GitHub API access")
    else:
        findings.append("repo endpoint must return 200")

    if branch_status == 200 and isinstance(branch, dict):
        print(f"main_protected={branch.get('protected')}")
        protection = branch.get("protection") or {}
        checks = (protection.get("required_status_checks") or {}).get("contexts") or []
        print(f"required_status_checks={','.join(checks) if checks else '(none)'}")
        if branch.get("protected") is not True:
            findings.append("main must be protected")
        missing_checks = sorted(EXPECTED_REQUIRED_CHECKS.difference(checks))
        if missing_checks:
            findings.append(f"required status checks missing: {', '.join(missing_checks)}")
    elif branch_status in {401, 403} and not auth_enabled:
        manual_checks.append("branch protection requires authenticated GitHub API access")
    else:
        findings.append("branch endpoint must return 200")

    if workflows_status == 200 and isinstance(workflows, dict):
        names = [workflow.get("name", "") for workflow in workflows.get("workflows", [])]
        print(f"workflows={','.join(name for name in names if name)}")
        missing_workflows = sorted(EXPECTED_WORKFLOWS.difference(names))
        if missing_workflows:
            findings.append(f"workflow names missing: {', '.join(missing_workflows)}")
    elif workflows_status in {401, 403} and not auth_enabled:
        manual_checks.append("workflow visibility requires authenticated GitHub API access")
    else:
        findings.append("workflows endpoint must return 200")

    if labels_status == 200 and isinstance(labels, list):
        label_names = {item.get("name") for item in labels if isinstance(item, dict)}
        print(f"labels={','.join(sorted(name for name in label_names if name))}")
        missing_labels = sorted(EXPECTED_LABELS.difference(label_names))
        if missing_labels:
            findings.append(f"labels missing: {', '.join(missing_labels)}")
    elif labels_status in {401, 403} and not auth_enabled:
        manual_checks.append("labels require authenticated GitHub API access")
    else:
        findings.append("labels endpoint must return 200")

    if issues_status == 200 and isinstance(issues, list):
        issue_items = [
            item for item in issues if isinstance(item, dict) and not item.get("pull_request")
        ]
        issue_titles = {item.get("title") for item in issue_items if item.get("title")}
        print(f"open_issue_count={len(issue_items)}")
        print(f"open_issues={','.join(sorted(title for title in issue_titles if title))}")
    elif issues_status in {401, 403} and not auth_enabled:
        manual_checks.append("open issues require authenticated GitHub API access")
    else:
        findings.append("issues endpoint must return 200")

    if pulls_status == 200 and isinstance(pulls, list):
        pull_titles = {item.get("title") for item in pulls if isinstance(item, dict) and item.get("title")}
        print(f"open_pull_request_count={len(pulls)}")
        print(f"open_pull_requests={','.join(sorted(title for title in pull_titles if title))}")
    elif pulls_status in {401, 403} and not auth_enabled:
        manual_checks.append("open pull requests require authenticated GitHub API access")
    else:
        findings.append("pulls endpoint must return 200")

    if releases_status == 200 and isinstance(releases, list):
        release_names = [item.get("tag_name", "") for item in releases if isinstance(item, dict)]
        print(f"releases={','.join(name for name in release_names if name)}")
        current_release_set = {name for name in release_names if name}
        if current_release_set != EXPECTED_PUBLIC_RELEASES:
            findings.append(
                "public releases on the rebuilt canonical repo must be exactly: "
                + ", ".join(sorted(EXPECTED_PUBLIC_RELEASES))
            )
    elif releases_status in {401, 403} and not auth_enabled:
        manual_checks.append("release listing requires authenticated GitHub API access")
    else:
        findings.append("releases endpoint must return 200")

    if latest_release_status == 200 and isinstance(latest_release, dict):
        latest_tag = latest_release.get("tag_name") or ""
        print(f"latest_release={latest_tag}")
        if latest_tag != EXPECTED_LATEST_RELEASE:
            findings.append(f"latest release must be {EXPECTED_LATEST_RELEASE}")
    elif latest_release_status == 404:
        print("latest_release=(missing)")
        findings.append("latest release endpoint must return the expected latest release")
    else:
        print("latest_release=unknown")
        findings.append("latest release endpoint must return 200")

    if pvr_status == 200 and isinstance(pvr, dict):
        print(f"private_vulnerability_reporting_enabled={pvr.get('enabled')}")
        if pvr.get("enabled") is not True:
            findings.append("private vulnerability reporting must be enabled")
    elif pvr_status in {401, 403} and not auth_enabled:
        print("private_vulnerability_reporting_enabled=unknown")
        manual_checks.append("private vulnerability reporting requires authenticated GitHub API access")
    else:
        print("private_vulnerability_reporting_enabled=unknown")
        findings.append("private vulnerability reporting endpoint must return 200")

    if code_scanning_status == 200 and isinstance(code_scanning, list):
        print("code_scanning_alerts_api=available")
        print(f"code_scanning_alert_count={len(code_scanning)}")
        if code_scanning:
            findings.append("code scanning alerts must be zero")
    elif code_scanning_status in {401, 403}:
        print("code_scanning_alerts_api=requires_auth")
        manual_checks.append(
            "code scanning alert count needs authenticated GitHub API access or a manual GitHub UI review"
        )
    else:
        print("code_scanning_alerts_api=unknown")
        findings.append("code scanning alerts API must be available or require auth")

    if secret_scanning_status == 200 and isinstance(secret_scanning, list):
        print("secret_scanning_alerts_api=available")
        print(f"secret_scanning_alert_count={len(secret_scanning)}")
        if secret_scanning:
            findings.append("secret scanning alerts must be zero")
    elif secret_scanning_status in {401, 403}:
        print("secret_scanning_alerts_api=requires_auth")
        manual_checks.append(
            "secret scanning alert count needs authenticated GitHub API access or a manual GitHub UI review"
        )
    else:
        print("secret_scanning_alerts_api=unknown")
        findings.append("secret scanning alerts API must be available or require auth")

    if dependabot_status == 200 and isinstance(dependabot, list):
        print("dependabot_alerts_api=available")
        print(f"dependabot_alert_count={len(dependabot)}")
        if dependabot:
            findings.append("dependabot alerts must be zero")
    elif dependabot_status in {401, 403}:
        print("dependabot_alerts_api=requires_auth")
        manual_checks.append(
            "Dependabot alert count needs authenticated GitHub API access or a manual GitHub UI review"
        )
    else:
        print("dependabot_alerts_api=unknown")
        findings.append("Dependabot alerts API must be available or require auth")

    if auth_enabled:
        if discussions_status == 200 and isinstance(discussions_payload, dict):
            repo = ((discussions_payload.get("data") or {}).get("repository") or {})
            nodes = ((repo.get("discussionCategories") or {}).get("nodes") or [])
            discussion_category_slugs = {
                item.get("slug", "")
                for item in nodes
                if isinstance(item, dict) and item.get("slug")
            }
            print(
                "discussion_categories="
                + ",".join(sorted(slug for slug in discussion_category_slugs if slug))
            )
            missing_discussion_categories = sorted(
                EXPECTED_DISCUSSION_CATEGORY_SLUGS.difference(discussion_category_slugs)
            )
            if missing_discussion_categories:
                findings.append(
                    "expected public discussion categories missing: "
                    + ", ".join(missing_discussion_categories)
                )
        else:
            findings.append("discussion GraphQL endpoint must return 200 with authenticated access")
    else:
        manual_checks.append("discussion category inventory needs authenticated GraphQL access")

    if findings:
        print("")
        print("Remote GitHub verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    if manual_checks:
        print("")
        print("Manual verification still required:")
        for item in manual_checks:
            print(f" - {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
