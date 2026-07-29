const PATTERNS = [
  {
    category: "private-key",
    regex:
      /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g,
  },
  {
    category: "authorization-header",
    regex: /Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]+/gi,
  },
  {
    category: "github-token",
    regex: /\bgh[pousr]_[A-Za-z0-9_]{12,}\b/g,
  },
  {
    category: "api-key",
    regex: /\bsk-[A-Za-z0-9_-]{12,}\b/g,
  },
  {
    category: "email",
    regex: /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
  },
];

export function scanSensitive(text) {
  const findings = [];

  for (const { category, regex } of PATTERNS) {
    regex.lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
      findings.push({
        category,
        start: match.index,
        end: match.index + match[0].length,
      });
      if (match[0].length === 0) regex.lastIndex += 1;
    }
  }

  return findings.sort((left, right) => left.start - right.start);
}

function publicFindings(findings) {
  return [
    ...new Set(findings.map((finding) => finding.category)),
  ].map((category) => ({ category }));
}

export function privacyPreflight(_definition, input) {
  const findings = scanSensitive(input);
  if (findings.length === 0) {
    return { status: "completed", findings: [] };
  }

  return {
    status: "blocked",
    findings: publicFindings(findings),
  };
}

function replaceLiteral(text, value, replacement) {
  if (typeof value !== "string" || value.length === 0) return text;
  return text.split(value).join(replacement);
}

export function sanitizeText(text, context = {}) {
  let sanitized = String(text);
  sanitized = replaceLiteral(sanitized, context.repoRoot, "<repo>");
  sanitized = replaceLiteral(sanitized, context.userHome, "<user-home>");

  for (const replacement of context.replacements ?? []) {
    sanitized = replaceLiteral(
      sanitized,
      replacement.value,
      replacement.replacement ?? `<redacted:${replacement.category}>`,
    );
  }

  const disabled = new Set(context.disabledCategories ?? []);
  const findings = scanSensitive(sanitized)
    .filter((finding) => !disabled.has(finding.category))
    .sort((left, right) => right.start - left.start);

  for (const finding of findings) {
    sanitized =
      sanitized.slice(0, finding.start) +
      `<redacted:${finding.category}>` +
      sanitized.slice(finding.end);
  }

  const remaining = scanSensitive(sanitized);
  if (remaining.length > 0) {
    throw new Error(
      `sanitization failed closed: ${publicFindings(remaining)
        .map((finding) => finding.category)
        .join(", ")}`,
    );
  }

  return {
    text: sanitized,
    findings: publicFindings(findings),
  };
}
