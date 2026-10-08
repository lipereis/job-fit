"""Unit tests. No network: the sources are given a fake fetch function."""
import json
from pathlib import Path

import pytest

from jobfit import db
from jobfit.cli import main
from jobfit.evaluate import evaluate, load_cases
from jobfit.extract import detect_level, extract, split_sections
from jobfit.profile import Profile, from_resume_text
from jobfit.score import UNJUDGEABLE_CAP, score
from jobfit.sources import ashby, fetch_all, filter_by_place, greenhouse, lever
from jobfit.taxonomy import find_skills

ROOT = Path(__file__).parent.parent
PROFILE = Profile.load(ROOT / "eval" / "profile.json")


def test_skills_match_whole_words_only():
    found = find_skills("Marketing digital, com interesse no restante do time.")
    assert "Git" not in found and "REST APIs" not in found
    assert set(find_skills("Usamos Git, APIs REST e automação com n8n.")) == {"Git", "REST APIs", "Workflow automation"}


def test_accents_and_case_do_not_matter():
    assert "Workflow automation" in find_skills("AUTOMAÇÃO DE PROCESSOS")
    assert "Video editing" in find_skills("edicao de video")


def test_company_blurb_and_benefits_are_not_requirements():
    posting = "Sobre nós\nUsamos Python e n8n todos os dias.\n\nRequisitos\n- Excel\n\nBenefícios\n- Curso de SQL"
    sections = split_sections(posting)
    assert "Python" in sections["other"] and "SQL" in sections["other"] and "Excel" in sections["required"]
    assert extract("Assistente", posting).required == ["Spreadsheets"]


def test_nice_to_haves_are_kept_apart_from_requirements():
    req = extract("Dev", "Requirements\n- Python\n\nNice to have\n- Docker\n- Python")
    assert req.required == ["Python"] and req.nice == ["Docker"]


def test_posting_without_headings_is_read_whole_and_flagged():
    req = extract("Dev Python", "Buscamos alguém com Python e SQL para o time.")
    assert req.required == ["Python", "SQL"] and req.sectioned is False


@pytest.mark.parametrize("title, body, expected", [
    ("Analista de Automação Júnior", "", "junior"),
    ("Senior AI Engineer", "", "senior"),
    ("Desenvolvedor Pleno", "", "mid"),
    ("Head of Content", "", "lead"),
    ("Data Developer", "Buscamos uma pessoa com senioridade técnica.", "senior"),
    ("Analista de Dados", "Time pequeno e colaborativo.", None),
])
def test_level_comes_from_the_title_then_from_the_text(title, body, expected):
    assert detect_level(title, body) == expected


def test_score_counts_strong_basic_and_missing_skills():
    req = extract("Analista Júnior", "Requisitos\n- Python\n- SQL\n- AWS")
    fit = score(req, PROFILE)
    assert (fit.have, fit.partial, fit.missing) == (["Python"], ["SQL"], ["AWS"])
    # coverage (1 + 0.5 + 0) / 3 = 0.5, weighted 0.85, plus full level fit 0.15
    assert fit.score == round(100 * (0.85 * 0.5 + 0.15))


def test_a_title_alone_never_reaches_the_cutoff():
    fit = score(extract("Analista de IA Júnior", "Procuramos uma pessoa proativa e curiosa."), PROFILE)
    assert fit.score <= UNJUDGEABLE_CAP and any("too few" in note for note in fit.notes)


def test_on_site_job_is_eligible_only_in_an_accepted_city():
    text = "Requisitos\n- Premiere\n- Reels"
    assert score(extract("Editor", text, "Rio de Janeiro (presencial)"), PROFILE, "Rio de Janeiro (presencial)").eligible
    assert not score(extract("Editor", text, "São Paulo (presencial)"), PROFILE, "São Paulo (presencial)").eligible
    assert score(extract("Editor", text, "Remoto"), PROFILE, "Remoto").eligible


def test_years_asked_beyond_the_profile_lower_the_level_fit():
    low = score(extract("Editor", "Requisitos\n- Premiere\n- Reels\n- 5 anos de experiência"), PROFILE)
    high = score(extract("Editor", "Requisitos\n- Premiere\n- Reels"), PROFILE)
    assert low.score < high.score and any("5+ years" in note for note in low.notes)


def test_profile_from_resume_grades_skills_by_how_often_they_appear():
    profile = from_resume_text("Skills: Python, SQL, Docker.\nProjects: an API in Python with FastAPI.", years=1)
    assert profile.skills["Python"] == "strong" and profile.skills["SQL"] == "basic"
    assert profile.level == "junior" and profile.years == 1


def test_profile_round_trips_through_its_file(tmp_path):
    PROFILE.save(tmp_path / "p.json")
    assert Profile.load(tmp_path / "p.json") == PROFILE


def test_each_source_is_mapped_to_the_common_shape():
    g = greenhouse("Acme", "acme", lambda url: {"jobs": [{"id": 1, "title": " Dev ", "location": {"name": "Remote, Brazil"},
                                                           "absolute_url": "u", "content": "&lt;p&gt;Python&lt;/p&gt;",
                                                           "updated_at": "2026-01-02T00:00:00"}]})
    le = lever("Acme", "acme", lambda url: [{"id": "a", "text": "Dev", "categories": {"location": "Brazil"},
                                             "workplaceType": "remote", "hostedUrl": "u", "descriptionPlain": "Python",
                                             "createdAt": 1767312000000, "lists": [{"text": "Requisitos", "content": "<li>SQL</li>"}]}])
    a = ashby("Acme", "acme", lambda url: {"jobs": [{"id": "z", "title": "Dev", "location": "Brazil", "isRemote": True,
                                                      "jobUrl": "u", "descriptionPlain": "Python",
                                                      "publishedAt": "2026-01-02T00:00:00"}]})
    assert g[0] == {"id": "greenhouse-acme-1", "source": "greenhouse", "company": "Acme", "title": "Dev",
                    "location": "Remote, Brazil", "url": "u", "description": "Python", "published": "2026-01-02"}
    assert le[0]["location"] == "Remote, Brazil" and "Requisitos\nSQL" in le[0]["description"]
    assert a[0]["location"] == "Remote, Brazil" and a[0]["published"] == "2026-01-02"


