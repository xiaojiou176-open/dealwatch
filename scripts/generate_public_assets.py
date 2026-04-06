#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import tempfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
ASSETS_DIR = ROOT / "assets"
COMPARE_SCREEN = ASSETS_DIR / "screens" / "compare-preview.png"
TASK_DETAIL_SCREEN = ASSETS_DIR / "screens" / "task-detail-price-history.png"
NOTIFICATIONS_SCREEN = ASSETS_DIR / "screens" / "notification-settings.png"
HERO_SCREEN = ASSETS_DIR / "hero" / "dealwatch-control-cabin.png"
SOCIAL_SCREEN = ASSETS_DIR / "social" / "social-preview-1280x640.png"
OG_HOME = ASSETS_DIR / "social" / "og-home.png"
OG_COMPARE = ASSETS_DIR / "social" / "og-compare-preview.png"
OG_PROOF = ASSETS_DIR / "social" / "og-proof.png"
OG_QUICK_START = ASSETS_DIR / "social" / "og-quick-start.png"
OG_FAQ = ASSETS_DIR / "social" / "og-faq.png"
OG_COMPARISON = ASSETS_DIR / "social" / "og-comparison.png"
COMPARE_GIF = ASSETS_DIR / "demo" / "compare-preview.gif"

SAMPLE_COMPARE_URLS = [
    "https://sayweee.com/p/pear-3ct",
    "https://99ranch.com/p/pear-3ct",
]


COMPARE_FIXTURE = {
    "submitted_count": 2,
    "resolved_count": 2,
    "comparisons": [
        {
            "submitted_url": "https://sayweee.com/p/pear-3ct",
            "supported": True,
            "store_key": "weee",
            "normalized_url": "https://sayweee.com/p/pear-3ct",
            "fetch_succeeded": True,
            "candidate_key": "pear-3ct",
            "offer": {
                "store_id": "weee",
                "product_key": "pear-3ct",
                "deal_id": "weee-pear-3ct",
                "title": "Asian Honey Pears 3ct",
                "url": "https://sayweee.com/p/pear-3ct",
                "price": 7.49,
                "original_price": 8.49,
                "fetch_at": "2026-03-25T08:20:00+00:00",
                "context": {"region": "98004", "currency": "USD", "is_member": False},
                "unit_price_info": {"raw": "$2.50 / each"},
            },
        },
        {
            "submitted_url": "https://99ranch.com/p/pear-3ct",
            "supported": True,
            "store_key": "ranch99",
            "normalized_url": "https://99ranch.com/p/pear-3ct",
            "fetch_succeeded": True,
            "candidate_key": "pear-3ct",
            "offer": {
                "store_id": "ranch99",
                "product_key": "pear-3ct",
                "deal_id": "ranch99-pear-3ct",
                "title": "Asian Honey Pears 3ct",
                "url": "https://99ranch.com/p/pear-3ct",
                "price": 6.99,
                "original_price": 7.49,
                "fetch_at": "2026-03-25T08:20:00+00:00",
                "context": {"region": "98004", "currency": "USD", "is_member": False},
                "unit_price_info": {"raw": "$2.33 / each"},
            },
        },
    ],
    "matches": [
        {
            "left_store_key": "weee",
            "left_product_key": "5869",
            "right_store_key": "ranch99",
            "right_product_key": "078895126389",
            "score": 96.4,
        }
    ],
}


WATCH_TASKS_FIXTURE = [
    {
        "id": "demo-task",
        "title": "Asian Honey Pears 3ct",
        "normalized_url": "https://sayweee.com/p/pear-3ct",
        "store_key": "weee",
        "status": "active",
        "cadence_minutes": 360,
        "next_run_at": "2026-03-25T18:00:00+00:00",
        "last_listed_price": 6.99,
        "last_effective_price": 6.59,
        "last_run_status": "succeeded",
    },
    {
        "id": "demo-task-ranch99",
        "title": "Asian Honey Pears 3ct",
        "normalized_url": "https://99ranch.com/p/pear-3ct",
        "store_key": "ranch99",
        "status": "active",
        "cadence_minutes": 480,
        "next_run_at": "2026-03-25T19:30:00+00:00",
        "last_listed_price": 7.49,
        "last_effective_price": 7.19,
        "last_run_status": "succeeded",
    },
]


