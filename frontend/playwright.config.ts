import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: path.resolve(__dirname, "./e2e"),
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:8000",
    headless: true,
    viewport: { width: 1280, height: 800 },
  },
  reporter: [["list"]],
});
