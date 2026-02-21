import { spawn, spawnSync } from "node:child_process";
import http from "node:http";

const PREVIEW_URL = "http://127.0.0.1:4173";
const PREVIEW_HOST = "127.0.0.1";
const PREVIEW_PORT = "4173";

const npmCmd = "npm";
const npxCmd = "npx";

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isServerReady() {
  return new Promise((resolve) => {
    const req = http.get(PREVIEW_URL, (res) => {
      res.resume();
      resolve(res.statusCode !== undefined && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForServer(timeoutMs = 60_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    // eslint-disable-next-line no-await-in-loop
    const ready = await isServerReady();
    if (ready) {
      return;
    }
    // eslint-disable-next-line no-await-in-loop
    await wait(400);
  }
  throw new Error(`Preview server did not become ready in ${timeoutMs}ms`);
}

function spawnProcess(command, args, label) {
  const child = spawn(command, args, {
    stdio: "inherit",
    shell: true,
  });
  child.on("error", (error) => {
    console.error(`[${label}] failed:`, error);
  });
  return child;
}

function killProcessTree(pid) {
  if (!pid) {
    return;
  }
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
      stdio: "ignore",
      shell: true,
    });
    return;
  }
  process.kill(pid, "SIGTERM");
}

async function main() {
  const preview = spawnProcess(
    npmCmd,
    ["run", "preview", "--", "--host", PREVIEW_HOST, "--port", PREVIEW_PORT],
    "preview",
  );

  try {
    await waitForServer();

    const testRunner = spawnProcess(
      npxCmd,
      ["playwright", "test", "tests/visual/scenes.spec.ts", "--config=playwright.config.ts"],
      "playwright",
    );

    const exitCode = await new Promise((resolve) => {
      testRunner.on("exit", (code) => resolve(code ?? 1));
    });

    if (exitCode !== 0) {
      process.exit(exitCode);
    }
  } finally {
    killProcessTree(preview.pid ?? 0);
    await wait(400);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