def test_a_failing_board_does_not_lose_the_others():
    def fetch(url):
        if "broken" in url:
            raise OSError("down")
        return {"jobs": [{"id": 1, "title": "Dev", "location": {"name": "Brazil"}}]}

    log = []
    jobs = fetch_all([{"company": "Broken", "ats": "greenhouse", "token": "broken"},
                      {"company": "Fine", "ats": "greenhouse", "token": "fine"}], fetch=fetch, pause=0, log=log.append)
    assert [j["company"] for j in jobs] == ["Fine"] and "failed" in log[0]
    assert filter_by_place(jobs + [{"location": "Berlin"}], "brazil|remote") == jobs


def test_database_stores_jobs_once_and_ranks_by_score(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    jobs = [{"id": "a", "source": "x", "company": "A", "title": "Analista de Automação Júnior", "location": "Remoto",
             "description": "Requisitos\n- Python\n- n8n\n- Git"},
            {"id": "b", "source": "x", "company": "B", "title": "SDR", "location": "Remoto",
             "description": "Requisitos\n- Prospecção\n- Salesforce"}]
    assert db.upsert_jobs(conn, jobs) == 2 and db.upsert_jobs(conn, jobs) == 0
    for job in jobs:
        req = extract(job["title"], job["description"], job["location"])
        db.save_analysis(conn, job["id"], "p1", score(req, PROFILE, job["location"]), req.required, req.nice)
    assert [row["id"] for row in db.ranked(conn, "p1", 65, 10)] == ["a"]
    demand = {row["skill"]: row["share"] for row in db.skill_demand(conn)}
    assert demand["Python"] == 50.0 and demand["Sales"] == 50.0


def test_cli_scores_and_explains_from_the_database(tmp_path, capsys):
    database, profile = str(tmp_path / "t.db"), str(ROOT / "eval" / "profile.json")
    db.upsert_jobs(db.connect(database), [{"id": "a", "source": "x", "company": "Acme", "title": "Dev Python Júnior",
                                           "location": "Remoto", "description": "Requisitos\n- Python\n- AWS"}])
    assert main(["--db", database, "--profile", profile, "score", "--min", "0"]) == 0
    assert main(["--db", database, "--profile", profile, "explain", "a"]) == 0
    out = capsys.readouterr().out
    assert "have     Python" in out and "MISSING  AWS" in out
    assert main(["--db", database, "--profile", profile, "explain", "nope"]) == 1


def test_labelled_set_stays_above_the_agreed_accuracy():
    """The regression gate: a rule change that breaks labelled cases fails the build."""
    report = evaluate(load_cases(ROOT / "eval" / "cases.jsonl"), PROFILE, cutoff=65)
    assert report.total == 28
    assert report.false_apply == 0, [m["id"] for m in report.misses]
    assert report.accuracy >= 0.9
    # the misses are documented in the README; if one gets fixed, update both
    assert [m["id"] for m in report.misses] == ["apply-support-video-saas", "hard-equal-weights"]


def test_gates_cap_the_score_whatever_the_skill_overlap():
    text = "Requirements\n- Python\n- REST APIs\n- Git\n- LLM APIs"
    assert score(extract("Junior Python Developer", text), PROFILE, title="Junior Python Developer").score >= 65
    senior = score(extract("Senior Product Manager", text), PROFILE, title="Senior Product Manager")
    assert senior.score <= 45
    java = score(extract("Junior Java Developer", text + "\n- Java"), PROFILE, title="Junior Java Developer")
    assert java.score <= 45 and any("title names a skill" in n for n in java.notes)
    other = score(extract("Fraud Analyst", text), PROFILE, title="Fraud Analyst")
    assert other.score <= 45 and any("outside the profile's target roles" in n for n in other.notes)


def test_a_title_word_that_is_not_a_stated_requirement_does_not_gate():
    text = "Requisitos\n- Premiere\n- Reels e TikTok\n- Redes sociais"
    fit = score(extract("Videomaker Júnior", text), PROFILE, title="Videomaker Júnior")
    assert fit.score >= 65 and not any("title names a skill" in n for n in fit.notes)


def test_remote_for_another_region_is_not_eligible():
    text = "Requirements\n- Python\n- Git\n- REST APIs"
    assert not score(extract("Dev", text, "Remote, San Francisco"), PROFILE, "Remote, San Francisco").eligible
    assert score(extract("Dev", text, "Remote, Brazil"), PROFILE, "Remote, Brazil").eligible
    assert score(extract("Dev", text, "Remote"), PROFILE, "Remote").eligible
    assert not score(extract("Dev (Híbrido/SP)", text, "São Paulo"), PROFILE, "São Paulo").eligible



def test_cases_file_matches_its_builder():
    built = json.loads((ROOT / "eval" / "cases.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert {"id", "title", "location", "label", "why", "description"} <= set(built)
