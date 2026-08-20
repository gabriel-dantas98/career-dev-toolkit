var GATEWAY_VERSION = "1.0.0";
var MAX_REQUEST_BYTES = 256 * 1024;
var MAX_CLOCK_SKEW_SECONDS = 300;
var NONCE_TTL_SECONDS = 600;
var MAX_RESULTS = 50;
var MAX_WINDOW_MS = 366 * 24 * 60 * 60 * 1000;
var MAX_QUERY_LENGTH = 200;
var MAX_DOC_CHARS = 8000;
var MAX_SHEET_READ_CELLS = 500;
var MAX_BRAGSHEET_ROWS = 200;
var MAX_BRAGSHEET_COLUMNS = 12;
var MAX_CELL_CHARS = 8000;
var MAX_SHEET_ROWS = 1000000;
var MAX_SHEET_COLUMNS = 18278;

var ALLOWED_ACTIONS = Object.freeze([
  "health",
  "calendar.search",
  "gmail.search",
  "drive.search",
  "docs.read",
  "sheets.read",
  "sheets.writeBragsheet",
  "sheets.readBack",
]);

function GatewayError(code, message) {
  this.name = "GatewayError";
  this.code = code;
  this.message = message;
}
GatewayError.prototype = Object.create(Error.prototype);
GatewayError.prototype.constructor = GatewayError;

function doPost(event) {
  var body =
    event && event.postData && typeof event.postData.contents === "string"
      ? event.postData.contents
      : "";
  return respond_(handleRequest_(body, runtimeDependencies_()));
}

function doGet() {
  return respond_(
    failureEnvelope_("", "METHOD_NOT_ALLOWED", "Use a JSON POST request.")
  );
}

function handleRequest_(body, dependencies) {
  var requestId = "";
  try {
    if (typeof body !== "string" || utf8Length_(body) > MAX_REQUEST_BYTES) {
      throw new GatewayError(
        "REQUEST_TOO_LARGE",
        "Request body exceeds the fixed limit."
      );
    }

    var request;
    try {
      request = JSON.parse(body);
    } catch (_parseError) {
      throw new GatewayError("INVALID_JSON", "Request body must be valid JSON.");
    }
    if (!request || Array.isArray(request) || typeof request !== "object") {
      throw new GatewayError(
        "INVALID_REQUEST",
        "Request body must be a JSON object."
      );
    }

    requestId = validateRequestId_(request.requestId);
    validateAction_(request.action);
    validateTimestamp_(request.timestamp, dependencies.nowMs());
    validateNonceAndPreventReplay_(request.nonce, dependencies);

    var data = dispatch_(request, dependencies);
    return successEnvelope_(requestId, data);
  } catch (error) {
    if (error instanceof GatewayError) {
      return failureEnvelope_(requestId, error.code, error.message);
    }
    return failureEnvelope_(
      requestId,
      "PROVIDER_ERROR",
      "The Google provider could not complete the bounded action."
    );
  }
}

function dispatch_(request, dependencies) {
  switch (request.action) {
    case "health":
      return { status: "healthy" };
    case "calendar.search":
      return calendarSearch_(request, dependencies);
    case "gmail.search":
      return gmailSearch_(request, dependencies);
    case "drive.search":
      return driveSearch_(request, dependencies);
    case "docs.read":
      return docsRead_(request, dependencies);
    case "sheets.read":
      return sheetsRead_(request, dependencies);
    case "sheets.writeBragsheet":
      return sheetsWriteBragsheet_(request, dependencies);
    case "sheets.readBack":
      return sheetsReadBack_(request, dependencies);
    default:
      throw new GatewayError(
        "ACTION_NOT_ALLOWED",
        "Action is not on the CareerOS allowlist."
      );
  }
}

function calendarSearch_(request, dependencies) {
  var window = validateSearch_(request);
  var calendarApi = dependencies.calendar || productionCalendar_();
  var options = {};
  if (request.query !== undefined) {
    options.search = validateQuery_(request.query, false);
  }
  var events = calendarApi
    .search(window.start, window.end, options)
    .slice(0, window.maxResults)
    .map(function (event) {
      return {
        id: String(event.getId()),
        summary: boundString_(event.getTitle(), 500),
        start: toIso_(event.getStartTime()),
        end: toIso_(event.getEndTime()),
      };
    });
  return { events: events };
}

