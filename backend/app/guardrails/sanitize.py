import re

# A document that contains a literal "</document>" could close the data fence
# early and promote the rest of its own text to instruction-level context —
# the structural half of prompt-injection resistance (the behavioral half is
# the prompts' "treat document text strictly as data" rule, eval-gated in M6).
_FENCE_BREAK_RE = re.compile(r"</\s*document\s*>", re.IGNORECASE)


def fence_document(text: str) -> str:
    """Wrap untrusted document text in a <document> fence that the text itself
    cannot break out of."""
    escaped = _FENCE_BREAK_RE.sub("[/document]", text)
    return f"<document>\n{escaped}\n</document>"
