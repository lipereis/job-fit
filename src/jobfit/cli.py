"""Command line: build a profile, fetch postings, score them, explain a score, evaluate the scorer."""

import argparse
import json
import sys
from pathlib import Path

from . import db
from .evaluate import evaluate, load_cases
from .extract import LEVELS, extract
from .profile import Profile, from_resume_text, read_resume
from .score import STRETCH, band, score
from .sources import default_boards, fetch_all, filter_by_place

DEFAULT_PLACES = r"remote|remoto|brazil|brasil|latam|latin america|worldwide|anywhere|global"


def cmd_profile(args) -> int:
    profile = from_resume_text(read_resume(Path(args.resume)), level=args.level, years=args.years)
    profile.remote_only = args.remote_only
    profile.locations = args.location or []
    profile.targets = args.target or []
    profile.save(Path(args.profile))
    strong = [s for s, v in profile.skills.items() if v == "strong"]
    basic = [s for s, v in profile.skills.items() if v == "basic"]
    print(f"Profile written to {args.profile} ({profile.level}, {profile.years} years)")
    print(f"  strong ({len(strong)}): {', '.join(strong) or '-'}")
    print(f"  basic  ({len(basic)}): {', '.join(basic) or '-'}")
    print("Edit the file to correct anything the resume does not show.")
    return 0


def cmd_fetch(args) -> int:
    boards = json.loads(Path(args.boards).read_text(encoding="utf-8")) if args.boards else default_boards()
    print(f"Reading {len(boards)} boards...")
    jobs = filter_by_place(fetch_all(boards, pause=args.pause), args.places)
    conn = db.connect(args.db)
    new = db.upsert_jobs(conn, jobs)
    print(f"{len(jobs)} postings match the location filter, {new} new.")
    return 0


def cmd_score(args) -> int:
    profile = Profile.load(Path(args.profile))
    conn = db.connect(args.db)
    jobs = conn.execute("SELECT id, title, description, location FROM jobs").fetchall()
    for job in jobs:
        req = extract(job["title"], job["description"], job["location"])
        db.save_analysis(conn, job["id"], profile.fingerprint(),
                         score(req, profile, job["location"], job["title"]), req.required, req.nice)
    conn.commit()
    rows = db.ranked(conn, profile.fingerprint(), args.min, args.limit)
    fits = sum(1 for row in rows if band(row["score"]) == "fit")
    print(f"{len(jobs)} postings scored; {len(rows)} eligible at {args.min}+ "
          f"({fits} fit, {len(rows) - fits} stretch)")
    for row in rows:
        detail = json.loads(row["detail"])
        print(f"\n{row['score']:3d}  {band(row['score']):7s} {row['title']} | {row['company']} | {row['location']}")
        print(f"     has: {', '.join(detail['have'] + detail['partial']) or '-'}")
        print(f"     missing: {', '.join(detail['missing']) or '-'}")
        print(f"     {row['url']}   (jobfit explain {row['id']})")
    return 0


def cmd_explain(args) -> int:
    profile = Profile.load(Path(args.profile))
    conn = db.connect(args.db)
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (args.job_id,)).fetchone()
    if job is None:
        print(f"No posting with id {args.job_id}", file=sys.stderr)
        return 1
    req = extract(job["title"], job["description"], job["location"])
    fit = score(req, profile, job["location"], job["title"])
    print(f"{job['title']} | {job['company']} | {job['location']}\n{job['url']}\n")
    print(f"Score {fit.score} ({band(fit.score)})" + ("" if fit.eligible else "  (not eligible)"))
    print(f"Level asked: {req.level or 'not stated'} | years: {req.years or 'not stated'} | "
          f"remote: {'yes' if req.remote else 'no' if req.remote is False else 'not stated'}\n")
    print("Required")
    for skill in req.required:
        status = {"strong": "have", "basic": "partial"}.get(profile.skills.get(skill, ""), "MISSING")
        print(f"  {status:8s} {skill}")
    if req.nice:
        print("Nice to have")
        for skill in req.nice:
            print(f"  {'have' if skill in profile.skills else 'missing':8s} {skill}")
    for note in fit.notes:
        print(f"note: {note}")
    return 0


