"""Candidate profile: built from a resume, stored as an editable JSON file."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .extract import LEVELS
from .taxonomy import find_skills


@dataclass
class Profile:
    skills: dict[str, str] = field(default_factory=dict)  # skill -> "strong" | "basic"
    level: str = "junior"
    years: int = 0
    remote_only: bool = False
    locations: list[str] = field(default_factory=list)  # cities where on-site or hybrid work is fine
    # a remote job is eligible when it names one of these, or names no place at all
    remote_regions: list[str] = field(default_factory=lambda: ["brazil", "brasil", "latam", "latin america",
                                                               "worldwide", "anywhere", "global"])

    # words that mark the roles you are after, matched against the title ("automa" matches "Automação");
    # empty means every title is considered
    targets: list[str] = field(default_factory=list)

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Profile":
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def read_resume(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8")


def from_resume_text(text: str, level: str = "junior", years: int = 0) -> Profile:
    """A skill mentioned once is 'basic'; mentioned in two or more places it is 'strong'.

    Seniority is not inferred: a resume's dates mix study, freelance work and unrelated jobs,
    so the level and years of experience are stated by the candidate.
    """
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    skills = {name: ("strong" if count >= 2 else "basic") for name, count in find_skills(text).items()}
    return Profile(skills=dict(sorted(skills.items())), level=level, years=years)
