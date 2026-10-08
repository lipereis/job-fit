"""Measure the scorer against postings a person has already labelled 'apply' or 'skip'."""

import json
from dataclasses import dataclass
from pathlib import Path

from .extract import extract
from .profile import Profile
from .score import score


@dataclass
class Report:
    total: int
    correct: int
    true_apply: int
    false_apply: int
    false_skip: int
    true_skip: int
    misses: list[dict]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        """Of the postings the tool says to apply to, how many the person would apply to."""
        flagged = self.true_apply + self.false_apply
        return self.true_apply / flagged if flagged else 0.0

    @property
    def recall(self) -> float:
        """Of the postings the person would apply to, how many the tool finds."""
        wanted = self.true_apply + self.false_skip
        return self.true_apply / wanted if wanted else 0.0


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(cases: list[dict], profile: Profile, cutoff: int) -> Report:
    counts = {"true_apply": 0, "false_apply": 0, "false_skip": 0, "true_skip": 0}
    misses = []
    for case in cases:
        fit = score(extract(case["title"], case["description"], case.get("location", "")), profile,
                    case.get("location", ""), case["title"])
        predicted = "apply" if fit.eligible and fit.score >= cutoff else "skip"
        key = ("true_" if predicted == case["label"] else "false_") + predicted
        counts[key] += 1
        if predicted != case["label"]:
            misses.append({"id": case["id"], "title": case["title"], "label": case["label"], "predicted": predicted,
                           "score": fit.score, "missing": fit.missing, "notes": fit.notes})
    return Report(total=len(cases), correct=counts["true_apply"] + counts["true_skip"], misses=misses, **counts)
