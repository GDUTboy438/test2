import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCENES = ["5JcTk", "88L9O", "JrodX", "2L8Xf", "J7vS3", "CIBf0", "Hyzda"];
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baselineDir = path.join(projectRoot, "visual", "baseline");
const actualDir = path.join(projectRoot, "visual", "actual");

function fail(message) {
  console.error(message);
  process.exit(1);
}

function copyFile(source, target) {
  if (!fs.existsSync(source)) {
    fail(`Source image not found: ${source}`);
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
  console.log(`Baseline updated: ${target}`);
}

const args = process.argv.slice(2);

if (args.includes("--from-actual")) {
  for (const scene of SCENES) {
    copyFile(path.join(actualDir, `${scene}.png`), path.join(baselineDir, `${scene}.png`));
  }
  process.exit(0);
}

if (args.length === 0) {
  fail("Usage: npm run visual:baseline -- --from-actual OR npm run visual:baseline -- <scene>=<path>");
}

for (const arg of args) {
  const [scene, sourcePath] = arg.split("=");
  if (!scene || !sourcePath || !SCENES.includes(scene)) {
    fail(`Invalid arg '${arg}'. Expected <scene>=<path> and scene in ${SCENES.join(", ")}.`);
  }
  copyFile(path.resolve(sourcePath), path.join(baselineDir, `${scene}.png`));
}

