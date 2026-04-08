# DealWatch Chrome Companion Listing Notes

Use this file when you submit the repo-owned Chrome companion package to the Chrome Web Store.

## Suggested title

`DealWatch Companion`

## Short description

`Open DealWatch Compare from the current grocery product page and keep the local-first workflow one click away.`

## Full description

DealWatch Companion is the browser helper for the local-first DealWatch runtime.

It helps you take the current grocery product page and open DealWatch's compare-first workflow without pretending the extension itself is the product runtime.

What it does:

- opens the local DealWatch `#compare` route
- pre-fills the current tab URL into the compare form
- provides a context-menu shortcut for the same action
- lets you configure the local DealWatch base URL

What it does not do:

- it does not run compare logic inside the extension
- it does not replace the DealWatch API / worker / WebUI runtime
- it does not expose write-side automation
- it does not claim hosted SaaS behavior

## Single-purpose statement

This extension exists to hand the current product page into the local DealWatch compare flow faster.

## Permission explanations

- `activeTab`: read the current tab URL when you ask the extension to open DealWatch Compare
- `tabs`: open the DealWatch local runtime in a new tab
- `storage`: remember the local DealWatch base URL
- `contextMenus`: offer a right-click "Open in DealWatch Compare" shortcut

## Support URLs

- Homepage: `https://xiaojiou176-open.github.io/dealwatch/`
- Support: `https://github.com/xiaojiou176-open/dealwatch/blob/main/SUPPORT.md`
- Privacy / security: `https://github.com/xiaojiou176-open/dealwatch/blob/main/SECURITY.md`
- Source: `https://github.com/xiaojiou176-open/dealwatch`

## Suggested visual assets

- Store icon: `browser-extension/assets/icon-128.png`
- Promo tile / social-style image: `assets/social/social-preview-1280x640.png`
- Product screenshot: `assets/screens/compare-preview.png`
- Product screenshot: `assets/screens/task-detail-price-history.png`

## Final truth reminder

This package is store-submission ready in-repo, but it is **not** already published in the Chrome Web Store.
