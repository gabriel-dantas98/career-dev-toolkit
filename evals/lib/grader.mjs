import { scanSensitive } from "./privacy.mjs";

function normalize(value) {
  return String(value).toLowerCase().replace(/\s+/g, " ").trim();
}

function countMatches(text, regex) {
  return [...text.matchAll(regex)].length;
}

function numericClaims(text) {
  return [
    ...new Set(
      [...text.matchAll(/(?<![A-Za-z])\d+(?:\.\d+)?%?/g)].map(
        (match) => match[0],
      ),
    ),
  ];
}

function allowedNumbers(definition) {
  const values = new Set();
  for (const fact of definition.allowedFacts ?? []) {
    for (const claim of numericClaims(fact)) values.add(claim);
  }
  for (const metric of definition.allowedDerivedMetrics ?? []) {
    for (const claim of numericClaims(metric.value)) values.add(claim);
    for (const operand of metric.operands ?? []) values.add(String(operand));
  }
  return values;
}

function evaluateCriteria(definition, output) {
  const normalized = normalize(output);
  const deliveryCount = countMatches(output, /^###\s+.+$/gm);
  const starFields = Object.fromEntries(
    ["situation", "task", "action", "result"].map((field) => [
      field,
      countMatches(output, new RegExp(`^-\\s*${field}:`, "gim")),
    ]),
  );
  const allowed = allowedNumbers(definition);
  const unapprovedNumbers = numericClaims(output).filter(
    (claim) => !allowed.has(claim),
  );
  const forbiddenClaims = (definition.forbiddenClaims ?? []).filter((claim) =>
    normalized.includes(normalize(claim)),
  );
  const evidencePreserved = (definition.allowedFacts ?? []).every((fact) =>
    normalized.includes(normalize(fact)),
  );
  const expectedCount = definition.expectedDeliveryCount ?? 0;

  return {
    "star-structure":
      expectedCount === 0 ||
      Object.values(starFields).every((count) => count >= expectedCount),
    "delivery-count": deliveryCount === expectedCount,
    "at-most-one-question": countMatches(output, /\?/g) <= 1,
    "no-sensitive-output": scanSensitive(output).length === 0,
    "no-invented-numeric-claims": unapprovedNumbers.length === 0,
    "no-forbidden-claims": forbiddenClaims.length === 0,
    "evidence-preserved": evidencePreserved,
    "explicit-evidence-gap": /evidence gap:/i.test(output),
    "separate-deliveries": deliveryCount === expectedCount,
    "action-attribution":
      expectedCount === 0 ||
      countMatches(output, /^-\s*Action:\s*(?:I\b|The user\b)/gim) >=
        expectedCount,
  };
}

export function gradeOutput(definition, output) {
  const criteria = evaluateCriteria(definition, output);
  const criticalFailures = (definition.criticalCriteria ?? []).filter(
    (criterion) => criteria[criterion] !== true,
  );
  const weighted = definition.weightedCriteria ?? [];
  const totalWeight = weighted.reduce(
    (total, criterion) => total + criterion.weight,
    0,
  );
  const earnedWeight = weighted.reduce(
    (total, criterion) =>
      total + (criteria[criterion.id] === true ? criterion.weight : 0),
    0,
  );
  const score = totalWeight === 0 ? 1 : earnedWeight / totalWeight;

  return {
    passed: criticalFailures.length === 0 && score >= 0.85,
    score,
    criticalFailures,
    criteria,
  };
}
