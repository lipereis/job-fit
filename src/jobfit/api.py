"""HTTP API over the same scorer and database the command line uses.

Run it with `jobfit serve`. Interactive documentation is served at /docs.
"""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from . import __version__, db
from .extract import extract
from .profile import Profile
from .score import STRETCH, band, score


class Posting(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=50_000)
    location: str = Field(default="", max_length=300)


class FitOut(BaseModel):
    score: int
    band: str
    eligible: bool
    level_asked: str | None
    years_asked: int | None
    have: list[str]
    partial: list[str]
    missing: list[str]
    nice_have: list[str]
    nice_missing: list[str]
    notes: list[str]


class JobOut(BaseModel):
    id: str
    company: str
    title: str
    location: str
    url: str
    score: int
    band: str


class JobDetail(JobOut):
    fit: FitOut


class SkillDemand(BaseModel):
    skill: str
    jobs: int
    share: float
    status: str


class CompanyDemand(BaseModel):
    company: str
    jobs: int
    required: int
    total: int


def _fit_out(req, fit) -> FitOut:
    return FitOut(score=fit.score, band=band(fit.score), eligible=fit.eligible, level_asked=req.level,
                  years_asked=req.years, have=fit.have, partial=fit.partial, missing=fit.missing,
                  nice_have=fit.nice_have, nice_missing=fit.nice_missing, notes=fit.notes)


def create_app(db_path: str | Path = "jobfit.db", profile_path: str | Path = "profile.json") -> FastAPI:
    app = FastAPI(title="jobfit", version=__version__,
                  description="Score job postings against a resume, requirement by requirement.")

    def connection() -> Iterator[sqlite3.Connection]:
        # one connection per request: SQLite connections must not cross threads
        conn = db.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    def profile() -> Profile:
        path = Path(profile_path)
        if not path.is_file():
            raise HTTPException(503, f"No profile at {path}. Create one with 'jobfit profile resume.pdf'.")
        return Profile.load(path)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    @app.post("/score", response_model=FitOut, summary="Score a posting you paste in")
    def score_posting(posting: Posting, who: Profile = Depends(profile)) -> FitOut:
        req = extract(posting.title, posting.description, posting.location)
        return _fit_out(req, score(req, who, posting.location, posting.title))

    @app.get("/jobs", response_model=list[JobOut], summary="Stored postings, best first")
    def jobs(minimum: int = Query(STRETCH, ge=0, le=100, alias="min"), limit: int = Query(20, ge=1, le=200),
             who: Profile = Depends(profile), conn: sqlite3.Connection = Depends(connection)) -> list[JobOut]:
        rows = db.ranked(conn, who.fingerprint(), minimum, limit)
        return [JobOut(id=r["id"], company=r["company"], title=r["title"], location=r["location"], url=r["url"],
                       score=r["score"], band=band(r["score"])) for r in rows]

    @app.get("/jobs/{job_id}", response_model=JobDetail, summary="One posting, explained")
    def job(job_id: str, who: Profile = Depends(profile),
            conn: sqlite3.Connection = Depends(connection)) -> JobDetail:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, f"No posting with id {job_id}")
        req = extract(row["title"], row["description"], row["location"])
        fit = score(req, who, row["location"], row["title"])
        return JobDetail(id=row["id"], company=row["company"], title=row["title"], location=row["location"],
                         url=row["url"], score=fit.score, band=band(fit.score), fit=_fit_out(req, fit))

    @app.get("/gaps", response_model=list[SkillDemand], summary="Most requested skills and whether you have them")
    def gaps(limit: int = Query(20, ge=1, le=200), who: Profile = Depends(profile),
             conn: sqlite3.Connection = Depends(connection)) -> list[SkillDemand]:
        status = {"strong": "have", "basic": "partial"}
        return [SkillDemand(skill=r["skill"], jobs=r["jobs"], share=r["share"],
                            status=status.get(who.skills.get(r["skill"], ""), "missing"))
                for r in db.skill_demand(conn)[:limit]]

    @app.get("/companies", response_model=list[CompanyDemand], summary="Companies that ask for a skill most")
    def companies(skill: str = Query(min_length=1, max_length=80), limit: int = Query(15, ge=1, le=200),
                  conn: sqlite3.Connection = Depends(connection)) -> list[CompanyDemand]:
        return [CompanyDemand(company=r["company"], jobs=r["jobs"], required=r["required"], total=r["total"])
                for r in db.companies_for_skill(conn, skill)[:limit]]

    return app
