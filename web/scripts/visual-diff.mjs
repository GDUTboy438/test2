import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";

const THRESHOLD = 0.02;
const SCENES = ["5JcTk", "88L9O", "JrodX", "2L8Xf", "J7vS3"];
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baselineDir = path.join(projectRoot, "visual", "baseline");
const actualDir = path.join(projectRoot, "visual", "actual");
const diffDir = path.join(projectRoot, "visual", "diff");
const reportPath = path.join(diffDir, "report.json");

function fail(message) {
  console.error(message);
  process.exit(1);
}

function readPng(filePath) {
  if (!fs.existsSync(filePath)) {
    fail(`Missing image: ${filePath}`);
  }
  return PNG.sync.read(fs.readFileSync(filePath));
}

const report = {
  threshold: THRESHOLD,
  scenes: {},
  pass: true,
};

for (const scene of SCENES) {
  const basePath = path.join(baselineDir, `${scene}.png`);
  const actualPath = path.join(actualDir, `${scene}.png`);
  const diffPath = path.join(diffDir, `${scene}.diff.png`);

  const baseline = readPng(basePath);
  const actual = readPng(actualPath);

  if (baseline.width !== actual.width || baseline.height !== actual.height) {
    fail(`Image size mismatch for ${scene}. baseline=${baseline.width}x${baseline.height}, actual=${actual.width}x${actual.height}`);
  }

  const diff = new PNG({ width: baseline.width, height: baseline.height });
  const diffPixels = pixelmatch(
    baseline.data,
    actual.data,
    diff.data,
    baseline.width,
    baseline.height,
    { threshold: 0.12 },
  );

  const totalPixels = baseline.width * baseline.height;
  const diffRatio = diffPixels / totalPixels;
  const pass = diffRatio < THRESHOLD;

  fs.mkdirSync(path.dirname(diffPath), { recursive: true });
  fs.writeFileSync(diffPath, PNG.sync.write(diff));

  report.scenes[scene] = {
    totalPixels,
    diffPixels,
    diffRatio,
    pass,
  };

  if (!pass) {
    report.pass = false;
  }
}

fs.mkdirSync(path.dirname(reportPath), { recursive: true });
fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));

if (!report.pass) {
  fail("Visual diff failed for one or more scenes.");
}

