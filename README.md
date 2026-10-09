# jobfit

A command-line tool that scores job postings against your resume and shows, requirement by requirement, why.

Many postings I applied to looked right by the title. When I went back and read them properly, most asked for things I did not have. This tool does the reading first.

```
$ jobfit explain lever-acme-1234
Data Developer (AI / Automation) | Acme | Remote, Brazil

Score 45
Level asked: senior | years: not stated | remote: yes

Required
  MISSING  AWS
  have     Git
  MISSING  Microservices
  have     Python
  have     REST APIs
  have     SQL
  have     Workflow automation
Nice to have
  missing  Agent frameworks
  have     Automated testing
  have     LLM APIs
  have     RAG
note: asks for senior, profile is junior
```

## How it works

1. **Profile.** `jobfit profile resume.pdf` reads your resume and writes `profile.json`: each skill it finds, graded `strong` (mentioned in two or more places) or `basic`. You state your level and years yourself, and you can edit the file.
2. **Postings.** `jobfit fetch` reads company job boards through the public Greenhouse, Lever and Ashby APIs and stores them in SQLite. No scraping, no login.
3. **Requirements.** Each posting is split by its headings. Skills are read from the requirements and responsibilities; the company description and the benefits are ignored. "Nice to have" is kept separate.
4. **Score.** `100 × (0.70 × required coverage + 0.15 × nice-to-have coverage + 0.15 × seniority fit)`. A strong skill counts 1, a basic one 0.5, a missing one 0.
5. **Gates.** Three things cap the score below the cutoff whatever the overlap: the job is two or more levels above you, a skill named in the title is missing, or the title is outside the roles you said you want.
6. **Refusing to guess.** If the tool recognizes fewer than two requirements, or cannot read at least half of the requirement lines, it caps the score and says so instead of reporting a match.

There is no language model in the scoring. Every number can be traced to a line in the posting and a rule in [`score.py`](src/jobfit/score.py).

## Use it

```bash
pip install -e .
jobfit profile resume.pdf --level junior --years 1 --location "Rio de Janeiro" --target automa --target video
jobfit fetch
jobfit score --min 65
jobfit explain <job id>
jobfit gaps
```

`jobfit gaps` lists the skills the stored postings ask for most and whether you have each one. It is a plain SQL aggregate over the requirements table.

Skills and their aliases are in [`skills.json`](src/jobfit/data/skills.json), the boards in [`boards.json`](src/jobfit/data/boards.json). Both are meant to be edited.

## How I know whether it works

`jobfit eval eval/cases.jsonl` runs the scorer against 28 postings labelled "apply" or "skip" for the profile in `eval/profile.json`, and the test suite fails if the result drops.

| | |
|---|---|
| Accuracy | 26 of 28 (93%) |
| Precision | 8 of 8: nothing it recommends is labelled "skip" |
| Recall | 8 of 10: two postings labelled "apply" are scored below the cutoff |

What that number is worth:

- **The 28 postings are fictional.** I wrote them in the style of real ones, in Portuguese and English, and the labels are my own judgement. Real postings are copyrighted, so they are not in the repository.
- **Several cases exist because an earlier version got them wrong.** A junior customer-success role that was really debt collection once scored 70, because "digital" matched *Git* and "interesse" matched *REST*, and the title earned points on its own. The test set keeps those.
- **The two misses are left in on purpose.** One is a junior automation role where two minor gaps (Excel, English) sink the score, because every requirement weighs the same. The other is a support role where the title skill is missing but product knowledge is strong.

On real data the first version did much worse than on its own test set. I ran it on 1,917 postings from 38 boards and it recommended twelve, including a senior product manager, a market-risk analyst and a Java role with no Java. The causes were all things the fictional set had not covered: seniority carried only 15% of the score, the title was ignored, "Remote, San Francisco" passed as remote, and a posting with two recognized skills out of twenty requirement lines scored 100. Each became a rule and a test. After that the same 1,917 postings produced one recommendation.

Building a sample of real postings to label by hand then showed a fifth: a location such as "São Paulo, Brazil", with no word about remote work, was being treated as open to anyone. It is now read as the office.

## Limits

- It only sees skills listed in `skills.json` (70 of them). A requirement outside that list is invisible, which is why it refuses to judge postings it mostly cannot read.
- It does not understand seniority that is only implied. A posting that never says "senior" or a number of years is treated as open to anyone.
- Every requirement weighs the same.
- The resume reader counts mentions, so it is generous: a skill named in two project descriptions becomes "strong". Check `profile.json` after generating it.
- Headings in unusual wording are missed, and the whole posting is then read as requirements. The output says when that happens.
- I have not yet measured it against a labelled set of real postings. That is the next step, along with tracking which applications get a reply.