function gmailSearch_(request, dependencies) {
  var window = validateSearch_(request);
  var query = validateGmailQuery_(request.query);
  var boundedQuery =
    query +
    " after:" +
    Math.floor(window.start.getTime() / 1000) +
    " before:" +
    Math.ceil(window.end.getTime() / 1000);
  var gmailApi = dependencies.gmail || productionGmail_();
  var messages = [];
  var threads = gmailApi.search(boundedQuery, 0, window.maxResults);

  for (var threadIndex = 0; threadIndex < threads.length; threadIndex += 1) {
    var threadMessages = threads[threadIndex].getMessages();
    for (
      var messageIndex = 0;
      messageIndex < threadMessages.length &&
      messages.length < window.maxResults;
      messageIndex += 1
    ) {
      var message = threadMessages[messageIndex];
      messages.push({
        id: String(message.getId()),
        subject: boundString_(message.getSubject(), 500),
        date: toIso_(message.getDate()),
        snippet: boundString_(message.getPlainBody(), 500),
      });
    }
  }
  return { messages: messages };
}

function driveSearch_(request, dependencies) {
  var window = validateSearch_(request);
  var query = escapeDriveQuery_(validateQuery_(request.query, true));
  var driveQuery =
    "trashed = false and fullText contains '" +
    query +
    "' and modifiedDate > '" +
    window.start.toISOString() +
    "' and modifiedDate < '" +
    window.end.toISOString() +
    "'";
  var driveApi = dependencies.drive || productionDrive_();
  var iterator = driveApi.search(driveQuery);
  var files = [];
  while (iterator.hasNext() && files.length < window.maxResults) {
    var file = iterator.next();
    files.push({
      id: String(file.getId()),
      name: boundString_(file.getName(), 500),
      mimeType: String(file.getMimeType()),
      modifiedTime: toIso_(file.getLastUpdated()),
    });
  }
  return { files: files };
}

function docsRead_(request, dependencies) {
  var documentId = validateResourceId_(
    request.documentId || request.resourceId,
    "documentId"
  );
  var docsApi = dependencies.docs || productionDocs_();
  var content = boundString_(docsApi.read(documentId), MAX_DOC_CHARS);
  return { resourceId: documentId, content: content };
}

function sheetsRead_(request, dependencies) {
  var spreadsheetId = validateResourceId_(
    request.spreadsheetId || request.resourceId,
    "spreadsheetId"
  );
  var sheetName = validateSheetName_(request.sheetName);
  var bounds = parseA1Range_(request.range, MAX_SHEET_READ_CELLS);
  var spreadsheetApi =
    dependencies.spreadsheet || productionSpreadsheet_();
  var values = spreadsheetApi.read(
    spreadsheetId,
    sheetName,
    bounds.normalized
  );
  return {
    resourceId: spreadsheetId,
    range: bounds.normalized,
    values: values,
  };
}

function sheetsWriteBragsheet_(request, dependencies) {
  var spreadsheetId = validateResourceId_(
    request.spreadsheetId,
    "spreadsheetId"
  );
  var sheetName = validateSheetName_(request.sheetName);
  var startRow = validateInteger_(
    request.startRow,
    1,
    MAX_SHEET_ROWS - MAX_BRAGSHEET_ROWS + 1,
    "START_ROW_OUT_OF_BOUNDS"
  );
  if (request.inputMode !== "RAW") {
    throw new GatewayError(
      "RAW_REQUIRED",
      "Brag-sheet writes require RAW input mode."
    );
  }
  var matrix = validateWriteMatrix_(request.values);
  if (startRow + matrix.rows - 1 > MAX_SHEET_ROWS) {
    throw new GatewayError(
      "WRITE_OUT_OF_BOUNDS",
      "Brag-sheet write exceeds sheet row bounds."
    );
  }

  var range =
    quoteSheetName_(sheetName) +
    "!A" +
    startRow +
    ":" +
    columnLabel_(matrix.columns) +
    (startRow + matrix.rows - 1);
  var sheetsApi = dependencies.sheets || productionSheets_();
  var ownedRange =
    quoteSheetName_(sheetName) +
    "!A" +
    startRow +
    ":" +
    columnLabel_(MAX_BRAGSHEET_COLUMNS) +
    (startRow + MAX_BRAGSHEET_ROWS - 1);
  sheetsApi.clear({}, spreadsheetId, ownedRange);
  sheetsApi.update(
    { values: request.values },
    spreadsheetId,
    range,
    { valueInputOption: "RAW" }
  );
  return {
    range: range,
    updatedRows: matrix.rows,
    updatedColumns: matrix.columns,
  };
}

