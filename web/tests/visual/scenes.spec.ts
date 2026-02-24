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
  { id: "J7vS3", url: "/?page=settings&module=tag-manager&mode=visual&scene=J7vS3" },
  { id: "CIBf0", url: "/?page=settings&module=logs-analysis&mode=visual&scene=CIBf0" },
  { id: "Hyzda", url: "/?page=settings&module=logs-analysis&mode=visual&scene=Hyzda" },
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
  await page.goto("/?page=settings&module=tag-manager&mode=visual&scene=J7vS3");
  await page.waitForTimeout(600);

  const readFontSize = async (selector: string) => {
    const locator = page.locator(selector).first();
    await expect(locator).toBeVisible();
    return locator.evaluate((node) => Number.parseFloat(window.getComputedStyle(node).fontSize));
  };

  const settingsModuleFont = await readFontSize("[data-testid='tag-manager-settings-sidebar'] >> text=设置模块");
  expect(Math.abs(settingsModuleFont - 16)).toBeLessThanOrEqual(1);

  const tagLibraryFont = await readFontSize("[data-testid='accordion-标签库'] button span");
  const candidateLibraryFont = await readFontSize("[data-testid='accordion-候选标签库'] button span");
  const blacklistFont = await readFontSize("[data-testid='accordion-黑名单'] button span");

  expect(Math.abs(tagLibraryFont - 20)).toBeLessThanOrEqual(1);
  expect(Math.abs(candidateLibraryFont - 20)).toBeLessThanOrEqual(1);
  expect(Math.abs(blacklistFont - 20)).toBeLessThanOrEqual(1);
});

test("Hyzda detail panel is docked with 16px gap and no overlap", async ({ page }) => {
  await page.goto("/?page=settings&module=logs-analysis&mode=visual&scene=Hyzda");
  await page.waitForTimeout(600);

  const main = page.locator("[data-testid='events-main-column']").first();
  const detail = page.locator("[data-testid='event-detail-panel']").first();
  await expect(main).toBeVisible();
  await expect(detail).toBeVisible();

  const [mainBox, detailBox] = await Promise.all([main.boundingBox(), detail.boundingBox()]);
  if (!mainBox || !detailBox) {
    throw new Error("Missing bounding boxes for Hyzda layout assertions.");
  }

  const gap = detailBox.x - (mainBox.x + mainBox.width);
  expect(gap).toBeGreaterThanOrEqual(14);
  expect(gap).toBeLessThanOrEqual(18);
  expect(detailBox.width).toBeGreaterThanOrEqual(398);
  expect(detailBox.width).toBeLessThanOrEqual(402);
});

test("CIBf0 pagination dock is outside events table card", async ({ page }) => {
  await page.goto("/?page=settings&module=logs-analysis&mode=visual&scene=CIBf0");
  await page.waitForTimeout(600);

  const table = page.locator("[data-testid='events-table-card']").first();
  const pagination = page.locator("[data-testid='events-pagination-dock']").first();
  await expect(table).toBeVisible();
  await expect(pagination).toBeVisible();

  const [tableBox, paginationBox] = await Promise.all([table.boundingBox(), pagination.boundingBox()]);
  if (!tableBox || !paginationBox) {
    throw new Error("Missing bounding boxes for CIBf0 pagination assertions.");
  }

  expect(paginationBox.y).toBeGreaterThanOrEqual(tableBox.y + tableBox.height + 8);
});

test("logs layout keeps viewport width without page-level overflow", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/?page=settings&module=logs-analysis&mode=visual&scene=Hyzda");
  await page.waitForTimeout(600);

  const metrics = await page.evaluate(() => ({
    docWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.docWidth + 1);
});
