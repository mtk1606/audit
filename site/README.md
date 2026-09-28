# as-audit project site

A static case-study site for the Avellaneda-Stoikov audit. Vite and TypeScript, no framework, no runtime dependencies. Charts and diagrams are hand-built SVG.

## Every number comes from the repository

```
docs/evidence/**, STATE.md, tests/golden/**
        │  scripts/extract-evidence.mjs
        ▼
src/data/evidence.json ──► src/claims.mjs (formats every quantitative claim)
        │                        │
        │                        ├─► scripts/check-claims.mjs   fails the build if any
        │                        │   <span data-ev="…"> in index.html disagrees
        ▼                        ▼
figures (z-chart, quote explorer)   main.ts re-renders the same values at runtime
```

- `npm run build` re-extracts the evidence, runs the claim check, typechecks, then builds. Edit a number in `index.html` by hand and the build fails.
- The extractor refuses a dirty or incomplete run (it checks `git_dirty` and `status` in the manifests) and a `STATE.md` without a clean test result.
- Illustrations are labelled as illustrations. The queue explainer and the quote explorer compute from the project's formulas and the paper's published parameters. They show no simulated or market data.
- `ACCURACY_AUDIT.md` lists every public claim and its source.

## Develop

```bash
cd site
npm ci
npm run dev        # http://localhost:5173
npm run build      # dist/
npm run preview    # serve dist/
npm run check      # claim check only
```

Node 20 or later.

## Configure

- `.env`: `VITE_SITE_URL` sets canonical and Open Graph URLs. Set it to the deployed origin, with a trailing slash.
- `BASE_PATH`: set when serving from a subpath, for example `/audit/` on GitHub Pages.
- `src/config.ts`: repository, LinkedIn and portfolio links. `REPO_REF` is the branch that holds the evidence; switch it to `main` once merged. The static `href`s in `index.html` use the same branch, so update both, or leave the runtime rewrite to handle JavaScript-enabled visitors.

## Social preview

`public/og.png` is rendered from the real replication z-values:

```bash
CHROMIUM_PATH=/path/to/chrome npm run og
```

Render it on a machine that can reach Google Fonts, or the image uses fallback faces.

## Deploy

| Host | How |
|---|---|
| GitHub Pages | `.github/workflows/site.yml` builds on every push and deploys from `main`. Enable Pages with source "GitHub Actions". |
| Netlify | `site/netlify.toml`, base directory `site`. |
| Vercel | Root directory `site`; `vercel.json` sets build, output and cache headers. |
| Any static host | Upload `dist/`. |

`npm run single -- out.html` writes a self-contained single-file version with CSS and JS inlined; fonts still load from Google Fonts.

## Accessibility and performance

- Semantic sections with labelled headings, a skip link, visible focus, and keyboard-operable controls: native range inputs, and buttons with `aria-pressed`.
- The z-chart marks are focusable and have text labels. A data table sits under every result chart, and outside-band marks differ in shape as well as colour.
- Light and dark themes via `prefers-color-scheme` and `data-theme`. Chart colours were checked with a colour-vision-deficiency palette validator in both themes.
- `prefers-reduced-motion` is respected.
- About 30 KB gzipped of HTML, CSS and JS (measured from `vite build` output), plus fonts. No images except the social preview.
