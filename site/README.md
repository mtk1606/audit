# as-audit project site

A static case-study page for the Avellaneda-Stoikov audit. Vite and TypeScript, no framework, hand-built SVG charts, self-hosted fonts, no runtime third-party requests.

## Every number comes from the repository

```
docs/evidence/**, STATE.md, tests/golden/**
        │  scripts/extract-evidence.mjs      (refuses dirty or failed runs)
        ▼
src/data/evidence.json ──► src/claims.mjs    (formats every quantitative claim)
                                 │
                                 ├─► scripts/check-claims.mjs  (build gate)
                                 └─► src/main.ts               (renders the same values)
```

The build fails when:

1. any `<span data-ev="…">` value in `index.html` differs from the evidence;
2. an evidence value sits in a sentence or cell without a numbered source mark (`<a class="src" href="#sN">`);
3. a source mark points at an entry missing from the Sources section.

`ACCURACY_AUDIT.md` lists every public claim, its source and its evidence type.

## Develop

```bash
cd site
npm ci
npm run dev          # http://localhost:5173
npm run build        # dist/, with evidence extraction, claim check and typecheck
npm run check        # claim check only
npm run typecheck
```

Node 20 or later (CI uses 22).

## Configure for deployment

| Setting | Where | Value |
|---|---|---|
| `VITE_SITE_URL` | build environment, or `site/.env` (see `.env.example`) | The deployed origin, `https://…/` with a trailing slash. Drives canonical, `og:url`, `og:image` and `twitter:image`. |
| `BASE_PATH` | build environment | Only for subpath hosting, e.g. `/audit/` on GitHub Pages. Default `/`. |
| `REPO_REF` | `src/config.ts` | **`main`** after the branch is merged (current value). Evidence links resolve to `https://github.com/mtk1606/audit/blob/main/…`. Set it to a branch name only while the evidence exists on that branch alone. |

`npm run build` without a valid `VITE_SITE_URL` prints a warning and omits the URL-dependent tags rather than shipping a placeholder. `npm run build:release` fails instead. Every host config below uses `build:release`.

## Deploy

| Host | How |
|---|---|
| GitHub Pages | `.github/workflows/site.yml` builds on every push that touches the site or its evidence, and deploys from `main`. Enable Pages with source "GitHub Actions". `BASE_PATH` and `VITE_SITE_URL` are set in the workflow. |
| Netlify | `netlify.toml` at the repository root (base `site`). Set `VITE_SITE_URL` in the site's environment variables. |
| Vercel | Project root directory `site`; `site/vercel.json` sets install, build, output and cache headers. Set `VITE_SITE_URL`. |
| Any static host | `VITE_SITE_URL=https://…/ npm run build:release`, then upload `dist/`. |

`dist/` contains only `index.html`, `assets/` (hashed JS, CSS, fonts), `og.png` and `robots.txt`.

## Social preview

`public/og.png` (1200×630) is rendered from the real replication values, with the same self-hosted fonts:

```bash
CHROMIUM_PATH=/path/to/chrome npm run og
```

The script fails if any font does not load.

## Quality checks (run 2026-09-28)

- axe-core 4.10 (WCAG 2 A/AA, 2.1 AA, best practice), light and dark themes, all disclosures open: 0 violations.
- Lighthouse 12.2 mobile: performance 99, accessibility 100, best practices 100, SEO 100. Desktop: 100 on all four measured categories. CLS 0.002, total blocking time 0 ms, 165 KiB total transfer.
- Rendered at 375, 430, 768, 1024, 1440 and 1920 px, light and dark: no horizontal scroll, no element overflowing the viewport, no console errors, fonts loaded, CLS ≤ 0.0022.
- Keyboard: every control is reachable, focus is always visible, and chart marks are focusable with text alternatives. A data table sits under the result chart. Overflowing code and table regions become focusable scroll regions.

`npm run single -- <path outside dist/> [--fragment]` writes a self-contained single-file copy for previews. It refuses to write into `dist/`.
