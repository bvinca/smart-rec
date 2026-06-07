# Rating instructions

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