def cmd_gaps(args) -> int:
    profile = Profile.load(Path(args.profile))
    conn = db.connect(args.db)
    rows = db.skill_demand(conn)
    if not rows:
        print("Nothing scored yet. Run 'jobfit score' first.")
        return 1
    print("Most requested skills in the stored postings (share of postings that require each):")
    for row in rows[: args.limit]:
        status = {"strong": "have", "basic": "partial"}.get(profile.skills.get(row["skill"], ""), "MISSING")
        print(f"  {row['share']:5.1f}%  {row['jobs']:4d}  {status:8s} {row['skill']}")
    return 0


def cmd_companies(args) -> int:
    conn = db.connect(args.db)
    rows = db.companies_for_skill(conn, args.skill)
    if not rows:
        print(f"No stored posting asks for {args.skill!r}. Run 'jobfit score' first, "
              "and check the skill names with 'jobfit gaps'.")
        return 1
    print(f"Companies asking for {args.skill} (postings that mention it / all their postings):")
    for row in rows[: args.limit]:
        share = 100 * row["jobs"] / row["total"]
        print(f"  {row['jobs']:4d} / {row['total']:<4d} {share:5.1f}%  {row['company']}  "
              f"({row['required']} required, {row['jobs'] - row['required']} nice to have)")
    return 0


def cmd_eval(args) -> int:
    report = evaluate(load_cases(Path(args.cases)), Profile.load(Path(args.profile)), args.cutoff)
    print(f"{report.total} labelled postings, cutoff {args.cutoff}")
    print(f"  accuracy  {report.accuracy:.0%}   precision {report.precision:.0%}   recall {report.recall:.0%}")
    print(f"  apply/apply {report.true_apply}   apply/skip {report.false_skip}   "
          f"skip/apply {report.false_apply}   skip/skip {report.true_skip}   (label/predicted)")
    for miss in report.misses:
        print(f"  MISS {miss['id']}: labelled {miss['label']}, predicted {miss['predicted']} "
              f"(score {miss['score']}) {miss['title']}")
    return 0 if report.accuracy >= args.min_accuracy else 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="jobfit", description="Score job postings against your resume.")
    parser.add_argument("--db", default="jobfit.db", help="SQLite file (default: jobfit.db)")
    parser.add_argument("--profile", default="profile.json", help="profile file (default: profile.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("profile", help="build profile.json from a resume (PDF or text)")
    p.add_argument("resume")
    p.add_argument("--level", choices=LEVELS, default="junior")
    p.add_argument("--years", type=int, default=0, help="years of professional experience in the target area")
    p.add_argument("--remote-only", action="store_true")
    p.add_argument("--location", action="append", help="city you can work on-site in (repeatable)")
    p.add_argument("--target", action="append",
                   help="word that marks a role you want, matched against titles, e.g. automa (repeatable)")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("fetch", help="download postings from the company boards")
    p.add_argument("--boards", help="JSON file with boards (default: the bundled list)")
    p.add_argument("--places", default=DEFAULT_PLACES, help="regex a posting's location must match")
    p.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("score", help="score every stored posting and list the best")
    p.add_argument("--min", type=int, default=STRETCH,
                   help="lowest score to list (default: stretch and above; 65 lists only fits)")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("explain", help="show requirement by requirement why a posting got its score")
    p.add_argument("job_id")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("gaps", help="most requested skills in the stored postings, and whether you have them")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_gaps)

    p = sub.add_parser("companies", help="companies ranked by how many of their postings ask for a skill")
    p.add_argument("--skill", required=True, help="skill name as shown by 'jobfit gaps', e.g. Python")
    p.add_argument("--limit", type=int, default=15)
    p.set_defaults(func=cmd_companies)

    p = sub.add_parser("eval", help="measure the scorer against labelled postings")
    p.add_argument("cases", help="JSONL file: id, title, description, location, label (apply|skip)")
    p.add_argument("--cutoff", type=int, default=65)
    p.add_argument("--min-accuracy", type=float, default=0.0, help="exit with an error below this accuracy")
    p.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
