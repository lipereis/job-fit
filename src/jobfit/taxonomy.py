"""Skill taxonomy and whole-word matching."""

import json
import re
import unicodedata
from functools import lru_cache
from importlib import resources


def normalize(text: str) -> str:
    """Lowercase and strip accents, so 'Automação' and 'automacao' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


@lru_cache(maxsize=1)
def load_skills() -> dict[str, list[str]]:
    raw = json.loads(resources.files("jobfit.data").joinpath("skills.json").read_text(encoding="utf-8"))
    return {name: [normalize(alias) for alias in aliases] for name, aliases in raw["skills"].items()}


@lru_cache(maxsize=1)
def _patterns() -> dict[str, re.Pattern]:
    # Whole-word on both sides: "git" must not match "digital", nor "rest" match "interest".
    return {
        name: re.compile("|".join(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
                                  for alias in sorted(aliases, key=len, reverse=True)))
        for name, aliases in load_skills().items()
    }


def find_skills(text: str) -> dict[str, int]:
    """Skills mentioned in the text, with how many times each one appears."""
    normalized = normalize(text)
    counts = {name: len(pattern.findall(normalized)) for name, pattern in _patterns().items()}
    return {name: count for name, count in counts.items() if count}
