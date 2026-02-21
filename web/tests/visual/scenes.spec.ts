import { test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const scenes = ["5JcTk", "88L9O", "JrodX", "2L8Xf"] as const;

for (const scene of scenes) {
  test(`capture scene ${scene}`, async ({ page }) => {
    await page.goto(`/?mode=visual&scene=${scene}`);
    await page.waitForTimeout(600);

    const outputDir = path.join(projectRoot, "visual", "actual");
    fs.mkdirSync(outputDir, { recursive: true });

    await page.screenshot({
      path: path.join(outputDir, `${scene}.png`),
      fullPage: false,
    });
  });
}
