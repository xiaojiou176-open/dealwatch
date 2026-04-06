from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


BROWSER_IDENTITY_RUNTIME_DIRNAME = "browser-identity"
DEFAULT_IDENTITY_TITLE_SUFFIX = "browser lane"
DEFAULT_DEALWATCH_IDENTITY_LABEL = "DealWatch"
DEFAULT_DEALWATCH_IDENTITY_MONOGRAM = "DW"
HEX_COLOR_PATTERN = re.compile(r"^#(?:[\da-fA-F]{3}|[\da-fA-F]{6})$")


def _escape_html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _hash_string(value: str) -> int:
    hashed = 0
    for character in value:
        hashed = (hashed * 31 + ord(character)) & 0xFFFFFFFF
    return hashed


def derive_identity_accent(label: str) -> str:
    hue = _hash_string(label) % 360
    return f"hsl({hue} 76% 46%)"


def derive_identity_monogram(label: str) -> str:
    tokens = [
        token
        for token in re.split(r"[^a-zA-Z0-9]+", str(label).strip())
        if token
    ]
    if not tokens:
        return DEFAULT_DEALWATCH_IDENTITY_MONOGRAM
    if len(tokens) == 1:
        return tokens[0][:2].upper()
    return f"{tokens[0][0]}{tokens[1][0]}".upper()


def build_identity_favicon(*, accent: str, monogram: str) -> str:
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
      <rect width="64" height="64" rx="14" fill="{accent}" />
      <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle"
        font-family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        font-size="26" font-weight="700" fill="white">{_escape_html(monogram)}</text>
    </svg>
    """.strip()
    from urllib.parse import quote

    return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"


@dataclass(frozen=True, slots=True)
class BrowserIdentityPage:
    repo_label: str
    accent: str
    monogram: str
    title: str
    identity_path: Path
    identity_url: str


def resolve_identity_label(
    env: Mapping[str, str] | None = None,
    *,
    fallback: str = DEFAULT_DEALWATCH_IDENTITY_LABEL,
) -> str:
    if env is None:
        return fallback
    value = str(env.get("DEALWATCH_BROWSER_IDENTITY_LABEL", "")).strip()
    return value or fallback


def resolve_identity_accent(
    env: Mapping[str, str] | None,
    *,
    label: str,
) -> str:
    if env is not None:
        value = str(env.get("DEALWATCH_BROWSER_IDENTITY_ACCENT", "")).strip()
        if value and HEX_COLOR_PATTERN.fullmatch(value):
            return value
    return derive_identity_accent(label)


def build_browser_identity_page_html(
    *,
    repo_label: str,
    repo_root: str,
    cdp_url: str,
    cdp_port: int,
    user_data_dir: str,
    profile_name: str,
    profile_directory: str,
    accent: str,
    monogram: str,
    quick_links: Sequence[tuple[str, str]] = (),
) -> str:
    title = f"{repo_label} · {cdp_port} · {DEFAULT_IDENTITY_TITLE_SUFFIX}"
    favicon_url = build_identity_favicon(accent=accent, monogram=monogram)
    quick_links_markup = "".join(
        f'<li><a href="{_escape_html(url)}">{_escape_html(label)}</a></li>'
        for label, url in quick_links
    )
    if not quick_links_markup:
        quick_links_markup = "<li>No quick links configured.</li>"

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_escape_html(title)}</title>
    <link rel="icon" href="{favicon_url}" />
    <style>
      :root {{
        --accent: {accent};
        --accent-soft: color-mix(in srgb, {accent} 14%, white);
        --border: rgba(15, 23, 42, 0.12);
        --surface: rgba(255, 255, 255, 0.9);
        --surface-strong: rgba(255, 255, 255, 0.97);
        --text: #0f172a;
        --muted: #475569;
      }}

      * {{ box-sizing: border-box; }}

      body {{
        margin: 0;
        min-height: 100vh;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 20%, white), transparent 34%),
          linear-gradient(160deg, #f8fafc 0%, #eef2ff 40%, #ecfeff 100%);
      }}

      main {{
        width: min(1040px, calc(100vw - 40px));
        margin: 32px auto;
        padding: 28px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.78);
        border: 1px solid var(--border);
        backdrop-filter: blur(12px);
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.12);
      }}

      .hero {{
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 18px;
        align-items: center;
        margin-bottom: 24px;
      }}

      .badge {{
        width: 72px;
        height: 72px;
        border-radius: 22px;
        display: grid;
        place-items: center;
        background: var(--accent);
        color: white;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: 0.06em;
        box-shadow: 0 18px 34px color-mix(in srgb, var(--accent) 35%, transparent);
      }}

      h1 {{
        margin: 0 0 8px;
        font-size: clamp(28px, 3.8vw, 40px);
        line-height: 1.02;
      }}

      .lede {{
        margin: 0;
        color: var(--muted);
        font-size: 15px;
        line-height: 1.6;
      }}

      .callout {{
        margin: 18px 0 0;
        padding: 14px 16px;
        border-radius: 18px;
        background: var(--accent-soft);
        border: 1px solid color-mix(in srgb, var(--accent) 26%, white);
        font-size: 14px;
        line-height: 1.55;
      }}

      .grid {{
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        margin-top: 24px;
      }}

      .card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 18px;
      }}

      .eyebrow {{
        margin: 0 0 10px;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }}

      .value {{
        margin: 0;
        font-size: 22px;
        font-weight: 700;
        line-height: 1.25;
      }}

      .stack {{
        display: grid;
        gap: 12px;
      }}

      .kv {{
        padding: 12px 14px;
        border-radius: 16px;
        background: var(--surface-strong);
        border: 1px solid var(--border);
      }}

      .kv label {{
        display: block;
        margin-bottom: 6px;
        font-size: 12px;
        color: var(--muted);
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}

      .kv code {{
        display: block;
        word-break: break-word;
        font-family: "SFMono-Regular", SFMono-Regular, ui-monospace, Menlo, monospace;
        font-size: 13px;
        line-height: 1.55;
      }}

      ul {{
        margin: 10px 0 0;
        padding-left: 18px;
      }}

      li {{ margin: 8px 0; }}

      a {{
        color: var(--accent);
        text-decoration: none;
        font-weight: 600;
      }}

      a:hover {{ text-decoration: underline; }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="badge">{_escape_html(monogram)}</div>
        <div>
          <h1>{_escape_html(repo_label)}</h1>
          <p class="lede">
            This is the repo-owned browser lane identity tab. Keep it as the left-most anchor so you can tell this
            DealWatch Chrome window apart from other repos at a glance.
          </p>
          <p class="callout">
            Manual one-time polish: pin this tab yourself if you want a tighter visual anchor.
            Do not script Chrome private avatar/theme internals as part of the normal repo bootstrap.
          </p>
        </div>
      </section>

      <section class="grid">
        <article class="card">
          <p class="eyebrow">CDP lane</p>
          <p class="value">{_escape_html(cdp_url)}</p>
          <ul>
            <li>Port: <strong>{_escape_html(str(cdp_port))}</strong></li>
            <li>Profile: <strong>{_escape_html(profile_name or profile_directory)}</strong></li>
            <li>Directory: <code>{_escape_html(profile_directory)}</code></li>
          </ul>
        </article>

        <article class="card">
          <p class="eyebrow">Repo root</p>
          <div class="kv">
            <label>Workspace</label>
            <code>{_escape_html(repo_root)}</code>
          </div>
        </article>

        <article class="card">
          <p class="eyebrow">Chrome user data dir</p>
          <div class="kv">
            <label>Persistent root</label>
            <code>{_escape_html(user_data_dir)}</code>
          </div>
        </article>
      </section>

      <section class="grid">
        <article class="card stack">
          <div class="kv">
            <label>Repo label</label>
            <code>{_escape_html(repo_label)}</code>
          </div>
          <div class="kv">
            <label>Profile display name</label>
            <code>{_escape_html(profile_name)}</code>
          </div>
          <div class="kv">
            <label>Identity accent</label>
            <code>{_escape_html(accent)}</code>
          </div>
        </article>

        <article class="card">
          <p class="eyebrow">Quick links</p>
          <ul>
            {quick_links_markup}
          </ul>
        </article>
      </section>
    </main>
  </body>
</html>
"""


