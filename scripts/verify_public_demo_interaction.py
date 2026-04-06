#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import shutil
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ASSETS = ROOT / "assets"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError as exc:
    if sys.executable != str(VENV_PYTHON) and VENV_PYTHON.exists():
        completed = subprocess.run([str(VENV_PYTHON), __file__], cwd=ROOT)
        raise SystemExit(completed.returncode)
    raise SystemExit(f"playwright import failed: {exc}")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    findings: list[str] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(SITE, temp_path, dirs_exist_ok=True)
        shutil.copytree(ASSETS, temp_path / "assets", dirs_exist_ok=True)

        previous = Path.cwd()
        os.chdir(temp_path)
        server = ThreadingHTTPServer(("127.0.0.1", 4191), QuietHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.goto(
                    "http://127.0.0.1:4191/compare-preview.html#sample-compare-demo",
                    wait_until="networkidle",
                )
                page.click("#load-sample-compare")
                page.wait_for_selector("text=Resolved comparisons")

                status_text = page.locator("#sample-status").inner_text()
                item_count = page.locator("#sample-results .demo-item").count()
                h1_text = page.locator("h1").first.inner_text()

                if "No data is saved" not in status_text:
                    findings.append("sample status does not keep the read-only / no-data-saved boundary")
                if item_count < 3:
                    findings.append("sample compare demo did not render the expected result cards")
                if "Check the product target before you create durable state." not in h1_text:
                    findings.append("compare preview page h1 drifted while validating the sample demo")

                browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            os.chdir(previous)

    if findings:
        print("Public demo interaction verification failed:")
        for finding in findings:
            print(f" - {finding}")
        return 1

    print("Public demo interaction verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
