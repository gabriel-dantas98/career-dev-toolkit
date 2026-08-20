import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATEWAY_PATH = path.resolve(HERE, "../../apps-script/Code.gs");
const FIXED_NOW_SECONDS = 1_787_198_400;

function loadGateway() {
  const source = fs.readFileSync(GATEWAY_PATH, "utf8");
  const sandbox = {
    module: { exports: {} },
    exports: {},
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
  return sandbox.module.exports;
}

function dependencies() {
  const cache = new Map();
  return {
    nowMs: () => FIXED_NOW_SECONDS * 1000,
    cache: {
      get: (key) => cache.get(key) ?? null,
      put: (key, value) => cache.set(key, value),
    },
    lock: {
      waitLock() {},
      releaseLock() {},
    },
    spreadsheet: {
      read() {
        return [["Synthetic", "sheet"]];
      },
    },
  };
}

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", () => {
  const payload = JSON.parse(input);
  const request = {
    ...payload,
    requestId: "connector-contract",
    timestamp: FIXED_NOW_SECONDS,
    nonce: "connector-contract-nonce",
  };
  const gateway = loadGateway();
  const result = gateway.handleRequestForTest(
    JSON.stringify(request),
    dependencies(),
  );
  process.stdout.write(JSON.stringify(result));
});
