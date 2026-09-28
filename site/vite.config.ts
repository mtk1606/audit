import { defineConfig, loadEnv, type Plugin } from "vite";

// Production concerns kept out of the page source:
//  - VITE_SITE_URL: absolute origin for canonical and social-preview tags. When
//    it is missing, those tags are removed rather than shipped with a
//    placeholder; build:release (REQUIRE_SITE_URL=1) fails instead.
//  - Font preloads for the two faces visible above the fold.
function siteUrl(mode: string): Plugin {
  const env = loadEnv(mode, process.cwd(), "");
  const url = (env.VITE_SITE_URL ?? "").trim();
  const valid = /^https:\/\/[^\s]+\/$/.test(url) && !url.includes("example");
  return {
    name: "site-url",
    apply: "build",
    buildStart() {
      if (valid) return;
      const msg = "VITE_SITE_URL is not set to a deployed https origin ending in '/'.";
      if (process.env.REQUIRE_SITE_URL) this.error(msg);
      this.warn(`${msg} Canonical and social-preview URL tags are omitted from this build.`);
    },
    transformIndexHtml: {
      order: "pre",
      handler(html) {
        if (valid) return html;
        return html
          .split("\n")
          .filter((line) => !line.includes("%VITE_SITE_URL%"))
          .join("\n");
      },
    },
  };
}

function preloadFonts(): Plugin {
  const wanted = [/source-serif-4-latin-600-normal-.*\.woff2$/, /ibm-plex-sans-latin-400-normal-.*\.woff2$/];
  return {
    name: "preload-fonts",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        const files = Object.keys(ctx.bundle ?? {}).filter((f) => wanted.some((w) => w.test(f)));
        return files.map((f) => ({
          tag: "link",
          attrs: { rel: "preload", as: "font", type: "font/woff2", href: `${ctx.server ? "" : process.env.BASE_PATH ?? "/"}${f}`, crossorigin: "" },
          injectTo: "head-prepend" as const,
        }));
      },
    },
  };
}

export default defineConfig(({ mode }) => ({
  base: process.env.BASE_PATH ?? "/",
  plugins: [siteUrl(mode), preloadFonts()],
  build: { target: "es2020", cssCodeSplit: false, assetsInlineLimit: 0 },
}));