function sheetsReadBack_(request, dependencies) {
  var spreadsheetId = validateResourceId_(
    request.spreadsheetId,
    "spreadsheetId"
  );
  var sheetName = validateSheetName_(request.sheetName);
  var startRow = validateInteger_(
    request.startRow,
    1,
    MAX_SHEET_ROWS,
    "READBACK_OUT_OF_BOUNDS"
  );
  var rowCount = validateInteger_(
    request.rowCount,
    1,
    MAX_BRAGSHEET_ROWS,
    "READBACK_OUT_OF_BOUNDS"
  );
  var columnCount = validateInteger_(
    request.columnCount,
    1,
    MAX_BRAGSHEET_COLUMNS,
    "READBACK_OUT_OF_BOUNDS"
  );
  if (startRow + rowCount - 1 > MAX_SHEET_ROWS) {
    throw new GatewayError(
      "READBACK_OUT_OF_BOUNDS",
      "Read-back exceeds sheet row bounds."
    );
  }
  var range =
    quoteSheetName_(sheetName) +
    "!A" +
    startRow +
    ":" +
    columnLabel_(columnCount) +
    (startRow + rowCount - 1);
  var sheetsApi = dependencies.sheets || productionSheets_();
  var response = sheetsApi.get(
    spreadsheetId,
    range,
    { valueRenderOption: "UNFORMATTED_VALUE" }
  );
  return {
    values: normalizeReadbackMatrix_(
      response && response.values,
      rowCount,
      columnCount
    ),
  };
}

function validateRequestId_(value) {
  if (
    typeof value !== "string" ||
    !/^[A-Za-z0-9._:-]{1,80}$/.test(value)
  ) {
    throw new GatewayError(
      "INVALID_REQUEST_ID",
      "requestId must be a bounded identifier."
    );
  }
  return value;
}

function validateAction_(action) {
  if (typeof action !== "string" || ALLOWED_ACTIONS.indexOf(action) === -1) {
    throw new GatewayError(
      "ACTION_NOT_ALLOWED",
      "Action is not on the CareerOS allowlist."
    );
  }
}

function validateTimestamp_(timestamp, nowMs) {
  if (
    typeof timestamp !== "number" ||
    !isFinite(timestamp) ||
    Math.floor(timestamp) !== timestamp ||
    Math.abs(Math.floor(nowMs / 1000) - timestamp) >
      MAX_CLOCK_SKEW_SECONDS
  ) {
    throw new GatewayError(
      "STALE_REQUEST",
      "Request timestamp is missing or outside the allowed window."
    );
  }
}

function validateNonceAndPreventReplay_(nonce, dependencies) {
  if (
    typeof nonce !== "string" ||
    !/^[A-Za-z0-9_-]{12,128}$/.test(nonce)
  ) {
    throw new GatewayError(
      "INVALID_NONCE",
      "nonce must be a bounded identifier."
    );
  }

  var lock = dependencies.lock;
  lock.waitLock(5000);
  try {
    var key = "careeros:nonce:" + nonce;
    if (dependencies.cache.get(key) !== null) {
      throw new GatewayError(
        "NONCE_REPLAYED",
        "Request nonce has already been used."
      );
    }
    dependencies.cache.put(key, "1", NONCE_TTL_SECONDS);
  } finally {
    lock.releaseLock();
  }
}

function validateSearch_(request) {
  var isoTimestamp =
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/;
  var startMs = Date.parse(request.timeMin);
  var endMs = Date.parse(request.timeMax);
  if (
    typeof request.timeMin !== "string" ||
    typeof request.timeMax !== "string" ||
    !isoTimestamp.test(request.timeMin) ||
    !isoTimestamp.test(request.timeMax) ||
    !isFinite(startMs) ||
    !isFinite(endMs) ||
    startMs >= endMs ||
    endMs - startMs > MAX_WINDOW_MS
  ) {
    throw new GatewayError(
      "INVALID_TIME_WINDOW",
      "Search requires a finite window of at most 366 days."
    );
  }
  var maxResults = validateInteger_(
    request.maxResults,
    1,
    MAX_RESULTS,
    "MAX_RESULTS_OUT_OF_BOUNDS"
  );
  return {
    start: new Date(startMs),
    end: new Date(endMs),
    maxResults: maxResults,
  };
}

