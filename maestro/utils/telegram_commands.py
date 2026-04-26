import re

SPACE_RE = re.compile(r"\s+")

_KNOWN_SOURCES = {"tavily", "google", "maps", "hunter", "apollo", "apify", "perplexity"}
_SOURCE_ALIASES = {"maps": "google"}


def parse_prospect_web_command(text: str) -> dict[str, str] | None:
    """Parse 'prospect web [source] [target]'.

    Returns {"source": str, "target": str} or None if not a prospect web command.
    source defaults to "tavily". target may be empty (caller should prompt).
    """
    normalized = SPACE_RE.sub(" ", text.replace(" ", " ")).strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    parts = normalized.split(" ")
    if parts:
        parts[0] = parts[0].split("@", 1)[0]
    folded = [part.casefold() for part in parts]
    if len(folded) < 2 or folded[0] not in {"prospect", "prospectar"} or folded[1] != "web":
        return None

    rest = parts[2:]
    source = "tavily"
    if rest and rest[0].casefold() in _KNOWN_SOURCES:
        raw = rest[0].casefold()
        source = _SOURCE_ALIASES.get(raw, raw)
        rest = rest[1:]

    return {"source": source, "target": " ".join(rest).strip()}
