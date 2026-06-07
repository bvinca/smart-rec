# CV date sanity checks - inconsistent, future, or implausible vs claimed experience.
# Recruiter flag only, not an auto score penalty.
# Severity: high = impossible, medium = suspicious, low = minor.
from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_PRESENT_TOKENS = ("present", "current", "now", "today", "ongoing")


def _current_year() -> int:
    return datetime.date.today().year


def _extract_year_range(duration: Optional[str]) -> Optional[Tuple[int, int]]:
    # Pull (start_year, end_year) out of free-text. Handles "2020-2024",
    # "2019 to present", "Mar 2018 - Aug 2022". A lone year + "present" gives
    # (year, current). A lone year alone = single-year stint (start == end).
    if not duration:
        return None
    text = duration.lower()
    years = [int(m.group(0)) for m in _YEAR_RE.finditer(text)]
    has_present = any(tok in text for tok in _PRESENT_TOKENS)

    if not years:
        return None
    if len(years) == 1:
        start = years[0]
        end = _current_year() if has_present else start
        return (min(start, end), max(start, end))

    start, end = years[0], years[1]
    if has_present and end < start:
        end = _current_year()
    return (min(start, end), max(start, end))


def _education_years(education: List[Dict[str, Any]]) -> List[int]:
    # every recognisable year across education entries
    out: List[int] = []
    for entry in education or []:
        # preprocessor's `year` field can be a bare year or a range string
        candidates = [str(entry.get("year") or "")]
        # the institution / degree strings sometimes carry the year too
        for fld in ("institution", "degree"):
            if entry.get(fld):
                candidates.append(str(entry[fld]))
        for blob in candidates:
            for m in _YEAR_RE.finditer(blob):
                out.append(int(m.group(0)))
    return out


def _ranges_overlap(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    # share at least one year
    return a[0] <= b[1] and b[0] <= a[1]


def _overlap_length(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    if not _ranges_overlap(a, b):
        return 0
    return min(a[1], b[1]) - max(a[0], b[0]) + 1


# checks

def _check_future_dates(
    education: List[Dict[str, Any]],
    work_ranges: List[Tuple[int, int]],
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    now = _current_year()
    for year in _education_years(education):
        if year > now:
            warnings.append({
                "severity": "high",
                "code": "future_education_year",
                "message": (
                    f"Education entry dated {year} is in the future "
                    f"(current year {now})."
                ),
            })
    for start, end in work_ranges:
        # +1yr is OK ("through 2026" for an ongoing contract); past that = suspicious
        if end > now + 1:
            warnings.append({
                "severity": "high",
                "code": "future_work_year",
                "message": (
                    f"Work entry dated through {end} is in the future "
                    f"(current year {now})."
                ),
            })
    return warnings


def _check_overlapping_roles(
    work_ranges: List[Tuple[int, int]],
) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for i in range(len(work_ranges)):
        for j in range(i + 1, len(work_ranges)):
            overlap = _overlap_length(work_ranges[i], work_ranges[j])
            # 1-year overlap = normal job transition. Flag 2+.
            if overlap >= 2:
                a, b = work_ranges[i], work_ranges[j]
                warnings.append({
                    "severity": "medium",
                    "code": "overlapping_roles",
                    "message": (
                        f"Two work entries overlap for {overlap} years: "
                        f"{a[0]}–{a[1]} and {b[0]}–{b[1]}. This is plausible "
                        f"for part-time / consulting work but unusual for two "
                        f"full-time roles."
                    ),
                })
    return warnings


def _check_experience_plausible(
    experience_years: float,
    work_ranges: List[Tuple[int, int]],
    education_years_list: List[int],
) -> List[Dict[str, Any]]:
    # claimed experience vs what the timeline actually supports
    # (1) claimed yrs >> union of work ranges, or (2) claimed yrs >> years since earliest education
    warnings: List[Dict[str, Any]] = []
    if experience_years <= 0:
        return warnings

    if work_ranges:
        union_years = _union_year_count(work_ranges)
        # Allow a generous tolerance: claimed up to 2 years more than
        # documented union is fine (often the CV is paraphrased).
        if experience_years > union_years + 2:
            warnings.append({
                "severity": "medium",
                "code": "experience_exceeds_work_history",
                "message": (
                    f"Claimed {experience_years:.1f} years of experience but "
                    f"work entries only cover {union_years} year(s) of "
                    f"timeline. This may indicate undocumented prior work "
                    f"or an inflated total."
                ),
            })
    elif experience_years >= 3.0:
        # No parsable work-experience entries at all, yet the candidate
        # claims a non-trivial total. This is more suspicious than the
        # case above, because there is *nothing* to corroborate the claim.
        warnings.append({
            "severity": "high",
            "code": "experience_exceeds_work_history",
            "message": (
                f"Claimed {experience_years:.1f} years of experience but no "
                f"work entries with parsable dates were extracted. Either "
                f"the CV has no employment history listed or the dates "
                f"could not be parsed."
            ),
        })

    if education_years_list:
        earliest = min(education_years_list)
        years_since_earliest = max(0, _current_year() - earliest)
        # If the candidate's earliest dated education was, say, 5 years ago
        # but they claim 15 years of experience, something is off.
        if experience_years > years_since_earliest + 3:
            warnings.append({
                "severity": "high",
                "code": "experience_exceeds_timeline",
                "message": (
                    f"Claimed {experience_years:.1f} years of experience but "
                    f"the earliest education entry is from {earliest} "
                    f"({years_since_earliest} years ago)."
                ),
            })
    return warnings


def _union_year_count(ranges: List[Tuple[int, int]]) -> int:
    # inclusive-year count of merged ranges
    if not ranges:
        return 0
    sorted_ranges = sorted(ranges)
    merged: List[List[int]] = [[*sorted_ranges[0]]]
    for start, end in sorted_ranges[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end - start + 1 for start, end in merged)


# entry point


def validate_timeline(parsed: Dict[str, Any]) -> Dict[str, Any]:
    # run all checks; returns {"warnings": [...]} - empty list = nothing flagged
    if not isinstance(parsed, dict):
        return {"warnings": []}

    education = parsed.get("education") or []
    work_experience = parsed.get("work_experience") or []
    experience_years = float(parsed.get("experience_years") or 0.0)

    work_ranges: List[Tuple[int, int]] = []
    for exp in work_experience:
        rng = _extract_year_range(exp.get("duration"))
        if rng:
            work_ranges.append(rng)

    education_years_list = _education_years(education)

    warnings: List[Dict[str, Any]] = []
    warnings.extend(_check_future_dates(education, work_ranges))
    warnings.extend(_check_overlapping_roles(work_ranges))
    warnings.extend(_check_experience_plausible(
        experience_years, work_ranges, education_years_list,
    ))

    return {"warnings": warnings}
