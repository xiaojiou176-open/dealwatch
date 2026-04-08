# DealWatch Chrome Companion

This package is the repo-owned Chrome extension companion for DealWatch.

In plain English:

- it is a browser helper for the local-first DealWatch runtime
- it is **not** the primary product surface
- it is **not** a hosted control plane
- it is prepared so the remaining work is the Chrome Web Store dashboard submission step, not missing repo files

## What it does

- opens the local `#compare` route directly from the current tab
- pre-fills the current page URL into the DealWatch compare form
- provides a context-menu shortcut for the same action
- lets the operator configure the local DealWatch base URL

## What it does not do

- it does not run compare logic in the extension itself
- it does not bypass the local runtime
- it does not expose write-side automation or builder-only surfaces
- it does not claim Chrome Web Store publication yet

## Files that matter

- `manifest.json`
- `background.js`
- `popup.html`
- `popup.js`
- `popup.css`
- `options.html`
- `options.js`
- `options.css`
- `assets/icon-16.png`
- `assets/icon-32.png`
- `assets/icon-48.png`
- `assets/icon-128.png`
- `chrome-web-store-listing.md`

## Build the store-upload bundle

```bash
python3 scripts/build_browser_extension_bundle.py
```

The generated ZIP will land under `dist/browser-extension/`.

## Verify the extension surface

```bash
python3 scripts/verify_browser_extension_surface.py
```

## Manual Chrome Web Store step that remains

After the repo stays green, the only remaining manual step is:

1. upload the generated ZIP in the Chrome Web Store dashboard
2. paste the prepared listing copy from `chrome-web-store-listing.md`
3. complete the store form answers and final review submission
