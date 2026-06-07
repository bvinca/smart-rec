# Build the rater-B briefing kit from benchmark source data.
# Second annotator rates every (CV, job) pair 1-5 without seeing rater A's labels.
# Output: ai/benchmark/rater_b_kit/ - regenerable via:
#   python ai/benchmark/build_rater_b_kit.py
# Writes README.md, instructions.md, jobs.md, cvs.md, labels_rater_b.csv (blank template).
from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Tuple

HERE = os.path.abspath(os.path.dirname(__file__))
KIT_DIR = os.path.join(HERE, "rater_b_kit")

CVS_PATH = os.path.join(HERE, "cvs.json")
JOBS_PATH = os.path.join(HERE, "jobs.json")
LABELS_PATH = os.path.join(HERE, "labels.csv")


# load source JSON + label pairs

def _load() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Tuple[str, str]]]:
    with open(CVS_PATH, encoding="utf-8") as f:
        cvs = json.load(f)["cvs"]
    with open(JOBS_PATH, encoding="utf-8") as f:
        jobs = json.load(f)["jobs"]
    pairs: List[Tuple[str, str]] = []
    with open(LABELS_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for row in reader:
            pairs.append((row["cv_id"].strip(), row["job_id"].strip()))
    return cvs, jobs, pairs


# markdown / CSV renderers

def _readme(n_pairs: int) -> str:
    return f"""# Rater B briefing pack — SmartRecruiter benchmark

Thank you for agreeing to rate this corpus. Your independent ratings let the
dissertation report **inter-rater agreement** rather than a single annotator's
opinion, which is the single biggest methodological improvement available
to the evaluation chapter.

## What you have to do

1. Read `instructions.md` (5 minutes).
2. Read `jobs.md` there are 2 job descriptions.
3. Read `cvs.md` there are 24 CVs.
4. Fill in `labels_rater_b.csv` — one row per (CV, job) pair, total **{n_pairs} pairs**.
5. Send the filled CSV back to Bora.

## How long it takes

Plan for **60-90 minutes total**. Most raters spend ~1 minute per pair after
the initial read-through.

## Ground rules

* **Independent.** Do not look at rater A's ratings, results.md, the
  dissertation, or the codebase during your session. The whole point is
  independence.
* **No need to be expert.** A senior CS student or junior software
  professional is more than enough. The scale is "would I interview this
  candidate for this role" not "would I hire them".
* **Use your judgement.** There is no "correct" answer. Inter-rater
  agreement statistics only mean something if both raters rated honestly.

If you have a clarification question that does *not* reveal which CV or
job it is about, ask. Otherwise rate first, ask afterwards.

— Bora
"""


def _instructions() -> str:
    return """# Rating instructions

## The scale (1-5)

For every (CV, job) pair, ask yourself one question:

> **If I were the hiring recruiter for this job, would I pull this CV
> forward to an interview?**

Then pick the number that best matches your answer:

| Rating | Interpretation |
|--------|----------------|
| **5** | Excellent fit. Definite interview. I'd actively reach out. |
| **4** | Good fit. Likely interview. Some gaps but worth talking to. |
| **3** | Passable. Maybe interview if the pipeline is thin. Borderline. |
| **2** | Poor fit. Probably not interview. Wrong stack, wrong level, or wrong family. |
| **1** | Bad fit. Reject. Clear mismatch (wrong field, no relevant skills). |

The scale is **ordinal, not continuous**: a 5 is not "five times better
than a 1". The gap between 1 and 2 is not necessarily the same as the
gap between 4 and 5. That's OK; the statistics account for this.

## What counts as "fit"?

Think like a recruiter, not an HR system. You can consider:

* The candidate's actual skills, both formal and inferred from work history.
* Years of experience versus the level the job asks for.
* Whether the candidate's career trajectory makes the role a reasonable next step.
* Education only insofar as the job specifically asks for it.

**Do not** consider name, gender, nationality, or anything that looks
like a protected characteristic. The CVs were synthesised to be neutral
on these but treat them as if they were real.

## Common patterns you will see

The corpus is deliberately varied. You will encounter:

* Clean fits — the CV is exactly the kind of person the job is asking for.
* Career changers — strong adjacent skills but wrong primary background.
* Overqualified candidates — too senior for a mid role.
* Cross-family applications — backend engineer applying to a data
  analyst job, or vice versa.

There is no right answer for any of these. Rate as you see it.

## How to fill in the CSV

Open `labels_rater_b.csv` in any spreadsheet tool (or a text editor).
For each row:

* `cv_id` and `job_id` are pre-filled — leave them alone.
* `rater_B_rank` — your 1-5 rating for this pair.
* `notes` — optional, one short line if you want to record why.
  Anything is fine: "fits stack", "career changer", "overqualified",
  "wrong family". Notes are for you and Bora; they don't go in the
  dissertation.

Save as CSV (not XLSX). Send it back.

That's it. Thank you.
"""


def _jobs_md(jobs: List[Dict[str, Any]]) -> str:
    parts = ["# Jobs\n"]
    parts.append(f"There are **{len(jobs)} job descriptions** in this corpus. ")
    parts.append("You will rate every CV against every job (so every CV gets two ratings, one per job).\n")
    for job in jobs:
        parts.append(f"\n---\n\n## `{job['id']}` — {job['title']}\n")
        if job.get("description"):
            parts.append("**Description**\n\n")
            parts.append(job["description"].strip())
            parts.append("\n")
        if job.get("requirements"):
            parts.append("\n**Requirements**\n\n")
            parts.append(job["requirements"].strip())
            parts.append("\n")
    return "".join(parts) + "\n"


def _cvs_md(cvs: List[Dict[str, Any]]) -> str:
    parts = ["# CVs\n"]
    parts.append(f"There are **{len(cvs)} CVs** in this corpus.\n\n")
    parts.append("Each is synthetic. The `id` field is what appears in the labels CSV. ")
    parts.append("The seniority/family hint at the top is intentional — recruiters in a real ")
    parts.append("ATS see equivalent metadata from the job-board.\n")

    for cv in cvs:
        family = cv.get("family", "?")
        # tier lives in the id (e.g. be-mid-03 -> mid), not a separate field
        tier_hint = ""
        for tier in ("jun", "mid", "sen"):
            if f"-{tier}-" in cv["id"]:
                tier_hint = {"jun": "junior", "mid": "mid-level", "sen": "senior"}[tier]
                break
        meta = f"family: **{family}**"
        if tier_hint:
            meta += f"  ·  apparent level: **{tier_hint}**"
        if cv.get("true_yrs") is not None:
            meta += f"  ·  approx. years of experience: **{cv['true_yrs']}**"

        parts.append(f"\n---\n\n## `{cv['id']}`\n\n")
        parts.append(f"_{meta}_\n\n")
        if cv.get("resume_text"):
            parts.append("```\n")
            parts.append(cv["resume_text"].strip())
            parts.append("\n```\n")
    return "".join(parts) + "\n"


def _blank_template(pairs: List[Tuple[str, str]]) -> str:
    # blank CSV: cv_id, job_id, rater_B_rank, notes - no rater_A_rank (B works blind)
    lines = ["cv_id,job_id,rater_B_rank,notes"]
    lines.append("# Rater B template — please fill in rater_B_rank for every row (1-5).")
    lines.append("# Leave notes blank if you have nothing to add. Save as CSV.")
    lines.append("# Do not change cv_id or job_id. Do not look at rater A's labels.csv.")
    for cv_id, job_id in pairs:
        lines.append(f"{cv_id},{job_id},,")
    return "\n".join(lines) + "\n"


# entry point

def main() -> int:
    cvs, jobs, pairs = _load()

    os.makedirs(KIT_DIR, exist_ok=True)

    files = {
        "README.md": _readme(len(pairs)),
        "instructions.md": _instructions(),
        "jobs.md": _jobs_md(jobs),
        "cvs.md": _cvs_md(cvs),
        "labels_rater_b.csv": _blank_template(pairs),
    }
    for name, content in files.items():
        path = os.path.join(KIT_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  wrote {path}  ({len(content)} chars)")

    print()
    print(f"Kit ready at: {KIT_DIR}")
    print(f"Total (CV, job) pairs to rate: {len(pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
