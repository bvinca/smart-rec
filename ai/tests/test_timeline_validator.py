# timeline / date sanity validator tests

from __future__ import annotations

import datetime
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.nlp.timeline_validator import (  # noqa: E402
    _extract_year_range,
    _union_year_count,
    validate_timeline,
)


CURRENT_YEAR = datetime.date.today().year


class TestYearRangeExtraction:
    def test_basic_dash_range(self):
        assert _extract_year_range("2020-2024") == (2020, 2024)

    def test_present_is_current_year(self):
        rng = _extract_year_range("2019 - present")
        assert rng == (2019, CURRENT_YEAR)

    def test_reversed_range_is_normalised(self):
        assert _extract_year_range("2024 - 2020") == (2020, 2024)

    def test_single_year(self):
        assert _extract_year_range("2021") == (2021, 2021)

    def test_with_months(self):
        assert _extract_year_range("Mar 2018 - Aug 2022") == (2018, 2022)

    def test_empty_returns_none(self):
        assert _extract_year_range("") is None
        assert _extract_year_range(None) is None
        assert _extract_year_range("permanent") is None


class TestUnionYearCount:
    def test_disjoint(self):
        assert _union_year_count([(2018, 2019), (2022, 2023)]) == 4

    def test_overlapping_merges(self):
        assert _union_year_count([(2018, 2021), (2020, 2023)]) == 6

    def test_adjacent_merges(self):
        assert _union_year_count([(2018, 2019), (2020, 2021)]) == 4

    def test_single_year_each(self):
        assert _union_year_count([(2020, 2020)]) == 1

    def test_empty(self):
        assert _union_year_count([]) == 0


class TestNoWarningsForCleanCV:
    def test_clean_cv_returns_empty_warnings(self):
        parsed = {
            "experience_years": 5.0,
            "education": [{"degree": "BSc CS", "institution": "Some Uni", "year": str(CURRENT_YEAR - 6)}],
            "work_experience": [
                {"title": "Engineer", "company": "Acme", "duration": f"{CURRENT_YEAR - 5} - {CURRENT_YEAR}",
                 "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        assert result["warnings"] == []


class TestFutureDates:
    def test_education_year_in_future_flagged(self):
        parsed = {
            "experience_years": 0.0,
            "education": [{"degree": "BSc", "institution": "Some Uni", "year": str(CURRENT_YEAR + 5)}],
            "work_experience": [],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "future_education_year" in codes

    def test_work_year_more_than_one_year_in_future_flagged(self):
        parsed = {
            "experience_years": 1.0,
            "education": [],
            "work_experience": [
                {"title": "Engineer", "company": "Acme", "duration": f"2020 - {CURRENT_YEAR + 5}",
                 "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "future_work_year" in codes


class TestOverlappingRoles:
    def test_two_year_overlap_flagged(self):
        parsed = {
            "experience_years": 5.0,
            "education": [],
            "work_experience": [
                {"title": "Engineer", "company": "A", "duration": "2018-2022", "description": ""},
                {"title": "Engineer", "company": "B", "duration": "2020-2023", "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "overlapping_roles" in codes

    def test_one_year_overlap_not_flagged(self):
        parsed = {
            "experience_years": 5.0,
            "education": [],
            "work_experience": [
                # one-year overlap is normal when switching jobs
                {"title": "Engineer", "company": "A", "duration": "2018-2021", "description": ""},
                {"title": "Engineer", "company": "B", "duration": "2021-2023", "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "overlapping_roles" not in codes


class TestExperiencePlausibility:
    def test_claimed_far_exceeds_work_history(self):
        parsed = {
            "experience_years": 10.0,
            "education": [],
            "work_experience": [
                {"title": "Engineer", "company": "A", "duration": "2022-2024", "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "experience_exceeds_work_history" in codes

    def test_claimed_within_tolerance_not_flagged(self):
        parsed = {
            "experience_years": 4.0,
            "education": [],
            "work_experience": [
                {"title": "Engineer", "company": "A", "duration": "2020-2023", "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "experience_exceeds_work_history" not in codes

    def test_claimed_exceeds_education_timeline(self):
        # earliest edu 5 yrs ago but claims 15 yrs experience
        parsed = {
            "experience_years": 15.0,
            "education": [{"degree": "BSc", "institution": "X", "year": str(CURRENT_YEAR - 5)}],
            "work_experience": [
                {"title": "Engineer", "company": "A", "duration": f"{CURRENT_YEAR - 4} - {CURRENT_YEAR}",
                 "description": ""},
            ],
        }
        result = validate_timeline(parsed)
        codes = [w["code"] for w in result["warnings"]]
        assert "experience_exceeds_timeline" in codes


class TestEdgeCases:
    def test_empty_cv_returns_empty_warnings(self):
        result = validate_timeline({})
        assert result == {"warnings": []}

    def test_non_dict_input_returns_empty(self):
        result = validate_timeline("not a dict")  # type: ignore[arg-type]
        assert result == {"warnings": []}

    def test_missing_fields_treated_as_empty(self):
        result = validate_timeline({"experience_years": 0.0})
        assert result == {"warnings": []}
