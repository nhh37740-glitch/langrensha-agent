import js from "@eslint/js";
import globals from "globals";
export default [
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    ignores: ["node_modules/**"],
  },
];
