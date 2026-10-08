"""Turn the free text of a job posting into structured requirements."""

import re
from dataclasses import dataclass, field

from .taxonomy import find_skills, normalize

LEVELS = ["intern", "junior", "mid", "senior", "lead"]

# A short line containing one of these starts a new section of the posting.
SECTION_MARKERS = {
    "required": ["requisitos", "o que esperamos", "o que buscamos", "o que voce precisa", "voce precisa ter",
                 "qualificacoes", "pre-requisitos", "requirements", "qualifications", "what you need",
                 "what you'll need", "what we're looking for", "what we are looking for", "must have", "must-have",
                 "you have", "about you", "habilidades necessarias", "conhecimentos necessarios", "obrigatorio",
                 "what you'll bring", "what you bring", "what you will bring", "who you are", "your profile",
                 "your skills", "skills and experience", "you'll need", "we're looking for", "o que procuramos",
                 "perfil desejado", "conhecimentos", "habilidades", "experiencias", "minimum qualifications",
                 "basic qualifications", "required skills", "essential"],
    "nice": ["diferenciais", "diferencial", "desejavel", "desejaveis", "sera um plus", "nice to have",
             "nice-to-have", "bonus", "preferred", "pluses", "good to have", "preferred qualifications",
             "bonus points", "extra points", "sera um diferencial", "seria um diferencial"],
    "duties": ["responsabilidades", "atribuicoes", "atividades", "suas responsabilidades", "sua missao",
               "o que voce vai fazer", "o que voce fara", "responsibilities", "what you'll do", "what you will do",
               "the role", "your mission", "day to day", "dia a dia"],
    "other": ["sobre a empresa", "sobre nos", "quem somos", "sobre o grupo", "about us", "about the company",
              "who we are", "beneficios", "benefits", "perks", "o que oferecemos", "what we offer",
              "localizacao", "location", "processo seletivo", "hiring process", "diversidade", "diversity"],
}

TITLE_LEVELS = [
    ("lead", ["lead", "lider", "leader", "head", "principal", "staff", "gerente", "manager", "coordenador",
              "coordenadora", "coordinator", "diretor", "director", "arquiteto", "architect", "vp", "chief"]),
    ("senior", ["senior", "sr", "especialista", "specialist iii", "iii"]),
    ("mid", ["pleno", "mid-level", "mid level", "midlevel", "pl", "ii"]),
    ("junior", ["junior", "jr", "trainee", "entry level", "entry-level", "associate", "i"]),
    ("intern", ["estagio", "estagiario", "estagiaria", "intern", "internship"]),
]
BODY_SENIOR = ["senioridade tecnica", "perfil senior", "nivel senior", "solida experiencia", "solida bagagem",
               "profundo conhecimento", "ampla experiencia", "vasta experiencia", "forte experiencia",
               "experiencia consistente", "extensive experience", "proven track record", "deep expertise",
               "strong experience"]
REMOTE_WORDS = ["remoto", "remota", "remote", "home office", "homeoffice", "trabalho remoto", "anywhere"]
ONSITE_WORDS = ["presencial", "on-site", "onsite", "hibrido", "hybrid"]


@dataclass
class Requirements:
    required: list[str] = field(default_factory=list)
    nice: list[str] = field(default_factory=list)
    level: str | None = None
    years: int | None = None
    remote: bool | None = None
    sectioned: bool = False  # False when the posting had no headings and everything was read as required
    title_skills: list[str] = field(default_factory=list)  # skills named in the title: the core of the job
    lines: int = 0  # requirement lines in the posting
    lines_read: int = 0  # of those, how many mention a skill the taxonomy knows


def split_sections(description: str) -> dict[str, str]:
    """Split a posting by its headings. Text before the first heading is the company intro."""
    sections = {name: [] for name in ("intro", "required", "nice", "duties", "other")}
    current = "intro"
    for line in description.splitlines():
        probe = normalize(line).strip(" :*-#•\t")
        if 0 < len(probe) <= 70:
            for name, markers in SECTION_MARKERS.items():
                if any(probe == m or probe.startswith(m + " ") or probe.startswith(m + ":") or probe.endswith(m)
                       for m in markers):
                    current = name
                    break
        sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def _word(text: str, word: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text) is not None


def detect_level(title: str, description: str) -> str | None:
    title_n = normalize(title)
    for level, words in TITLE_LEVELS:
        if any(_word(title_n, w) for w in words):
            return level
    if any(phrase in normalize(description) for phrase in BODY_SENIOR):
        return "senior"
    return None


def detect_years(description: str) -> int | None:
    found = [int(n) for n in re.findall(r"(\d{1,2})\s*\+?\s*(?:anos|years|yrs)", normalize(description))]
    found = [n for n in found if n <= 15]
    return max(found) if found else None


def requirement_lines(text: str) -> tuple[int, int]:
    """How many requirement lines there are, and how many of them the taxonomy can read."""
    lines = [line for line in text.splitlines() if len(normalize(line).strip(" :*-#•\t")) > 12]
    return len(lines), sum(1 for line in lines if find_skills(line))


def detect_remote(title: str, location: str, description: str) -> bool | None:
    place = normalize(title + " " + location)
    # the title and location are explicit; the body often says "remote" about the company, not the job
    if any(_word(place, w) for w in ONSITE_WORDS):
        return False
    if any(_word(place, w) for w in REMOTE_WORDS):
        return True
    head = normalize(description[:600])
    if any(_word(head, w) for w in REMOTE_WORDS):
        return True
    if any(_word(head, w) for w in ONSITE_WORDS):
        return False
    return None


def extract(title: str, description: str, location: str = "") -> Requirements:
    sections = split_sections(description)
    sectioned = bool(sections["required"].strip() or sections["nice"].strip())
    if sectioned:
        # What the person will do counts as required too, but the company blurb and benefits never do.
        required = find_skills(sections["required"] + "\n" + sections["duties"])
        nice = find_skills(sections["nice"])
    else:
        required = find_skills(sections["intro"] + "\n" + sections["duties"])
        nice = {}
    total, read = requirement_lines(sections["required"]) if sectioned else (0, 0)
    return Requirements(
        title_skills=sorted(find_skills(title)),
        lines=total,
        lines_read=read,
        required=sorted(required),
        nice=sorted(set(nice) - set(required)),
        level=detect_level(title, description),
        years=detect_years(sections["required"] or description),
        remote=detect_remote(title, location, description),
        sectioned=sectioned,
    )