function validateQuery_(value, required) {
  if (value === undefined && !required) {
    return "";
  }
  if (
    typeof value !== "string" ||
    (required && value.trim() === "") ||
    value.length > MAX_QUERY_LENGTH
  ) {
    throw new GatewayError(
      "INVALID_QUERY",
      "Search query is missing or exceeds the fixed limit."
    );
  }
  return value.trim();
}

function validateGmailQuery_(value) {
  var query = validateQuery_(value, true);
  if (
    /[(){}\[\]]/.test(query) ||
    /(^|\s)OR(?=\s|$)/i.test(query)
  ) {
    throw new GatewayError(
      "INVALID_QUERY",
      "Gmail query contains unsupported grouping or OR syntax."
    );
  }
  return query;
}

function validateResourceId_(value, fieldName) {
  if (
    typeof value !== "string" ||
    !/^[A-Za-z0-9_-]{6,200}$/.test(value)
  ) {
    throw new GatewayError(
      "INVALID_RESOURCE_ID",
      fieldName + " must be an explicit Google resource ID."
    );
  }
  return value;
}

function validateSheetName_(value) {
  if (
    typeof value !== "string" ||
    value.trim() === "" ||
    value.length > 100 ||
    /[\u0000-\u001F]/.test(value)
  ) {
    throw new GatewayError(
      "INVALID_SHEET_NAME",
      "sheetName must be explicit and bounded."
    );
  }
  return value;
}

function validateInteger_(value, minimum, maximum, code) {
  if (
    typeof value !== "number" ||
    Math.floor(value) !== value ||
    value < minimum ||
    value > maximum
  ) {
    throw new GatewayError(code, "Numeric request bound is invalid.");
  }
  return value;
}

function parseA1Range_(value, maxCells) {
  if (typeof value !== "string") {
    throw new GatewayError(
      "RANGE_OUT_OF_BOUNDS",
      "A finite A1 range is required."
    );
  }
  var match = /^([A-Za-z]{1,3})([1-9][0-9]{0,6})(?::([A-Za-z]{1,3})([1-9][0-9]{0,6}))?$/.exec(
    value.trim()
  );
  if (!match) {
    throw new GatewayError(
      "RANGE_OUT_OF_BOUNDS",
      "Only finite rectangular A1 ranges are supported."
    );
  }
  var startColumn = columnNumber_(match[1]);
  var startRow = Number(match[2]);
  var endColumn = columnNumber_(match[3] || match[1]);
  var endRow = Number(match[4] || match[2]);
  if (
    startColumn > endColumn ||
    startRow > endRow ||
    endColumn > MAX_SHEET_COLUMNS ||
    endRow > MAX_SHEET_ROWS ||
    (endColumn - startColumn + 1) * (endRow - startRow + 1) > maxCells
  ) {
    throw new GatewayError(
      "RANGE_OUT_OF_BOUNDS",
      "Sheet range exceeds the fixed cell limit."
    );
  }
  return {
    normalized:
      columnLabel_(startColumn) +
      startRow +
      ":" +
      columnLabel_(endColumn) +
      endRow,
  };
}

function validateWriteMatrix_(values) {
  if (
    !Array.isArray(values) ||
    values.length < 1 ||
    values.length > MAX_BRAGSHEET_ROWS ||
    !Array.isArray(values[0]) ||
    values[0].length < 1 ||
    values[0].length > MAX_BRAGSHEET_COLUMNS
  ) {
    throw new GatewayError(
      "WRITE_OUT_OF_BOUNDS",
      "Brag-sheet values exceed fixed row or column limits."
    );
  }
  var columns = values[0].length;
  for (var rowIndex = 0; rowIndex < values.length; rowIndex += 1) {
    var row = values[rowIndex];
    if (!Array.isArray(row) || row.length !== columns) {
      throw new GatewayError(
        "INVALID_VALUES",
        "Brag-sheet values must be a rectangular matrix."
      );
    }
    for (var columnIndex = 0; columnIndex < row.length; columnIndex += 1) {
      validateCell_(row[columnIndex]);
    }
  }
  return { rows: values.length, columns: columns };
}

