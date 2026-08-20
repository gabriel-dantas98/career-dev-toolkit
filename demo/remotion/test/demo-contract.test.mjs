import assert from "node:assert/strict";
import {existsSync, readFileSync} from "node:fs";
import {join} from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));
const requiredFiles = [
  "package.json",
  "README.md",
  "src/content.mjs",
  "src/index.jsx",
  "src/Root.jsx",
  "src/CareerOSDemo.jsx",
];

test("demo project contains the isolated render surface", () => {
  const missing = requiredFiles.filter(
    (relativePath) => !existsSync(join(projectRoot, relativePath)),
  );

  assert.deepEqual(missing, []);
});

test("composition metadata and scene copy preserve the evidence boundary", async () => {
  const {COMPOSITION, SCENES} = await import("../src/content.mjs");
  const copy = JSON.stringify(SCENES);

  assert.deepEqual(COMPOSITION, {
    id: "CareerOSDemo",
    width: 1920,
    height: 1080,
    fps: 30,
    durationInFrames: 1140,
  });
  assert.equal(SCENES.length, 7);
  assert.match(copy, /90% glue/);
  assert.match(copy, /workflow shorthand—not a measured metric/i);
  assert.match(copy, /harvest → validate → encrypted SQLCipher store/);
  assert.match(copy, /Tapioca-style Apps Script browser-mode/);
  assert.match(copy, /no Tapioca runtime/);
  assert.match(copy, /Privacy fails closed/);
  assert.match(copy, /Destination grant ≠ background grant/);
  assert.match(copy, /RAW/);
  assert.match(copy, /exact read-back/);
  assert.match(copy, /All 8 stages passed/);
  assert.match(copy, /Synthetic providers only/);
  assert.match(copy, /Live Google OAuth certification/);
  assert.match(copy, /NOT RUN/);
  assert.match(copy, /google:event-88/);
  assert.equal(
    SCENES.find((scene) => scene.key === "certification")?.duration,
    150,
  );
  assert.doesNotMatch(copy, /live Google passed/i);
  assert.doesNotMatch(copy, /customer/i);
  assert.doesNotMatch(copy, /@/);
  assert.doesNotMatch(copy, /SYNTHETIC_SECRET_/);
});

test("root package remains independent of Remotion", () => {
  const rootPackage = JSON.parse(
    readFileSync(join(projectRoot, "..", "..", "package.json"), "utf8"),
  );
  const demoPackage = JSON.parse(
    readFileSync(join(projectRoot, "package.json"), "utf8"),
  );

  assert.equal(rootPackage.dependencies?.remotion, undefined);
  assert.equal(rootPackage.devDependencies?.remotion, undefined);
  assert.equal(demoPackage.scripts.render, "remotion render src/index.jsx CareerOSDemo out/careeros-demo.mp4");
});
