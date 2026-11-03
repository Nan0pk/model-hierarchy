"""Model-name reconciliation across sources (METHODOLOGY.md §12).

Arena reports display names ("Claude Opus 5.5 (High)"), OpenRouter reports
slugs ("anthropic/claude-opus-5.5"), benchmark pages report vendor names.
Matching is exact AFTER canonicalization + a user-maintained alias table
(config/models.yaml). No fuzzy matching on purpose: silent wrong merges are
worse than visible unmatched names.
"""

from __future__ import annotations

import pathlib
import re

try:  # optional file; the pipeline runs without it
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ALIAS_FILE = pathlib.Path(__file__).resolve().parent.parent / "config" / "models.yaml"


def _load_aliases() -> dict[str, str]:
    if yaml is None or not ALIAS_FILE.exists():
        return {}
    data = yaml.safe_load(ALIAS_FILE.read_text()) or {}
    return {str(k).strip().lower(): str(v).strip().lower() for k, v in (data.get("aliases") or {}).items()}


_ALIASES: dict[str, str] | None = None


def canonical(name: str) -> str:
    """lowercase -> drop provider prefix -> unify separators -> alias map."""
    global _ALIASES
    if _ALIASES is None:
        _ALIASES = _load_aliases()
    n = str(name).strip().lower()
    # OpenRouter IDs have a compact provider/model slug (e.g. openai/gpt-4o).
    # Do not treat slashes in human-readable dates like "(02/26)" as prefixes.
    if re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.:-]+", n):
        n = n.split("/", 1)[1]
    n = re.sub(r"[\s\-_]+", " ", n).strip()  # '.' stays: version syntax (5.5 ≠ 5 5)
    n = re.sub(r"\s+", " ", n)
    return _ALIASES.get(n, n)


def canonical_map(names) -> dict[str, str]:
    """{original_name: canonical_name} for a collection (for the report)."""
    return {str(n): canonical(n) for n in names}