TASK_DETAIL_FIXTURE = {
    "task": {
        "id": "demo-task",
        "title": "Asian Honey Pears 3ct",
        "status": "active",
        "normalized_url": "https://sayweee.com/p/pear-3ct",
        "submitted_url": "https://sayweee.com/p/pear-3ct",
        "store_key": "weee",
        "threshold_type": "effective_price_below",
        "threshold_value": 6.5,
        "cadence_minutes": 360,
        "cooldown_minutes": 240,
        "next_run_at": "2026-03-25T18:00:00+00:00",
        "last_listed_price": 6.99,
        "last_effective_price": 6.59,
        "last_run_status": "succeeded",
        "recipient_email": "owner@example.com",
    },
    "observations": [
        {"observed_at": "2026-03-21T18:00:00+00:00", "listed_price": 8.29, "title_snapshot": "Asian Honey Pears 3ct"},
        {"observed_at": "2026-03-22T18:00:00+00:00", "listed_price": 7.99, "title_snapshot": "Asian Honey Pears 3ct"},
        {"observed_at": "2026-03-23T18:00:00+00:00", "listed_price": 7.79, "title_snapshot": "Asian Honey Pears 3ct"},
        {"observed_at": "2026-03-24T18:00:00+00:00", "listed_price": 7.29, "title_snapshot": "Asian Honey Pears 3ct"},
        {"observed_at": "2026-03-25T18:00:00+00:00", "listed_price": 6.99, "title_snapshot": "Asian Honey Pears 3ct"},
    ],
    "runs": [
        {
            "id": "run-2026-03-25",
            "status": "succeeded",
            "started_at": "2026-03-25T18:00:00+00:00",
            "finished_at": "2026-03-25T18:02:00+00:00",
            "error_message": None,
            "artifact_run_dir": "./.runtime-cache/runs/watch-tasks/demo-task/run-2026-03-25",
            "artifact_evidence": {
                "summary_path": "./.runtime-cache/runs/watch-tasks/demo-task/run-2026-03-25/task_run_summary.json",
                "summary_exists": True,
                "captured_at": "2026-03-25T18:02:00+00:00",
                "title_snapshot": "Asian Honey Pears 3ct",
                "listed_price": 6.99,
                "effective_price": 6.59,
                "source_url": "https://sayweee.com/p/pear-3ct",
                "delivery_count": 1,
                "latest_delivery_status": "sent",
                "has_cashback_quote": True,
            },
        },
        {
            "id": "run-2026-03-24",
            "status": "succeeded",
            "started_at": "2026-03-24T18:00:00+00:00",
            "finished_at": "2026-03-24T18:01:30+00:00",
            "error_message": None,
            "artifact_run_dir": "./.runtime-cache/runs/watch-tasks/demo-task/run-2026-03-24",
            "artifact_evidence": {
                "summary_path": "./.runtime-cache/runs/watch-tasks/demo-task/run-2026-03-24/task_run_summary.json",
                "summary_exists": True,
                "captured_at": "2026-03-24T18:01:30+00:00",
                "title_snapshot": "Asian Honey Pears 3ct",
                "listed_price": 7.29,
                "effective_price": 6.89,
                "source_url": "https://sayweee.com/p/pear-3ct",
                "delivery_count": 1,
                "latest_delivery_status": "sent",
                "has_cashback_quote": True,
            },
        },
    ],
    "delivery_events": [
        {
            "id": "delivery-1",
            "provider": "postmark",
            "recipient": "owner@example.com",
            "status": "sent",
            "sent_at": "2026-03-25T18:02:10+00:00",
            "created_at": "2026-03-25T18:02:05+00:00",
        },
        {
            "id": "delivery-0",
            "provider": "postmark",
            "recipient": "owner@example.com",
            "status": "sent",
            "sent_at": "2026-03-24T18:01:34+00:00",
            "created_at": "2026-03-24T18:01:31+00:00",
        },
    ],
    "cashback_quotes": [
        {
            "provider": "cashbackmonitor",
            "rate_type": "percent",
            "rate_value": 5.7,
            "confidence": 0.92,
            "collected_at": "2026-03-25T18:01:00+00:00",
        }
    ],
    "effective_prices": [
        {"effective_price": 7.89, "computed_at": "2026-03-21T18:01:00+00:00"},
        {"effective_price": 7.59, "computed_at": "2026-03-22T18:01:00+00:00"},
        {"effective_price": 7.39, "computed_at": "2026-03-23T18:01:00+00:00"},
        {"effective_price": 6.89, "computed_at": "2026-03-24T18:01:00+00:00"},
        {"effective_price": 6.59, "computed_at": "2026-03-25T18:01:00+00:00"},
    ],
}


