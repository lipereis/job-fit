"""API tests. They use a temporary database and the fictional profile; no network."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobfit import db
from jobfit.api import create_app
from jobfit.extract import extract
from jobfit.profile import Profile
from jobfit.score import score

ROOT = Path(__file__).parent.parent
PROFILE_PATH = ROOT / "eval" / "profile.json"
PROFILE = Profile.load(PROFILE_PATH)

JOBS = [
    {"id": "fit", "source": "x", "company": "Acme", "title": "Analista de Automação Júnior", "location": "Remoto",
     "url": "https://example.com/fit", "description": "Requisitos\n- Python\n- n8n\n- Git\n- APIs REST"},
    {"id": "out", "source": "x", "company": "Beta", "title": "SDR", "location": "Remoto",
     "url": "https://example.com/out", "description": "Requisitos\n- Prospecção\n- Salesforce"},
]


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "t.db"
    conn = db.connect(database)
    db.upsert_jobs(conn, JOBS)
    for job in JOBS:
        req = extract(job["title"], job["description"], job["location"])
        db.save_analysis(conn, job["id"], PROFILE.fingerprint(), score(req, PROFILE, job["location"], job["title"]),
                         req.required, req.nice)
    conn.commit()
    conn.close()
    return TestClient(create_app(database, PROFILE_PATH))


def test_health(client):
    assert client.get("/health").json()["ok"] is True


def test_score_explains_a_pasted_posting(client):
    body = client.post("/score", json={"title": "Dev Python Júnior", "location": "Remoto",
                                       "description": "Requisitos\n- Python\n- SQL\n- AWS"}).json()
    assert (body["have"], body["partial"], body["missing"]) == (["Python"], ["SQL"], ["AWS"])
    assert body["band"] == "stretch" and body["eligible"] is True and body["level_asked"] == "junior"


def test_score_rejects_an_empty_posting(client):
    assert client.post("/score", json={"title": "", "description": ""}).status_code == 422


def test_jobs_lists_only_postings_above_the_minimum(client):
    assert [j["id"] for j in client.get("/jobs").json()] == ["fit"]
    everything = client.get("/jobs", params={"min": 0}).json()
    assert [j["id"] for j in everything] == ["fit", "out"] and everything[0]["band"] == "fit"
    assert client.get("/jobs", params={"min": 101}).status_code == 422


def test_job_detail_and_missing_job(client):
    detail = client.get("/jobs/out").json()
    assert detail["company"] == "Beta" and set(detail["fit"]["missing"]) == {"CRM platforms", "Sales"}
    assert client.get("/jobs/nope").status_code == 404


def test_gaps_and_companies(client):
    gaps = {row["skill"]: row["status"] for row in client.get("/gaps").json()}
    assert gaps["Python"] == "have" and gaps["Sales"] == "missing"
    assert client.get("/companies", params={"skill": "python"}).json() == [
        {"company": "Acme", "jobs": 1, "required": 1, "total": 1}]
    assert client.get("/companies").status_code == 422


def test_missing_profile_is_reported_not_crashed(tmp_path):
    client = TestClient(create_app(tmp_path / "t.db", tmp_path / "absent.json"))
    response = client.post("/score", json={"title": "Dev", "description": "Python"})
    assert response.status_code == 503 and "jobfit profile" in response.json()["detail"]
