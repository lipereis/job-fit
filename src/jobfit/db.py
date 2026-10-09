"""SQLite storage for postings and their analyses."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    published   TEXT NOT NULL DEFAULT '',
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
    job_id   TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    profile  TEXT NOT NULL,
    score    INTEGER NOT NULL,
    eligible INTEGER NOT NULL,
    detail   TEXT NOT NULL,
    PRIMARY KEY (job_id, profile)
);
CREATE TABLE IF NOT EXISTS required_skills (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill  TEXT NOT NULL,
    kind   TEXT NOT NULL CHECK (kind IN ('required', 'nice')),
    PRIMARY KEY (job_id, skill)
);
CREATE INDEX IF NOT EXISTS idx_analyses_score ON analyses(profile, eligible, score DESC);
CREATE INDEX IF NOT EXISTS idx_required_skill ON required_skills(skill);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_jobs(conn: sqlite3.Connection, jobs: list[dict]) -> int:
    """Insert postings not seen before; return how many were new."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO jobs (id, source, company, title, location, url, description, published, fetched_at) "
        "VALUES (:id, :source, :company, :title, :location, :url, :description, :published, :fetched_at)",
        [{"location": "", "url": "", "description": "", "published": "", **job, "fetched_at": now} for job in jobs],
    )
    conn.commit()
    return conn.total_changes - before


def save_analysis(conn: sqlite3.Connection, job_id: str, profile: str, fit, required: list[str], nice: list[str]) -> None:
    conn.execute("INSERT OR REPLACE INTO analyses (job_id, profile, score, eligible, detail) VALUES (?, ?, ?, ?, ?)",
                 (job_id, profile, fit.score, int(fit.eligible), json.dumps(fit.to_dict(), ensure_ascii=False)))
    conn.execute("DELETE FROM required_skills WHERE job_id = ?", (job_id,))
    conn.executemany("INSERT OR IGNORE INTO required_skills (job_id, skill, kind) VALUES (?, ?, ?)",
                     [(job_id, s, "required") for s in required] + [(job_id, s, "nice") for s in nice])


def ranked(conn: sqlite3.Connection, profile: str, minimum: int, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT j.id, j.company, j.title, j.location, j.url, a.score, a.detail FROM analyses a "
        "JOIN jobs j ON j.id = a.job_id WHERE a.profile = ? AND a.eligible = 1 AND a.score >= ? "
        "ORDER BY a.score DESC, j.published DESC LIMIT ?", (profile, minimum, limit)).fetchall()


def companies_for_skill(conn: sqlite3.Connection, skill: str) -> list[sqlite3.Row]:
    """Companies ranked by how many of their postings ask for a skill.

    Each row has the company, the postings that mention the skill, how many of those list it as
    required rather than nice to have, and all the postings the company has in the database.
    """
    return conn.execute(
        """
        SELECT j.company,
               COUNT(*) AS jobs,
               SUM(CASE WHEN r.kind = 'required' THEN 1 ELSE 0 END) AS required,
               t.total
        FROM required_skills AS r
        JOIN jobs AS j ON j.id = r.job_id
        JOIN (SELECT company, COUNT(*) AS total FROM jobs GROUP BY company) AS t ON t.company = j.company
        WHERE r.skill = ? COLLATE NOCASE
        GROUP BY j.company
        ORDER BY jobs DESC, j.company
        """, (skill,)).fetchall()


def skill_demand(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """How many postings require each skill, and what share of all analysed postings that is."""
    return conn.execute(
        "SELECT skill, COUNT(*) AS jobs, "
        "ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT job_id) FROM required_skills), 1) AS share "
        "FROM required_skills WHERE kind = 'required' GROUP BY skill ORDER BY jobs DESC").fetchall()