SOCIAL_CARD_SPECS = [
    {
        "output": HERO_SCREEN,
        "eyebrow": "DealWatch control cabin",
        "title": "Know what to compare before you create the task.",
        "subtitle": "Compare URLs first, then move into evidence, price history, and notifications without changing product context.",
        "chips": ["Compare Preview", "Artifact Evidence", "Notifications"],
        "primary": COMPARE_SCREEN,
        "support_mode": "none",
    },
    {
        "output": SOCIAL_SCREEN,
        "eyebrow": "DealWatch public surface",
        "title": "Compare first. Track with evidence after.",
        "subtitle": "Cross-store grocery tracking with compare preview, evidence cards, effective price, and alert history.",
        "chips": ["Compare Preview", "Artifact Evidence", "Alerts"],
        "primary": COMPARE_SCREEN,
        "support_mode": "none",
    },
    {
        "output": OG_HOME,
        "eyebrow": "DealWatch homepage",
        "title": "See the product shape before you install anything.",
        "subtitle": "The homepage shows compare preview, task evidence, and notification policy as one product story.",
        "chips": ["Homepage", "Proof", "Release surface"],
        "primary": COMPARE_SCREEN,
        "support_mode": "none",
    },
    {
        "output": OG_COMPARE,
        "eyebrow": "Compare Preview",
        "title": "Validate the target before you save durable state.",
        "subtitle": "Normalized URLs, candidate keys, and match scores make comparison the first product step instead of guesswork.",
        "chips": ["Read-only sample", "Match score", "Candidate keys"],
        "primary": COMPARE_SCREEN,
        "support_mode": "none",
    },
    {
        "output": OG_PROOF,
        "eyebrow": "Proof",
        "title": "Show the evidence surface, not just the claim.",
        "subtitle": "Routes, screenshots, verifiers, and runtime truth should point back to the same product story.",
        "chips": ["Claims", "Evidence", "Verifiers"],
        "primary": TASK_DETAIL_SCREEN,
        "support_mode": "none",
    },
    {
        "output": OG_QUICK_START,
        "eyebrow": "Quick Start",
        "title": "Get from compare preview to a live task fast.",
        "subtitle": "The local stack stays honest: compare first, then task creation, then price and alert review.",
        "chips": ["Quick start", "Local stack", "Control cabin"],
        "primary": COMPARE_SCREEN,
        "support_mode": "none",
    },
    {
        "output": OG_FAQ,
        "eyebrow": "FAQ",
        "title": "Fast answers should still look like the same product.",
        "subtitle": "FAQ should feel like part of the control cabin, not a detached help page with a recycled image.",
        "chips": ["FAQ", "Trust signals", "Support"],
        "primary": NOTIFICATIONS_SCREEN,
        "support_mode": "none",
    },
    {
        "output": OG_COMPARISON,
        "eyebrow": "Why not a generic tracker",
        "title": "Decide what deserves a watch task first.",
        "subtitle": "DealWatch starts earlier than a single-link tracker by making comparison the intake step, not an afterthought.",
        "chips": ["Comparison", "Compare first", "Decision quality"],
        "primary": COMPARE_SCREEN,
        "support_mode": "none",
    },
]


NOTIFICATION_FIXTURE = {
    "default_recipient_email": "owner@example.com",
    "cooldown_minutes": 240,
    "notifications_enabled": True,
}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


