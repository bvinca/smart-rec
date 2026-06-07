# Merge rater B's filled CSV into labels.csv.
# Usage: python ai/benchmark/merge_rater_b.py <filled_template.csv>
# Validates all pairs, ranks in [1,5]. Writes .bak before overwrite.
from __future__ import annotations

import csv
import os
import shutil
import sys
from typing import Dict, List, Tuple

HERE = os.path.abspath(os.path.dirname(__file__))
LABELS_PATH = os.path.join(HERE, "labels.csv")


def _read_labels(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    # Read labels.csv but keep the header + leading '#' comment block as preamble
    # so the rater-A instructions survive the round-trip.
    # Returns (preamble_lines, data_rows).
    preamble: List[str] = []
    data_rows: List[Dict[str, str]] = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        raise SystemExit("labels.csv is empty")
    header = lines[0].rstrip("\n")
    preamble.append(header)
    cols = [c.strip() for c in header.split(",")]

    body_started = False
    body_lines: List[str] = []
    for ln in lines[1:]:
        if not body_started and ln.lstrip().startswith("#"):
            preamble.append(ln.rstrip("\n"))
            continue
        body_started = True
        body_lines.append(ln)

    reader = csv.DictReader(body_lines, fieldnames=cols)
    for row in reader:
        data_rows.append(row)
    return preamble, data_rows


def _read_template(path: str) -> Dict[Tuple[str, str], Tuple[int, str]]:
    # parse + validate rater B's CSV into {(cv_id, job_id): (rank, notes)}
    out: Dict[Tuple[str, str], Tuple[int, str]] = {}
    errors: List[str] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for i, row in enumerate(reader, start=1):
            cv_id = (row.get("cv_id") or "").strip()
            job_id = (row.get("job_id") or "").strip()
            raw = (row.get("rater_B_rank") or "").strip()
            notes = (row.get("notes") or "").strip()
            if not cv_id or not job_id:
                errors.append(f"row {i}: missing cv_id or job_id")
                continue
            if not raw:
                errors.append(f"row {i} ({cv_id}, {job_id}): rater_B_rank is blank")
                continue
            try:
                rank = int(raw)
            except ValueError:
                errors.append(f"row {i} ({cv_id}, {job_id}): rater_B_rank '{raw}' is not an integer")
                continue
            if not 1 <= rank <= 5:
                errors.append(f"row {i} ({cv_id}, {job_id}): rater_B_rank {rank} is outside [1, 5]")
                continue
            out[(cv_id, job_id)] = (rank, notes)
    if errors:
        raise SystemExit("Validation failed in template:\n  - " + "\n  - ".join(errors))
    return out


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Usage: python merge_rater_b.py <path_to_filled_template.csv>", file=sys.stderr)
        return 2
    template_path = argv[1]
    if not os.path.exists(template_path):
        print(f"Template not found: {template_path}", file=sys.stderr)
        return 2

    preamble, data_rows = _read_labels(LABELS_PATH)
    rb = _read_template(template_path)

    label_keys = {(r["cv_id"].strip(), r["job_id"].strip()) for r in data_rows}
    missing_in_template = label_keys - set(rb.keys())
    extra_in_template = set(rb.keys()) - label_keys

    if missing_in_template:
        raise SystemExit(
            f"Template is missing {len(missing_in_template)} pair(s) that exist in "
            f"labels.csv (rater B must rate every pair). Examples: "
            f"{list(missing_in_template)[:5]}"
        )
    if extra_in_template:
        # not fatal - extra pairs in template, just warn
        print(f"Warning: template has {len(extra_in_template)} pair(s) not present "
              f"in labels.csv: {list(extra_in_template)[:5]}")

    # apply
    changed = 0
    for row in data_rows:
        key = (row["cv_id"].strip(), row["job_id"].strip())
        if key in rb:
            new_rank, new_note = rb[key]
            old = (row.get("rater_B_rank") or "").strip()
            if old != str(new_rank):
                row["rater_B_rank"] = str(new_rank)
                changed += 1
            # only fill notes when empty - keep rater A's notes intact
            if new_note and not (row.get("notes") or "").strip():
                row["notes"] = new_note

    # backup, then overwrite
    backup_path = LABELS_PATH + ".bak"
    shutil.copyfile(LABELS_PATH, backup_path)

    with open(LABELS_PATH, "w", encoding="utf-8", newline="") as f:
        for line in preamble:
            f.write(line + "\n")
        writer = csv.DictWriter(f, fieldnames=[c.strip() for c in preamble[0].split(",")])
        for row in data_rows:
            writer.writerow(row)

    print(f"Updated {changed} row(s) in {LABELS_PATH}")
    print(f"Backup saved to {backup_path}")
    print()
    print("Next: re-run the benchmark to compute inter-rater agreement and the")
    print("rater-A × rater-B confusion plot:")
    print()
    print("  python ai/benchmark/run_benchmark.py")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
