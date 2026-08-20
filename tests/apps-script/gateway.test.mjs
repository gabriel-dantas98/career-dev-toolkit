import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATEWAY_PATH = path.resolve(HERE, "../../apps-script/Code.gs");
const FIXED_NOW_MS = 1_787_198_400_000;

function loadGateway() {
  const source = fs.readFileSync(GATEWAY_PATH, "utf8");
  const sandbox = {
    module: { exports: {} },
    exports: {},
    console,
    Date,
    JSON,
    Math,
    Object,
    RegExp,
    String,
    Error,
    Array,
  };
  vm.runInNewContext(source, sandbox, { filename: GATEWAY_PATH });
  return { gateway: sandbox.module.exports, source };
}

function dependencies() {
  const values = new Map();
  return {
    nowMs: () => FIXED_NOW_MS,
    cache: {
      get(key) {
        return values.get(key) ?? null;
      },
      put(key, value) {
        values.set(key, value);
      },
    },
    lock: {
      waitLock() {},
      releaseLock() {},
    },
  };
}

function request(action, extra = {}) {
  return JSON.stringify({
    action,
    requestId: `request-${action}`,
    timestamp: FIXED_NOW_MS / 1000,
    nonce: `nonce-${action.replaceAll(".", "-")}-0001`,
    ...extra,
  });
}

test("gateway exposes only the promised fixed action allowlist", () => {
  const { gateway } = loadGateway();

  assert.deepEqual(Array.from(gateway.ALLOWED_ACTIONS), [
    "health",
    "calendar.search",
    "gmail.search",
    "drive.search",
    "docs.read",
    "sheets.read",
    "sheets.writeBragsheet",
    "sheets.readBack",
  ]);
});

test("unknown actions fail in the stable envelope without echoing canaries", () => {
  const { gateway } = loadGateway();
  const authorizationCanary = "SYNTHETIC_AUTHORIZATION_CANARY";

  const response = gateway.handleRequestForTest(
    request("admin.eval", {
      authorization: authorizationCanary,
      expression: authorizationCanary,
    }),
    dependencies(),
  );
  const serialized = JSON.stringify(response);

  assert.deepEqual(Object.keys(response), [
    "ok",
    "requestId",
    "data",
    "errors",
    "version",
  ]);
  assert.equal(response.ok, false);
  assert.equal(response.requestId, "request-admin.eval");
  assert.equal(response.errors[0].code, "ACTION_NOT_ALLOWED");
  assert.equal(serialized.includes(authorizationCanary), false);
});

test("sheet reads reject open-ended and broad ranges before provider access", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();

  for (const [index, range] of ["A:A", "1:10", "A1:Z1000"].entries()) {
    const response = gateway.handleRequestForTest(
      request("sheets.read", {
        requestId: `range-${index}`,
        nonce: `nonce-range-${index}-0001`,
        spreadsheetId: "synthetic-sheet-id",
        sheetName: "Brag Sheet",
        range,
      }),
      deps,
    );
    assert.equal(response.ok, false);
    assert.equal(response.errors[0].code, "RANGE_OUT_OF_BOUNDS");
  }
});

test("search actions require finite windows and bounded counts", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();

  const missingWindow = gateway.handleRequestForTest(
    request("gmail.search", {
      query: "synthetic",
      maxResults: 10,
    }),
    deps,
  );
  assert.equal(missingWindow.errors[0].code, "INVALID_TIME_WINDOW");

  const broadWindow = gateway.handleRequestForTest(
    request("calendar.search", {
      nonce: "nonce-calendar-broad-0001",
      timeMin: "2024-01-01T00:00:00Z",
      timeMax: "2026-08-20T00:00:00Z",
      maxResults: 10,
    }),
    deps,
  );
  assert.equal(broadWindow.errors[0].code, "INVALID_TIME_WINDOW");

  const broadCount = gateway.handleRequestForTest(
    request("drive.search", {
      nonce: "nonce-drive-count-0001",
      query: "synthetic",
      timeMin: "2026-08-01T00:00:00Z",
      timeMax: "2026-08-20T00:00:00Z",
      maxResults: 51,
    }),
    deps,
  );
  assert.equal(broadCount.errors[0].code, "MAX_RESULTS_OUT_OF_BOUNDS");

  const timezoneMissing = gateway.handleRequestForTest(
    request("calendar.search", {
      nonce: "nonce-calendar-zone-0001",
      timeMin: "2026-08-01",
      timeMax: "2026-08-20",
      maxResults: 10,
    }),
    deps,
  );
  assert.equal(timezoneMissing.errors[0].code, "INVALID_TIME_WINDOW");
});

test("stale timestamps and replayed nonces fail closed", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();

  const stale = gateway.handleRequestForTest(
    request("health", {
      timestamp: FIXED_NOW_MS / 1000 - 301,
      nonce: "nonce-stale-health-0001",
    }),
    deps,
  );
  assert.equal(stale.errors[0].code, "STALE_REQUEST");

  const body = request("health", { nonce: "nonce-replay-health-0001" });
  const first = gateway.handleRequestForTest(body, deps);
  const second = gateway.handleRequestForTest(body, deps);
  assert.equal(first.ok, true);
  assert.equal(second.ok, false);
  assert.equal(second.errors[0].code, "NONCE_REPLAYED");
});

test("brag-sheet writes require RAW mode and use the bounded Sheets API update", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();
  const calls = [];
  deps.sheets = {
    update(resource, spreadsheetId, range, options) {
      calls.push({ resource, spreadsheetId, range, options });
      return { updatedRows: resource.values.length };
    },
  };

  const rejected = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "USER_ENTERED",
      values: [["delivery:1", "03/04/2026"]],
    }),
    deps,
  );
  assert.equal(rejected.errors[0].code, "RAW_REQUIRED");

  const accepted = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-write-raw-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: [["delivery:1", "'03/04/2026"]],
    }),
    deps,
  );
  assert.equal(accepted.ok, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.valueInputOption, "RAW");
  assert.equal(calls[0].range, "'Brag Sheet'!A2:B2");
});

test("gateway has no arbitrary evaluation or property-based action dispatch", () => {
  const { source } = loadGateway();

  assert.doesNotMatch(source, /\beval\s*\(/);
  assert.doesNotMatch(source, /\bFunction\s*\(/);
  assert.doesNotMatch(source, /\[[^\]]*action[^\]]*\]\s*\(/);
});

