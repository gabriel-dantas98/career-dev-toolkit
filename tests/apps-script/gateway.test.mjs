import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATEWAY_PATH = path.resolve(HERE, "../../apps-script/Code.gs");
const PACKAGE_PATH = path.resolve(HERE, "../../package.json");
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

test("aggregate npm test includes the gateway suite", () => {
  const packageJson = JSON.parse(fs.readFileSync(PACKAGE_PATH, "utf8"));

  assert.match(packageJson.scripts.test, /tests\/apps-script\/\*\.test\.mjs/);
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

  const broadQuery = gateway.handleRequestForTest(
    request("drive.search", {
      nonce: "nonce-drive-query-0001",
      query: "x".repeat(201),
      timeMin: "2026-08-01T00:00:00Z",
      timeMax: "2026-08-20T00:00:00Z",
      maxResults: 10,
    }),
    deps,
  );
  assert.equal(broadQuery.errors[0].code, "INVALID_QUERY");
});

test("Gmail rejects grouping and token-delimited OR before GmailApp", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();
  let providerCalls = 0;
  deps.gmail = {
    search() {
      providerCalls += 1;
      return [];
    },
  };
  const adversarialQueries = [
    "(synthetic)",
    "{synthetic evidence}",
    "[synthetic evidence]",
    "synthetic oR after:0",
    "synthetic,OR,after:0",
  ];

  for (const [index, query] of adversarialQueries.entries()) {
    const response = gateway.handleRequestForTest(
      request("gmail.search", {
        requestId: `gmail-query-${index}`,
        nonce: `nonce-gmail-query-${index}-0001`,
        query,
        timeMin: "2026-08-01T00:00:00Z",
        timeMax: "2026-08-20T00:00:00Z",
        maxResults: 10,
      }),
      deps,
    );
    assert.equal(response.ok, false);
    assert.equal(response.errors[0].code, "INVALID_QUERY");
  }
  assert.equal(providerCalls, 0);
});

test("stale timestamps, invalid nonces, and replayed nonces fail closed", () => {
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

  const invalidNonce = gateway.handleRequestForTest(
    request("health", {
      requestId: "invalid-nonce",
      nonce: "short",
    }),
    deps,
  );
  assert.equal(invalidNonce.errors[0].code, "INVALID_NONCE");

  const body = request("health", { nonce: "nonce-replay-health-0001" });
  const first = gateway.handleRequestForTest(body, deps);
  const second = gateway.handleRequestForTest(body, deps);
  assert.equal(first.ok, true);
  assert.equal(second.ok, false);
  assert.equal(second.errors[0].code, "NONCE_REPLAYED");
});

test("brag-sheet writes use one full-owned-window RAW update", () => {
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
  const call = JSON.parse(JSON.stringify(calls[0]));
  assert.equal(call.spreadsheetId, "synthetic-sheet-id");
  assert.equal(call.range, "'Brag Sheet'!A2:L201");
  assert.deepEqual(call.options, { valueInputOption: "RAW" });
  assert.equal(call.resource.values.length, 200);
  assert.equal(call.resource.values[0].length, 12);
  assert.deepEqual(call.resource.values[0].slice(0, 2), [
    "delivery:1",
    "'03/04/2026",
  ]);
  assert.deepEqual(call.resource.values[0].slice(2), Array(10).fill(""));
  assert.deepEqual(call.resource.values[1], Array(12).fill(""));
});

test("one full-window update addresses only the owned rows and A:L", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();
  const addressedRanges = [];
  let ownedRows = Array(200).fill(undefined);
  deps.sheets = {
    update(resource, _spreadsheetId, range, options) {
      addressedRanges.push(range);
      assert.deepEqual(JSON.parse(JSON.stringify(options)), {
        valueInputOption: "RAW",
      });
      ownedRows = resource.values.map((row) => Array.from(row));
      return { updatedRange: range };
    },
  };

  const response = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-owned-window-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: [["first"], ["second"]],
    }),
    deps,
  );

  assert.equal(response.ok, true);
  assert.deepEqual(addressedRanges, ["'Brag Sheet'!A2:L201"]);
  assert.equal(ownedRows.length, 200);
  assert.deepEqual(ownedRows[0], ["first", ...Array(11).fill("")]);
  assert.deepEqual(ownedRows[1], ["second", ...Array(11).fill("")]);
  assert.deepEqual(ownedRows[2], Array(12).fill(""));
});

test("read-back uses UNFORMATTED_VALUE and pads the requested matrix", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();
  const calls = [];
  deps.sheets = {
    get(spreadsheetId, range, options) {
      calls.push({ spreadsheetId, range, options });
      return { values: [["delivery:1"]] };
    },
  };

  const response = gateway.handleRequestForTest(
    request("sheets.readBack", {
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      rowCount: 1,
      columnCount: 2,
    }),
    deps,
  );

  assert.equal(response.ok, true);
  assert.deepEqual(JSON.parse(JSON.stringify(response.data.values)), [
    ["delivery:1", ""],
  ]);
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    {
      spreadsheetId: "synthetic-sheet-id",
      range: "'Brag Sheet'!A2:B2",
      options: { valueRenderOption: "UNFORMATTED_VALUE" },
    },
  ]);
});

