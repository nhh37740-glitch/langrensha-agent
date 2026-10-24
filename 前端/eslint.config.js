import js from "@eslint/js";
import globals from "globals";
export default [
  js.configs.recommended,
  {
    files: ["src/scene.js"],
    rules: {
      "no-restricted-globals": ["error", "fetch", "XMLHttpRequest", "WebSocket"],
      "no-restricted-imports": ["error", { paths: ["./main.js"] }],
    },
  },
  {
    files: ["**/*.js"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    ignores: ["node_modules/**"],
  },
];