def write_browser_identity_page(
    *,
    repo_root: Path | str,
    env: Mapping[str, str] | None,
    cdp_url: str,
    cdp_port: int,
    user_data_dir: str,
    profile_name: str,
    profile_directory: str,
    quick_links: Sequence[tuple[str, str]] = (),
) -> BrowserIdentityPage:
    repo_root_path = Path(repo_root).resolve()
    repo_label = resolve_identity_label(env)
    accent = resolve_identity_accent(env, label=repo_label)
    monogram = derive_identity_monogram(repo_label)
    title = f"{repo_label} · {cdp_port} · {DEFAULT_IDENTITY_TITLE_SUFFIX}"
    identity_dir = repo_root_path / ".runtime-cache" / BROWSER_IDENTITY_RUNTIME_DIRNAME
    identity_dir.mkdir(parents=True, exist_ok=True)
    identity_path = identity_dir / "index.html"
    identity_path.write_text(
        build_browser_identity_page_html(
            repo_label=repo_label,
            repo_root=str(repo_root_path),
            cdp_url=cdp_url,
            cdp_port=cdp_port,
            user_data_dir=user_data_dir,
            profile_name=profile_name,
            profile_directory=profile_directory,
            accent=accent,
            monogram=monogram,
            quick_links=quick_links,
        ),
        encoding="utf-8",
    )
    return BrowserIdentityPage(
        repo_label=repo_label,
        accent=accent,
        monogram=monogram,
        title=title,
        identity_path=identity_path,
        identity_url=identity_path.resolve().as_uri(),
    )
