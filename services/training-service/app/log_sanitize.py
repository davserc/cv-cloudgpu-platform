import re

_PATTERNS = [
    (re.compile(r"([?&]api_key=)[^&\s]+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(Authorization:\s*Bearer\s+)[^\s\"']+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(X-API-?Key[:=]\s*)[^\s\"']+", re.IGNORECASE), r"\1[REDACTED]"),
]


def sanitize_log_text(value: object) -> str:
    text = str(value)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
