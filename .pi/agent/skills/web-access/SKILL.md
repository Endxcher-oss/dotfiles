---
name: web-access
description: Fetch web pages and search results from inside Pi. Use when a fetch fails (HTTP 403, Cloudflare "Just a moment", Anubis "Making sure you're not a bot!") or returns unrelated content, when choosing between web-fetch and browser-navigate, when reading a page that needs JavaScript, or when picking a reliable source for sourcecode/search/ProtonDB lookups.
---

# Choosing and operating web tools

## Tool selection (cheapest thing that works, first)

| Need | Tool |
|---|---|
| Static page, raw file, JSON API, known URL | `web-fetch` (no JS, cheap) |
| Search results | `web-fetch` on `https://html.duckduckgo.com/html/?q=...` |
| Site blocks non-browser clients / JS challenge / needs interaction | `browser-navigate` (+ `browser-snapshot`, `browser-inspect`, `browser-console`) |

Always try `web-fetch` first unless the site is known to challenge bots.

## Interpreting failures (do not misreport them as tool bugs)

- `Fetch failed: HTTP 403 Forbidden` + "some sites block plain HTTP fetches" → site rejects non-browser clients (observed: `www.mojeek.com`). Fall back to `browser-navigate`.
- Page titled `Making sure you're not a bot!` / "Calculating... Difficulty: N" → **Anubis** proof-of-work anti-scraping (observed on `gitlab.winehq.org`). Requires JS: `web-fetch` will never pass it. A real browser solves the PoW automatically in ~10 s.
- `Just a moment...` / "Checking your browser" → Cloudflare challenge; same handling. See `web-guide` with `guide: "bot-detection"`.
- Search engine results that are **completely unrelated to the query** → the search page was not usable (observed with `www.bing.com/search?q=` returning an unrelated set of results). Treat Bing as unreliable; use DuckDuckGo HTML.
- `HTTP 404` → **suspect your own URL first**, not the tool. Verify the path convention of the project (e.g. Wine's `toolhelp.c` lives in `dlls/kernel32/`, not `dlls/kernelbase/`) or query the API directory listing before retrying.
- `No active session` from browser-* tools → you never navigated; call `browser-navigate` first.
- `Browser not installed. Run /web install` → the browser backend is not registered; browser tools are unusable until installed. Check before promising a browser fallback.

## Reliable sources (verified working)

- Source code: `https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>` and `https://api.github.com/repos/<owner>/<repo>/contents/<path>` — use GitHub mirrors instead of self-hosted forges that run Anubis (e.g. `wine-mirror/wine` mirrors Wine's GitLab).
- Search: `https://html.duckduckgo.com/html/?q=<encoded>` (works, but results are thin for niche/technical queries — prefer fetching the canonical page directly).
- ProtonDB: `https://www.protondb.com/api/v1/reports/summaries/<steam_appid>.json` → `{tier, confidence, score, total}`.

## Browser workflow

1. `browser-navigate` (leave `strategy` default unless it is blocked).
2. If a challenge page appears: **wait 5–10 s** (`bash: sleep 10`) then `browser-snapshot` to re-check. Do not click CAPTCHAs, do not retry rapidly — that escalates blocks.
3. Plain-text pages (raw source, text files) expose almost no elements, so `browser-inspect` may report "No elements cached". Read content instead with `browser-console`:

   ```js
   (() => { const t = document.body.innerText; return { url: location.href, len: t.length, head: t.slice(0, 120) }; })()
   ```
   Add targeted checks (`t.includes('CreateToolhelp32Snapshot')`) instead of dumping whole pages into context.
4. `@e` refs expire after any click/type/scroll/press/back — take a fresh `browser-snapshot` before interacting again.
5. Large pages: bound the output (`browser-inspect` `maxChars`/`query`, `read` with offset/limit on the saved temp file) rather than pulling everything in.

## Context discipline

Fetching is cheap; keeping fetched text is not. After extracting the facts (error string, version, function signature, numbers), compress the fetch/tool output in the same turn. Prefer one targeted fetch over a crawl, and record the URL + the exact quoted string you needed rather than the page body.
