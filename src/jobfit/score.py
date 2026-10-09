"""Fit score: how much of what the posting asks for the profile covers.

score = 100 * (0.70 * required coverage + 0.15 * nice-to-have coverage + 0.15 * seniority fit)

A skill the profile has as 'strong' counts 1, 'basic' counts 0.5, missing counts 0. When the posting
lists no nice-to-haves, their weight goes to the required skills.

Three things cap the score below the cutoff however good the skill overlap is: the job is two or more
levels above the profile, a skill named in the job title is missing, or the title is outside the
roles the profile targets. Skill overlap alone made a senior product manager look like a match.

The scorer only sees requirements its taxonomy knows. When it recognizes fewer than two (three, if the
posting has no requirements section), or reads less than half of the requirement lines, it cannot
tell a good match from a posting it does not understand, so the score is capped below any sensible
cutoff and the reason is reported.
"""

import re

from dataclasses import asdict, dataclass, field

from .extract import LEVELS, Requirements
from .profile import Profile
from .taxonomy import normalize

WEIGHT_REQUIRED, WEIGHT_NICE, WEIGHT_LEVEL = 0.70, 0.15, 0.15
UNJUDGEABLE_CAP = 50
GATE_CAP = 45
MIN_REQUIREMENTS = 3
MIN_LINES_READ = 0.5
SKILL_VALUE = {"strong": 1.0, "basic": 0.5}


@dataclass
class Fit:
    score: int
    eligible: bool
    have: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    nice_have: list[str] = field(default_factory=list)
    nice_missing: list[str] = field(default_factory=list)
    level_fit: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _coverage(skills: list[str], profile: Profile) -> float:
    return sum(SKILL_VALUE.get(profile.skills.get(s, ""), 0.0) for s in skills) / len(skills)


def level_fit(req: Requirements, profile: Profile) -> tuple[float, list[str]]:
    notes = []
    if req.level is None:
        fit = 0.7  # unknown seniority: neither rewarded nor punished much
    else:
        gap = LEVELS.index(req.level) - LEVELS.index(profile.level)
        fit = 1.0 if gap <= 0 else 0.5 if gap == 1 else 0.0
        if gap > 0:
            notes.append(f"asks for {req.level}, profile is {profile.level}")
    if req.years is not None and req.years > profile.years + 1:
        fit *= 0.5
        notes.append(f"asks for {req.years}+ years, profile has {profile.years}")
    return fit, notes


def _names_another_place(part: str, profile: Profile) -> bool:
    """True when the text names somewhere beyond 'remote' and the regions the profile accepts."""
    for region in profile.remote_regions:
        part = part.replace(normalize(region), "")
    return bool(re.sub(r"remot[eoa]|home ?-?based|home ?office|[\s,/|()\-–—.]", "", part))


def eligibility(remote: bool | None, location: str, profile: Profile) -> tuple[bool, str]:
    """Can the person take this job where it is? A location may list alternatives; one that fits is enough."""
    place = normalize(location)
    if any(normalize(city) in place for city in profile.locations) and not profile.remote_only:
        return True, ""
    if remote is False:
        return False, f"on-site or hybrid outside the profile's locations ({location or 'unknown'})"
    parts = [p for p in re.split(r"[;/]", place) if p.strip()] or [place]
    if all(_names_another_place(part, profile) for part in parts):
        if remote:
            return False, f"remote, but for another region ({location})"
        # "São Paulo, Brazil" with no word about remote work: assume the office
        return False, f"names a place outside the profile's locations and does not say remote ({location})"
    return True, ""


def score(req: Requirements, profile: Profile, location: str = "", title: str = "") -> Fit:
    have = [s for s in req.required if profile.skills.get(s) == "strong"]
    partial = [s for s in req.required if profile.skills.get(s) == "basic"]
    missing = [s for s in req.required if s not in profile.skills]
    nice_have = [s for s in req.nice if s in profile.skills]
    nice_missing = [s for s in req.nice if s not in profile.skills]
    lvl, notes = level_fit(req, profile)

    if req.required:
        required_cov = _coverage(req.required, profile)
        if req.nice:
            raw = WEIGHT_REQUIRED * required_cov + WEIGHT_NICE * _coverage(req.nice, profile) + WEIGHT_LEVEL * lvl
        else:
            raw = (WEIGHT_REQUIRED + WEIGHT_NICE) * required_cov + WEIGHT_LEVEL * lvl
    else:
        raw = WEIGHT_LEVEL * lvl
    value = round(100 * raw)

    if len(req.required) < 2 or (len(req.required) < MIN_REQUIREMENTS and not req.sectioned):
        value = min(value, UNJUDGEABLE_CAP)
        notes.append("posting lists too few recognizable requirements to judge")
    elif req.lines >= 3 and req.lines_read / req.lines < MIN_LINES_READ:
        value = min(value, UNJUDGEABLE_CAP)
        notes.append(f"only {req.lines_read} of {req.lines} requirement lines mention a known skill; "
                     "the rest could not be read")
    if not req.sectioned:
        notes.append("posting has no clear requirements section; whole text was read as required")

    if req.level is not None and LEVELS.index(req.level) - LEVELS.index(profile.level) >= 2:
        value = min(value, GATE_CAP)
    # only when the posting also lists it: a title word alone ("Videomaker") is not a stated requirement
    core_missing = [s for s in req.title_skills if s in req.required and s not in profile.skills]
    if core_missing:
        value = min(value, GATE_CAP)
        notes.append("the title names a skill the profile lacks: " + ", ".join(core_missing))
    if profile.targets and title and not any(normalize(t) in normalize(title) for t in profile.targets):
        value = min(value, GATE_CAP)
        notes.append("title is outside the profile's target roles")

    eligible, reason = eligibility(req.remote, location, profile)
    if not eligible:
        notes.append(reason)
    return Fit(score=value, eligible=eligible, have=have, partial=partial, missing=missing,
               nice_have=nice_have, nice_missing=nice_missing, level_fit=lvl, notes=notes)
