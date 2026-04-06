import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

const repoRoot = fileURLToPath(new URL("..", import.meta.url));
const sharedLocales = fileURLToPath(new URL("../site/data/i18n", import.meta.url));

export default defineConfig({
  plugins: [preact()],
  resolve: {
    alias: {
      "@shared-locales": sharedLocales,
      react: "preact/compat",
      "react-dom": "preact/compat",
      "react/jsx-runtime": "preact/jsx-runtime"
    }
  },
  server: {
    fs: {
      allow: [repoRoot]
    },
    port: 5173
  }
});