COMPARE_SCREEN_CLIP = {"x": 36, "y": 34, "width": 1360, "height": 1230}
TASK_DETAIL_CLIP = {"x": 36, "y": 34, "width": 1360, "height": 1280}
NOTIFICATIONS_CLIP = {"x": 36, "y": 34, "width": 1360, "height": 900}


@contextlib.contextmanager
def serve_directory(directory: Path, port: int):
    previous = Path.cwd()
    os.chdir(directory)
    server = ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        thread.join(timeout=5)
        os.chdir(previous)


async def install_routes(page, delay_compare: bool = False):
    async def handler(route):
        request = route.request
        url = request.url
        if url.endswith("/api/watch-tasks") and request.method == "GET":
            await route.fulfill(json=WATCH_TASKS_FIXTURE)
            return
        if "/api/watch-tasks/" in url and url.endswith(":run-now"):
            await route.fulfill(json={"id": "run-latest", "status": "running"})
            return
        if url.endswith("/api/watch-tasks/demo-task"):
            await route.fulfill(json=TASK_DETAIL_FIXTURE)
            return
        if url.endswith("/api/settings/notifications") and request.method == "GET":
            await route.fulfill(json=NOTIFICATION_FIXTURE)
            return
        if url.endswith("/api/settings/notifications") and request.method == "PATCH":
            await route.fulfill(json=NOTIFICATION_FIXTURE)
            return
        if url.endswith("/api/compare/preview") and request.method == "POST":
            if delay_compare:
                await asyncio.sleep(1.0)
            await route.fulfill(json=COMPARE_FIXTURE)
            return
        await route.continue_()

    await page.route("**/api/**", handler)


async def capture_compare_screen(context):
    page = await context.new_page()
    await install_routes(page)
    await page.goto("http://127.0.0.1:4173/#compare", wait_until="networkidle")
    await page.fill("textarea", "\n".join(SAMPLE_COMPARE_URLS))
    await page.click("button:has-text('Compare URLs')")
    await page.wait_for_selector("text=Compare result")
    await page.locator("form").evaluate("(node) => node.remove()")
    await page.set_viewport_size({"width": 1440, "height": 1320})
    await page.evaluate("window.scrollTo(0, 0)")
    await page.screenshot(path=str(COMPARE_SCREEN), clip=COMPARE_SCREEN_CLIP)
    await page.close()


async def capture_task_detail(context):
    page = await context.new_page()
    await install_routes(page)
    await page.goto("http://127.0.0.1:4173/#watch-detail/demo-task", wait_until="networkidle")
    await page.wait_for_selector("text=Price Timeline")
    await page.set_viewport_size({"width": 1440, "height": 1360})
    await page.evaluate("window.scrollTo(0, 0)")
    await page.screenshot(path=str(TASK_DETAIL_SCREEN), clip=TASK_DETAIL_CLIP)
    await page.close()


async def capture_notifications(context):
    page = await context.new_page()
    await install_routes(page)
    await page.goto("http://127.0.0.1:4173/#settings", wait_until="networkidle")
    await page.wait_for_selector("text=Default recipient policy")
    await page.set_viewport_size({"width": 1440, "height": 980})
    await page.evaluate("window.scrollTo(0, 0)")
    await page.screenshot(path=str(NOTIFICATIONS_SCREEN), clip=NOTIFICATIONS_CLIP)
    await page.close()


