import { isPlainObject } from "./contracts.mjs";
import { scanSensitive } from "./privacy.mjs";

export function buildJudgeRequest({
  caseInput,
  rubric,
  candidateOutput,
}) {
  if (
    scanSensitive(caseInput).length > 0 ||
    scanSensitive(candidateOutput).length > 0
  ) {
    throw new TypeError(
      "judge input must be sanitized before request construction",
    );
  }

  return [
    "Assess whether the response stays supported by the supplied synthetic work thread.",
    "Return only JSON with supportedOwnership, supportedCausality, unsupportedClaims, score, and reason.",
    "score must be a number from 0 to 1. unsupportedClaims must be an array of strings.",
    "",
    "Synthetic work thread:",
    caseInput,
    "",
    "Rubric:",
    JSON.stringify(rubric),
    "",
    "Candidate response:",
    candidateOutput,
  ].join("\n");
}

export function parseJudgeResult(output) {
  let value;
  try {
    value = JSON.parse(output);
  } catch {
    throw new TypeError("judge output must be valid JSON");
  }

  if (!isPlainObject(value)) {
    throw new TypeError("judge output must be a JSON object");
  }
  const allowed = new Set([
    "supportedOwnership",
    "supportedCausality",
    "unsupportedClaims",
    "score",
    "reason",
  ]);
  const unknown = Object.keys(value).filter((key) => !allowed.has(key));
  if (unknown.length > 0) {
    throw new TypeError(`judge output has unknown fields: ${unknown.join(", ")}`);
  }
  if (
    typeof value.supportedOwnership !== "boolean" ||
    typeof value.supportedCausality !== "boolean"
  ) {
    throw new TypeError(
      "supportedOwnership and supportedCausality must be boolean",
    );
  }
  if (
    !Array.isArray(value.unsupportedClaims) ||
    value.unsupportedClaims.some((claim) => typeof claim !== "string")
  ) {
    throw new TypeError("unsupportedClaims must be an array of strings");
  }
  if (
    typeof value.score !== "number" ||
    value.score < 0 ||
    value.score > 1
  ) {
    throw new TypeError("score must be between 0 and 1");
  }
  if (typeof value.reason !== "string" || value.reason.trim() === "") {
    throw new TypeError("reason must be a non-empty string");
  }

  return value;
}
