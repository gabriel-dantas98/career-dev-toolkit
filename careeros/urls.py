from __future__ import annotations

import re

_GOOGLE_EXEC_URL = (
    r"https://script\.google\.com/"
    r"(?:macros/s/[A-Za-z0-9_-]+|"
    r"a/macros/[A-Za-z0-9.-]+/s/[A-Za-z0-9_-]+)/exec"
)
_GOOGLE_EXEC_FULL = re.compile(rf"^{_GOOGLE_EXEC_URL}$")
_GOOGLE_EXEC_IN_TEXT = re.compile(
    rf"(?<![A-Za-z0-9]){_GOOGLE_EXEC_URL}(?![A-Za-z0-9_./?#:-])"
)


def validate_google_exec_url(value: str) -> str:
    if not isinstance(value, str) or _GOOGLE_EXEC_FULL.fullmatch(value) is None:
        raise ValueError(
            "web_app_url must be an exact Google Apps Script /macros/.../exec URL"
        )
    return value


def google_exec_urls_in_text(value: str) -> tuple[str, ...]:
    matches = tuple(dict.fromkeys(_GOOGLE_EXEC_IN_TEXT.findall(value)))
    return tuple(validate_google_exec_url(match) for match in matches)
