import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const scenes = [
  { id: "5JcTk", url: "/?mode=visual&scene=5JcTk" },
  { id: "88L9O", url: "/?mode=visual&scene=88L9O" },
  { id: "JrodX", url: "/?mode=visual&scene=JrodX" },
  { id: "2L8Xf", url: "/?mode=visual&scene=2L8Xf" },
  { id: "J7vS3", url: "/?page=tag-manager&mode=visual&scene=J7vS3" },
] as const;

for (const scene of scenes) {
  test(`capture scene ${scene.id}`, async ({ page }) => {
    await page.goto(scene.url);
    await page.waitForTimeout(600);

    const outputDir = path.join(projectRoot, "visual", "actual");
    fs.mkdirSync(outputDir, { recursive: true });

    await page.screenshot({
      path: path.join(outputDir, `${scene.id}.png`),
      fullPage: false,
    });
  });
}

test("J7vS3 heading font sizes follow pen spec", async ({ page }) => {
  await page.goto("/?page=tag-manager&mode=visual&scene=J7vS3");
  await page.waitForTimeout(600);

  const readFontSize = async (selector: string, index = 0) => {
    const locator = page.locator(selector).nth(index);
    await expect(locator).toBeVisible();
    return locator.evaluate((node) => Number.parseFloat(window.getComputedStyle(node).fontSize));
  };

  const settingsModuleFont = await readFontSize(
    "[data-testid='tag-manager-settings-sidebar'] > div:nth-child(3) > div:first-child",
  );
  expect(Math.abs(settingsModuleFont - 16)).toBeLessThanOrEqual(1);

  const sectionTitleSelector = "section[data-testid^='accordion-'] > button > div:first-child > span:last-child";
  const tagLibraryFont = await readFontSize(sectionTitleSelector, 0);
  const candidateLibraryFont = await readFontSize(sectionTitleSelector, 1);
  const blacklistFont = await readFontSize(sectionTitleSelector, 2);

  expect(Math.abs(tagLibraryFont - 20)).toBeLessThanOrEqual(1);
  expect(Math.abs(candidateLibraryFont - 20)).toBeLessThanOrEqual(1);
  expect(Math.abs(blacklistFont - 20)).toBeLessThanOrEqual(1);
});
