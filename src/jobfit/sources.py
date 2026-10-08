"""Job sources with public, documented APIs: company boards on Greenhouse, Lever and Ashby."""

import html
import json
import re
import time
import urllib.request
from importlib import resources
from typing import Callable

Fetch = Callable[[str], object]
USER_AGENT = "jobfit/0.1 (+https://github.com/lipereis/job-fit)"


def http_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", text or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def greenhouse(company: str, token: str, fetch: Fetch = http_json) -> list[dict]:
    data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    return [{"id": f"greenhouse-{token}-{j['id']}", "source": "greenhouse", "company": company,
             "title": j.get("title", "").strip(), "location": (j.get("location") or {}).get("name", ""),
             "url": j.get("absolute_url", ""), "description": strip_html(html.unescape(j.get("content", ""))),
             "published": (j.get("updated_at") or "")[:10]} for j in data.get("jobs", [])]


def lever(company: str, token: str, fetch: Fetch = http_json) -> list[dict]:
    data = fetch(f"https://api.lever.co/v0/postings/{token}?mode=json")
    jobs = []
    for j in data:
        created = j.get("createdAt")
        location = (j.get("categories") or {}).get("location", "")
        if j.get("workplaceType") == "remote" and "remote" not in location.lower():
            location = f"Remote, {location}".strip(", ")
        jobs.append({"id": f"lever-{token}-{j['id']}", "source": "lever", "company": company,
                     "title": j.get("text", "").strip(), "location": location, "url": j.get("hostedUrl", ""),
                     "description": j.get("descriptionPlain", "") + "\n" + "\n".join(
                         f"{block.get('text', '')}\n{strip_html(block.get('content', ''))}" for block in j.get("lists", [])),
                     "published": time.strftime("%Y-%m-%d", time.gmtime(created / 1000)) if created else ""})
    return jobs


def ashby(company: str, token: str, fetch: Fetch = http_json) -> list[dict]:
    data = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    jobs = []
    for j in data.get("jobs", []):
        places = [j.get("location") or ""] + [s.get("location") or "" for s in j.get("secondaryLocations", [])]
        location = " / ".join(p for p in places if p)
        if j.get("isRemote") and "remote" not in location.lower():
            location = f"Remote, {location}".strip(", ")
        jobs.append({"id": f"ashby-{token}-{j['id']}", "source": "ashby", "company": company,
                     "title": j.get("title", "").strip(), "location": location, "url": j.get("jobUrl", ""),
                     "description": j.get("descriptionPlain", ""), "published": (j.get("publishedAt") or "")[:10]})
    return jobs


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def default_boards() -> list[dict]:
    return json.loads(resources.files("jobfit.data").joinpath("boards.json").read_text(encoding="utf-8"))


def fetch_all(boards: list[dict], *, fetch: Fetch = http_json, pause: float = 1.0, log=print) -> list[dict]:
    """Read every board, one request each. A board that fails is reported and skipped."""
    jobs = []
    for board in boards:
        try:
            found = ADAPTERS[board["ats"]](board["company"], board["token"], fetch)
        except Exception as error:  # one board being down must not lose the rest
            log(f"  {board['company']}: failed ({error})")
            continue
        log(f"  {board['company']}: {len(found)} postings")
        jobs.extend(found)
        time.sleep(pause)
    return jobs


def filter_by_place(jobs: list[dict], pattern: str) -> list[dict]:
    regex = re.compile(pattern, re.I)
    return [job for job in jobs if regex.search(job.get("location", ""))]