function validateCell_(value) {
  var validType =
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean";
  if (
    !validType ||
    (typeof value === "number" && !isFinite(value)) ||
    (typeof value === "string" && value.length > MAX_CELL_CHARS)
  ) {
    throw new GatewayError(
      "INVALID_VALUES",
      "Brag-sheet cells must be bounded scalar JSON values."
    );
  }
}

function normalizeReadbackMatrix_(values, rowCount, columnCount) {
  var source = Array.isArray(values) ? values : [];
  var normalized = [];
  for (var rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
    var sourceRow = Array.isArray(source[rowIndex]) ? source[rowIndex] : [];
    var row = [];
    for (var columnIndex = 0; columnIndex < columnCount; columnIndex += 1) {
      row.push(
        sourceRow[columnIndex] === undefined ? "" : sourceRow[columnIndex]
      );
    }
    normalized.push(row);
  }
  return normalized;
}

function columnNumber_(label) {
  var value = String(label).toUpperCase();
  var result = 0;
  for (var index = 0; index < value.length; index += 1) {
    result = result * 26 + value.charCodeAt(index) - 64;
  }
  return result;
}

function columnLabel_(number) {
  var value = number;
  var label = "";
  while (value > 0) {
    var remainder = (value - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    value = Math.floor((value - 1) / 26);
  }
  return label;
}

function quoteSheetName_(name) {
  return "'" + name.replace(/'/g, "''") + "'";
}

function boundString_(value, maximum) {
  return String(value || "").slice(0, maximum);
}

function toIso_(value) {
  return new Date(value).toISOString();
}

function escapeDriveQuery_(value) {
  return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function utf8Length_(value) {
  return unescape(encodeURIComponent(value)).length;
}

function successEnvelope_(requestId, data) {
  return {
    ok: true,
    requestId: requestId,
    data: data,
    errors: [],
    version: GATEWAY_VERSION,
  };
}

function failureEnvelope_(requestId, code, message) {
  return {
    ok: false,
    requestId: requestId,
    data: null,
    errors: [{ code: code, message: message }],
    version: GATEWAY_VERSION,
  };
}

function respond_(body) {
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(
    ContentService.MimeType.JSON
  );
}

function runtimeDependencies_() {
  return {
    nowMs: function () {
      return Date.now();
    },
    cache: CacheService.getScriptCache(),
    lock: LockService.getScriptLock(),
  };
}

function productionCalendar_() {
  return {
    search: function (start, end, options) {
      return CalendarApp.getDefaultCalendar().getEvents(start, end, options);
    },
  };
}

function productionGmail_() {
  return {
    search: function (query, start, maximum) {
      return GmailApp.search(query, start, maximum);
    },
  };
}

function productionDrive_() {
  return {
    search: function (query) {
      return DriveApp.searchFiles(query);
    },
  };
}

function productionDocs_() {
  return {
    read: function (documentId) {
      return DocumentApp.openById(documentId).getBody().getText();
    },
  };
}

function productionSpreadsheet_() {
  return {
    read: function (spreadsheetId, sheetName, range) {
      var spreadsheet = SpreadsheetApp.openById(spreadsheetId);
      var sheet = spreadsheet.getSheetByName(sheetName);
      if (!sheet) {
        throw new GatewayError("SHEET_NOT_FOUND", "Explicit sheet was not found.");
      }
      return sheet.getRange(range).getValues();
    },
  };
}

function productionSheets_() {
  return {
    clear: function (resource, spreadsheetId, range) {
      return Sheets.Spreadsheets.Values.clear(
        resource,
        spreadsheetId,
        range
      );
    },
    get: function (spreadsheetId, range, options) {
      return Sheets.Spreadsheets.Values.get(
        spreadsheetId,
        range,
        options
      );
    },
    update: function (resource, spreadsheetId, range, options) {
      return Sheets.Spreadsheets.Values.update(
        resource,
        spreadsheetId,
        range,
        options
      );
    },
  };
}

function handleRequestForTest(body, dependencies) {
  return handleRequest_(body, dependencies);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    ALLOWED_ACTIONS: ALLOWED_ACTIONS,
    handleRequestForTest: handleRequestForTest,
  };
}