test("a shrinking write clears stale owned rows without expanding ownership", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();
  let ownedRows = Array(200).fill(undefined);
  deps.sheets = {
    update(resource, _spreadsheetId, range, options) {
      assert.equal(range, "'Brag Sheet'!A2:L201");
      assert.equal(options.valueInputOption, "RAW");
      ownedRows = resource.values.map((row) => Array.from(row));
      return { updatedRange: range };
    },
  };

  const first = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-shrink-first-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: [["first"], ["stale"]],
    }),
    deps,
  );
  const second = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      requestId: "request-shrink-second",
      nonce: "nonce-shrink-second-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: [["replacement"]],
    }),
    deps,
  );

  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.deepEqual(ownedRows[0], [
    "replacement",
    ...Array(11).fill(""),
  ]);
  assert.deepEqual(ownedRows[1], Array(12).fill(""));
});

test("resource, body, matrix, and write/read-back bounds have stable errors", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();

  const oversizedBody = gateway.handleRequestForTest(
    "x".repeat(256 * 1024 + 1),
    deps,
  );
  assert.equal(oversizedBody.errors[0].code, "REQUEST_TOO_LARGE");

  const invalidJson = gateway.handleRequestForTest("{", deps);
  assert.equal(invalidJson.errors[0].code, "INVALID_JSON");

  const invalidShape = gateway.handleRequestForTest("[]", deps);
  assert.equal(invalidShape.errors[0].code, "INVALID_REQUEST");

  const invalidRequestId = gateway.handleRequestForTest(
    request("health", { requestId: "spaces are not identifiers" }),
    deps,
  );
  assert.equal(invalidRequestId.errors[0].code, "INVALID_REQUEST_ID");

  const invalidResource = gateway.handleRequestForTest(
    request("docs.read", {
      nonce: "nonce-invalid-resource-0001",
      documentId: "doc:canonical-is-not-bare",
    }),
    deps,
  );
  assert.equal(invalidResource.errors[0].code, "INVALID_RESOURCE_ID");

  const invalidSheetName = gateway.handleRequestForTest(
    request("sheets.read", {
      nonce: "nonce-invalid-sheet-name-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "",
      range: "A1:B1",
    }),
    deps,
  );
  assert.equal(invalidSheetName.errors[0].code, "INVALID_SHEET_NAME");

  const ragged = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-ragged-write-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: [["one", "two"], ["three"]],
    }),
    deps,
  );
  assert.equal(ragged.errors[0].code, "INVALID_VALUES");

  for (const [index, value] of [
    { nested: "not scalar" },
    "x".repeat(8_001),
  ].entries()) {
    const response = gateway.handleRequestForTest(
      request("sheets.writeBragsheet", {
        requestId: `invalid-cell-${index}`,
        nonce: `nonce-invalid-cell-${index}-0001`,
        spreadsheetId: "synthetic-sheet-id",
        sheetName: "Brag Sheet",
        startRow: 2,
        inputMode: "RAW",
        values: [[value]],
      }),
      deps,
    );
    assert.equal(response.errors[0].code, "INVALID_VALUES");
  }

  const tooManyRows = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-write-rows-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: Array.from({ length: 201 }, () => ["value"]),
    }),
    deps,
  );
  assert.equal(tooManyRows.errors[0].code, "WRITE_OUT_OF_BOUNDS");

  const tooManyColumns = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-write-columns-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 2,
      inputMode: "RAW",
      values: [Array.from({ length: 13 }, () => "value")],
    }),
    deps,
  );
  assert.equal(tooManyColumns.errors[0].code, "WRITE_OUT_OF_BOUNDS");

  const ownedAreaOverflow = gateway.handleRequestForTest(
    request("sheets.writeBragsheet", {
      nonce: "nonce-write-overflow-0001",
      spreadsheetId: "synthetic-sheet-id",
      sheetName: "Brag Sheet",
      startRow: 999_802,
      inputMode: "RAW",
      values: [["value"]],
    }),
    deps,
  );
  assert.equal(ownedAreaOverflow.errors[0].code, "START_ROW_OUT_OF_BOUNDS");

  for (const [index, dimensions] of [
    { rowCount: 201, columnCount: 1 },
    { rowCount: 1, columnCount: 13 },
    { rowCount: 200, columnCount: 12, startRow: 999_802 },
  ].entries()) {
    const response = gateway.handleRequestForTest(
      request("sheets.readBack", {
        requestId: `readback-bound-${index}`,
        nonce: `nonce-readback-bound-${index}-0001`,
        spreadsheetId: "synthetic-sheet-id",
        sheetName: "Brag Sheet",
        startRow: dimensions.startRow ?? 2,
        rowCount: dimensions.rowCount,
        columnCount: dimensions.columnCount,
      }),
      deps,
    );
    assert.equal(response.errors[0].code, "READBACK_OUT_OF_BOUNDS");
  }
});

test("Docs content is capped at the shared excerpt bound", () => {
  const { gateway } = loadGateway();
  const deps = dependencies();
  deps.docs = {
    read() {
      return "x".repeat(8_001);
    },
  };

  const response = gateway.handleRequestForTest(
    request("docs.read", {
      documentId: "synthetic-document-id",
    }),
    deps,
  );

  assert.equal(response.ok, true);
  assert.equal(response.data.content.length, 8_000);
});

test("gateway has no arbitrary evaluation or property-based action dispatch", () => {
  const { source } = loadGateway();

  assert.doesNotMatch(source, /\beval\s*\(/);
  assert.doesNotMatch(source, /\bFunction\s*\(/);
  assert.doesNotMatch(source, /\[[^\]]*action[^\]]*\]\s*\(/);
  assert.match(
    source,
    /valueRenderOption:\s*"UNFORMATTED_VALUE"/,
  );
  assert.match(source, /Sheets\.Spreadsheets\.Values\.get/);
  assert.doesNotMatch(source, /Sheets\.Spreadsheets\.Values\.clear/);
});