async def capture_compare_gif(context, temp_dir: Path):
    def build_frame_html(stage: int) -> str:
        intro_copy = "Paste two grocery URLs, verify the target, then move into a watch task with the winning row."
        result_copy = "Compare Preview keeps the first product step honest: normalize the URL, verify the candidate, then carry the result forward."
        cta_state = "active" if stage >= 3 else "idle"
        score_state = "active" if stage >= 2 else "idle"
        result_state = "active" if stage >= 1 else "idle"
        ghost = "0.18" if result_state == "idle" else "1"
        score_opacity = "1" if score_state == "active" else "0.25"
        cta_opacity = "1" if cta_state == "active" else "0.2"
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <style>
      :root {{
        --ink: #14213d;
        --paper: #fcfaf5;
        --clay: #f5efe4;
        --ember: #b84c27;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        width: 1280px;
        height: 820px;
        overflow: hidden;
        font-family: "Avenir Next", "SF Pro Display", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(184, 76, 39, 0.16), transparent 28%),
          linear-gradient(180deg, #fcfaf5 0%, #f4ede2 100%);
        color: var(--ink);
      }}
      .shell {{
        width: 100%;
        height: 100%;
        padding: 28px;
        display: grid;
        grid-template-rows: 1fr;
        gap: 0;
      }}
      .hero {{
        display: none;
      }}
      .kicker {{
        color: var(--ember);
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.22em;
        text-transform: uppercase;
      }}
      h1 {{
        margin: 12px 0 8px;
        font-family: Georgia, serif;
        font-size: 56px;
        line-height: 0.96;
      }}
      .lede {{
        margin: 0;
        font-size: 22px;
        line-height: 1.45;
        color: #5f6878;
        max-width: 24ch;
      }}
      .panel {{
        border-radius: 30px;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background: rgba(255, 255, 255, 0.92);
        box-shadow: 0 24px 60px rgba(20, 33, 61, 0.12);
        padding: 32px 34px;
        display: grid;
        grid-template-rows: auto auto 1fr auto;
        gap: 18px;
      }}
      .panel-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }}
      .panel-title {{
        font-size: 16px;
        font-weight: 800;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--ember);
      }}
      .pill-row {{
        display: flex;
        gap: 10px;
      }}
      .pill {{
        padding: 10px 14px;
        border-radius: 999px;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background: rgba(255, 255, 255, 0.9);
        font-size: 15px;
        font-weight: 700;
      }}
      .subcopy {{
        font-size: 20px;
        line-height: 1.45;
        color: #5f6878;
      }}
      .result-grid {{
        display: grid;
        grid-template-columns: 1.1fr 0.9fr;
        gap: 18px;
      }}
      .card {{
        border-radius: 24px;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background: rgba(255, 255, 255, 0.9);
        padding: 20px 22px;
      }}
      .card--accent {{
        background: rgba(245, 239, 228, 0.9);
      }}
      .label {{
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #6f7786;
      }}
      .store {{
        margin-top: 10px;
        font-size: 22px;
        font-weight: 700;
      }}
      .mono {{
        margin-top: 10px;
        font-family: ui-monospace, "SFMono-Regular", monospace;
        font-size: 16px;
        line-height: 1.45;
        color: #4a5568;
      }}
      .product {{
        margin-top: 14px;
        font-size: 34px;
        font-weight: 700;
        line-height: 1.02;
      }}
      .muted {{
        margin-top: 10px;
        font-size: 18px;
        line-height: 1.4;
        color: #5f6878;
      }}
      .metrics {{
        opacity: {score_opacity};
      }}
      .metric {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 10px;
        padding: 12px 0;
        border-bottom: 1px solid rgba(20, 33, 61, 0.08);
        font-size: 18px;
        color: #5f6878;
      }}
      .metric:last-child {{
        border-bottom: none;
      }}
      .metric strong {{
        font-size: 24px;
        color: var(--ink);
      }}
      .metric .ember {{
        color: var(--ember);
      }}
      .cta {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: fit-content;
        padding: 14px 18px;
        border-radius: 999px;
        background: #14213d;
        color: white;
        font-size: 18px;
        font-weight: 700;
        opacity: {cta_opacity};
      }}
      .ghost {{
        opacity: {ghost};
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="hero">
        <div class="kicker">DealWatch Compare Preview</div>
        <h1>Validate the target before you create the task.</h1>
        <p class="lede">{intro_copy}</p>
      </div>
      <div class="panel">
        <div class="panel-top">
          <div class="panel-title">Compare result</div>
          <div class="pill-row">
            <span class="pill">2 submitted</span>
            <span class="pill">2 resolved</span>
          </div>
        </div>
        <div class="subcopy">{result_copy}</div>
        <div class="result-grid ghost">
          <div class="card">
            <div class="label">Store</div>
            <div class="store">weee</div>
            <div class="mono">sayweee.com/p/pear-3ct</div>
            <div class="product">Asian Honey Pears 3ct</div>
            <div class="muted">candidate: pear-3ct</div>
          </div>
          <div class="card card--accent metrics">
            <div class="metric"><span>weee</span><strong>$7.49</strong></div>
            <div class="metric"><span>99 Ranch</span><strong>$6.99</strong></div>
            <div class="metric"><span>match score</span><strong class="ember">96.4</strong></div>
            <div class="metric"><span>next step</span><strong>watch task</strong></div>
          </div>
        </div>
        <div class="cta">Create watch task</div>
      </div>
    </div>
  </body>
</html>"""

    page = await context.new_page()
    await page.set_viewport_size({"width": 1280, "height": 820})
    await page.set_content(build_frame_html(3), wait_until="networkidle")
    source_frame = temp_dir / "frame-source.png"
    await page.screenshot(path=str(source_frame))

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_frame),
        "-vf",
        "scale=960:614:flags=lanczos",
        "-frames:v",
        "1",
        str(COMPARE_GIF),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
    await page.close()


async def capture_social_card(
    context,
    *,
    output_path: Path,
    eyebrow: str,
    title: str,
    subtitle: str,
    chips: list[str],
    width: int,
    height: int,
):
    is_hero = output_path == HERO_SCREEN
    support_mode = "double"
    for spec in SOCIAL_CARD_SPECS:
        if spec["output"] == output_path:
            support_mode = spec.get("support_mode", "double")
            break
    primary_scale = 1.0
    primary_origin = "50% 0%"
    chip_markup = "".join(f'<div class="chip">{chip}</div>' for chip in chips[:3])
    shell_padding = 54 if is_hero else 34
    shell_gap = 26 if is_hero else 20
    columns = "0.8fr 1.2fr" if is_hero else "0.74fr 1.26fr"
    eyebrow_size = 18 if is_hero else 14
    title_size = 70 if is_hero else 44
    subtitle_size = 22 if is_hero else 17
    chip_size = 17 if is_hero else 13
    chip_padding = "12px 16px" if is_hero else "10px 14px"
    primary_height = 760 if is_hero else 548
    rail_height = 172 if is_hero else 148
    screens_rows = f"{primary_height}px" if support_mode == "none" else f"{primary_height}px {rail_height}px"
    compare_variant = output_path in {HERO_SCREEN, SOCIAL_SCREEN, OG_HOME, OG_COMPARE, OG_QUICK_START, OG_COMPARISON}
    proof_variant = output_path == OG_PROOF
    faq_variant = output_path == OG_FAQ
    support_markup = ""
    if compare_variant:
        support_markup = """
        <div class="proof-shell">
          <div class="proof-top">
            <span class="proof-kicker">Compare result</span>
            <div class="proof-pill-row">
              <span class="proof-pill">2 submitted</span>
              <span class="proof-pill">2 resolved</span>
            </div>
          </div>
          <div class="proof-grid proof-grid--compare">
            <div class="proof-card">
              <div class="proof-label">Store</div>
              <div class="proof-value">weee</div>
              <div class="proof-mono">sayweee.com/p/pear-3ct</div>
              <div class="proof-product">Asian Honey Pears 3ct</div>
              <div class="proof-muted">candidate: pear-3ct</div>
            </div>
            <div class="proof-card proof-card--accent">
              <div class="proof-metric"><span>weee</span><strong>$7.49</strong></div>
              <div class="proof-metric"><span>99 Ranch</span><strong>$6.99</strong></div>
              <div class="proof-metric"><span>match score</span><strong class="proof-score">96.4</strong></div>
              <div class="proof-metric"><span>next step</span><strong>create watch task</strong></div>
            </div>
          </div>
        </div>"""
    elif proof_variant:
        support_markup = """
        <div class="proof-shell">
          <div class="proof-top">
            <span class="proof-kicker">Artifact evidence</span>
            <div class="proof-pill-row">
              <span class="proof-pill proof-pill--success">summary ready</span>
              <span class="proof-pill">1 delivery</span>
            </div>
          </div>
          <div class="proof-grid proof-grid--task">
            <div class="proof-card">
              <div class="proof-label">Listed price</div>
              <div class="proof-big">$6.99</div>
            </div>
            <div class="proof-card">
              <div class="proof-label">Effective price</div>
              <div class="proof-big proof-big--ember">$6.59</div>
            </div>
            <div class="proof-card">
              <div class="proof-label">Source captured</div>
              <div class="proof-value">sayweee.com</div>
            </div>
            <div class="proof-card proof-card--accent">
              <div class="proof-label">Cashback</div>
              <div class="proof-value">5.7% back</div>
              <div class="proof-muted">confidence 92%</div>
            </div>
          </div>
        </div>"""
    elif faq_variant:
        support_markup = """
        <div class="proof-shell">
          <div class="proof-top">
            <span class="proof-kicker">Default recipient policy</span>
            <div class="proof-pill-row">
              <span class="proof-pill">cooldown 240m</span>
              <span class="proof-pill">notifications on</span>
            </div>
          </div>
          <div class="proof-grid proof-grid--faq">
            <div class="proof-card">
              <div class="proof-label">Recipient</div>
              <div class="proof-value">owner@example.com</div>
            </div>
            <div class="proof-card">
              <div class="proof-label">Why it exists</div>
              <div class="proof-muted">Repeat suppression and delivery rules stay explicit.</div>
            </div>
          </div>
        </div>"""
    elif support_mode != "none":
        support_markup = f"""
        <div class="rail">
          <div class="frame frame--rail">
            <img src="{TASK_DETAIL_SCREEN.as_uri()}" alt="" />
          </div>
          <div class="frame frame--rail">
            <img src="{NOTIFICATIONS_SCREEN.as_uri()}" alt="" />
          </div>
        </div>"""
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <style>
      :root {{
        color-scheme: light;
        --ink: #14213d;
        --paper: #fcfaf5;
        --clay: #f5efe4;
        --ember: #b84c27;
        --moss: #4e6e58;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Avenir Next", "SF Pro Display", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(184, 76, 39, 0.18), transparent 26%),
          radial-gradient(circle at bottom right, rgba(78, 110, 88, 0.22), transparent 28%),
          linear-gradient(180deg, #fcfaf5 0%, #f4ede2 100%);
        color: var(--ink);
      }}
      .shell {{
        width: {width}px;
        height: {height}px;
        padding: {shell_padding}px;
        display: grid;
        gap: {shell_gap}px;
        grid-template-columns: {columns};
        align-items: stretch;
      }}
      .copy {{
        display: flex;
        flex-direction: column;
        justify-content: center;
      }}
      .eyebrow {{
        color: var(--ember);
        font-size: {eyebrow_size}px;
        font-weight: 800;
        letter-spacing: 0.24em;
        text-transform: uppercase;
      }}
      h1 {{
        margin: 16px 0;
        font-size: {title_size}px;
        line-height: 0.96;
        font-family: Georgia, serif;
        max-width: 11ch;
      }}
      p {{
        margin: 0;
        color: #5f6878;
        font-size: {subtitle_size}px;
        line-height: 1.46;
        max-width: 23ch;
      }}
      .chips {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 22px;
      }}
      .chip {{
        padding: {chip_padding};
        border-radius: 999px;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background: rgba(245, 239, 228, 0.85);
        font-weight: 700;
        font-size: {chip_size}px;
      }}
      .screens {{
        display: grid;
        gap: 16px;
        grid-template-rows: {screens_rows};
        min-width: 0;
      }}
      .proof-shell {{
        border-radius: 28px;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 242, 234, 0.88));
        box-shadow: 0 24px 70px rgba(20, 33, 61, 0.12);
        padding: 20px;
        display: grid;
        gap: 18px;
      }}
      .proof-top {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
      }}
      .proof-kicker {{
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--ember);
      }}
      .proof-pill-row {{
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
      }}
      .proof-pill {{
        padding: 8px 12px;
        border-radius: 999px;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background: rgba(255, 255, 255, 0.86);
        font-size: 12px;
        font-weight: 700;
      }}
      .proof-pill--success {{
        color: #2f6a43;
      }}
      .proof-grid {{
        display: grid;
        gap: 14px;
      }}
      .proof-grid--compare {{
        grid-template-columns: 1.08fr 0.92fr;
      }}
      .proof-grid--task,
      .proof-grid--faq {{
        grid-template-columns: 1fr 1fr;
      }}
      .proof-card {{
        border-radius: 22px;
        border: 1px solid rgba(20, 33, 61, 0.1);
        background: rgba(255, 255, 255, 0.82);
        padding: 16px 18px;
      }}
      .proof-card--accent {{
        background: rgba(245, 239, 228, 0.94);
      }}
      .proof-label {{
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #6f7786;
      }}
      .proof-value {{
        margin-top: 10px;
        font-size: 24px;
        font-weight: 700;
        line-height: 1.15;
      }}
      .proof-product {{
        margin-top: 12px;
        font-size: 22px;
        font-weight: 700;
        line-height: 1.15;
      }}
      .proof-big {{
        margin-top: 10px;
        font-size: 36px;
        font-weight: 700;
        line-height: 1;
      }}
      .proof-big--ember,
      .proof-score {{
        color: var(--ember);
      }}
      .proof-mono {{
        margin-top: 10px;
        font-family: ui-monospace, "SFMono-Regular", monospace;
        font-size: 15px;
        line-height: 1.45;
        color: #4a5568;
      }}
      .proof-muted {{
        margin-top: 10px;
        font-size: 16px;
        line-height: 1.45;
        color: #5f6878;
      }}
      .proof-metric {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid rgba(20, 33, 61, 0.08);
        font-size: 15px;
        color: #5f6878;
      }}
      .proof-metric:last-child {{
        border-bottom: none;
      }}
      .proof-metric strong {{
        color: var(--ink);
        font-size: 18px;
      }}
      .frame {{
        border-radius: 28px;
        overflow: hidden;
        border: 1px solid rgba(20, 33, 61, 0.12);
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(248, 242, 234, 0.86));
        box-shadow: 0 24px 70px rgba(20, 33, 61, 0.12);
      }}
      .frame--primary {{
        padding: 14px;
      }}
      .frame--rail {{
        padding: 10px;
      }}
      .frame img {{
        width: 100%;
        height: 100%;
        display: block;
        border-radius: 18px;
      }}
      .frame--primary img {{
        object-fit: cover;
        object-position: center 0%;
        transform: scale({primary_scale});
        transform-origin: {primary_origin};
      }}
      .frame--rail img {{
        object-fit: cover;
      }}
      .rail {{
        display: grid;
        gap: 16px;
        grid-template-columns: 1fr 1fr;
      }}
      .rail .frame:first-child img {{
        object-position: 74% 18%;
      }}
      .rail .frame:last-child img {{
        object-position: 30% 28%;
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="copy">
        <div>
          <div class="eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
          <div class="chips">
            {chip_markup}
          </div>
        </div>
      </div>
      <div class="screens">
        {support_markup}
      </div>
    </div>
    </body>
</html>"""
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    page = await context.new_page()
    await page.goto(html_path.as_uri(), wait_until="networkidle")
    await page.set_viewport_size({"width": width, "height": height})
    await page.screenshot(path=str(output_path))
    await page.close()
    html_path.unlink(missing_ok=True)


async def main() -> None:
    for path in (
        ASSETS_DIR / "screens",
        ASSETS_DIR / "hero",
        ASSETS_DIR / "demo",
        ASSETS_DIR / "social",
    ):
        path.mkdir(parents=True, exist_ok=True)

    if not FRONTEND_DIST.exists():
        raise RuntimeError("frontend/dist is missing. Run `cd frontend && pnpm build` first.")

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        with serve_directory(FRONTEND_DIST, 4173):
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                context = await browser.new_context(viewport={"width": 1440, "height": 1200}, device_scale_factor=1.5)
                await capture_compare_screen(context)
                await capture_task_detail(context)
                await capture_notifications(context)
                await capture_compare_gif(context, temp_path)
                for spec in SOCIAL_CARD_SPECS:
                    width = 1440 if spec["output"] == HERO_SCREEN else 1280
                    height = 980 if spec["output"] == HERO_SCREEN else 640
                    await capture_social_card(
                        context,
                        output_path=spec["output"],
                        eyebrow=spec["eyebrow"],
                        title=spec["title"],
                        subtitle=spec["subtitle"],
                        chips=spec["chips"],
                        width=width,
                        height=height,
                    )
                await context.close()
                await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
