"""Output language guardrails (tech_requirements.md §16-§18).

The coaching output may name mechanical patterns and hedged muscular tendencies, but
must NEVER name a medical diagnosis as a conclusion or use prohibited phrasing. This
module provides a detector used by tests (and available to callers) to enforce that.

Note: mentioning a structure ("IT band", "knee") is allowed; naming the *syndrome*
as a diagnosis ("IT band syndrome") is not.
"""

from __future__ import annotations

import re
from typing import List

# Diagnosis names (§16) and prohibited phrasings (§18) — word-boundary, case-insensitive.
_PROHIBITED = [
    r"IT[\s-]?band syndrome", r"\bITBS\b",
    r"\bPFPS\b", r"patellofemoral", r"patellar tendinopathy",
    r"hip labral( tear)?", r"\bFAI\b",
    r"SI[\s-]?joint", r"sacroiliac", r"discogenic",
    r"hallux rigidus", r"achilles tendinopathy",
    r"tibial stress fracture", r"stress fracture", r"shin splints?", r"\bMTSS\b",
    r"foot drop", r"parkinson",
    r"this is causing your pain", r"you should stop running", r"\bdiagnos",
]
_PATTERNS = [re.compile(p, re.I) for p in _PROHIBITED]


def find_prohibited(text: str) -> List[str]:
    """Return the prohibited patterns found in `text` (empty if the text is clean)."""
    if not text:
        return []
    return [p.pattern for p in _PATTERNS if p.search(text)]


def scan_findings(items: List[dict]) -> List[str]:
    """Scan a list of feedback items' text fields; return any prohibited hits."""
    hits: List[str] = []
    for it in items:
        for field in ("title", "detail", "cue", "drill"):
            hits += find_prohibited(it.get(field, ""))
    return hits
