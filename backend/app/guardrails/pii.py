import re

# Order matters: card before SSN/phone (longest digit runs first), SSN before
# phone (xxx-xx-xxxx would otherwise partially match the phone pattern).
_CARD_RE = re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Phones require separators/parens/+ so bare 10-digit identifiers (policy or
# claim numbers) aren't swallowed.
_PHONE_RE = re.compile(r"(?:\+\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")


def redact_pii(text: str) -> str:
    text = _CARD_RE.sub("[REDACTED_CARD]", text)
    text = _SSN_RE.sub("[REDACTED_SSN]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    return text
