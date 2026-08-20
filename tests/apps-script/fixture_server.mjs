import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATEWAY_PATH = path.resolve(HERE, "../../apps-script/Code.gs");
const PORT = Number(process.env.CAREEROS_FIXTURE_PORT || 8765);
const FIXED_NOW_SECONDS = Number(
  process.env.CAREEROS_FIXTURE_NOW || 1_787_198_400,
);
const MAX_BODY_BYTES = 256 * 1024;

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

function fixtureDependencies() {
  const cacheValues = new Map();
  return {
    nowMs: () => FIXED_NOW_SECONDS * 1000,
    cache: {
      get: (key) => cacheValues.get(key) ?? null,
      put: (key, value) => cacheValues.set(key, value),
    },
    lock: {
      waitLock() {},
      releaseLock() {},
    },
  };
}

const gateway = loadGateway();
const dependencies = fixtureDependencies();

const server = http.createServer((request, response) => {
  if (request.method !== "POST" || request.url !== "/exec") {
    response.writeHead(404, { "content-type": "application/json" });
    response.end('{"ok":false}');
    return;
  }

  let body = "";
  let bytes = 0;
  request.setEncoding("utf8");
  request.on("data", (chunk) => {
    bytes += Buffer.byteLength(chunk);
    if (bytes <= MAX_BODY_BYTES) {
      body += chunk;
    }
  });
  request.on("end", () => {
    const result =
      bytes > MAX_BODY_BYTES
        ? {
            ok: false,
            requestId: "",
            data: null,
            errors: [
              {
                code: "REQUEST_TOO_LARGE",
                message: "Request body exceeds the fixed limit.",
              },
            ],
            version: "1.0.0",
          }
        : gateway.handleRequestForTest(body, dependencies);
    response.writeHead(200, {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    });
    response.end(JSON.stringify(result));
  });
});

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(
    `CareerOS synthetic gateway listening on http://127.0.0.1:${PORT}/exec\n`,
  );
});
