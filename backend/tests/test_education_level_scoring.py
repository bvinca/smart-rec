# required_education_level scoring tests
# structured level on job vs text-mining fallback when unset

from __future__ import annotations

import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.scoring_service import ScoringService  # noqa: E402


@pytest.fixture(scope="module")
def svc() -> ScoringService:
    return ScoringService(db=None)


# job text with no degree keywords (avoids text-miner false positives)
JOB_NO_DEGREE_TEXT = "Looking for a great hire to join our growing team."

BACHELOR_CV = [{"degree": "BSc Computer Science", "institution": "Some University"}]
MASTER_CV = [{"degree": "MSc Software Engineering", "institution": "Some University"}]
PHD_CV = [{"degree": "PhD Computer Science", "institution": "Some University"}]
ASSOCIATE_CV = [{"degree": "Associate Degree in IT", "institution": "Local College"}]
NO_DEGREE_CV: list = []


class TestStructuredEducationRequirement:

    def test_meets_master_requirement(self, svc):
        score = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, "master")
        assert score >= 90

    def test_phd_overshoots_master_requirement(self, svc):
        score = svc._calculate_education_score(PHD_CV, JOB_NO_DEGREE_TEXT, "master")
        assert score >= 90

    def test_bachelor_one_below_master_requirement(self, svc):
        score = svc._calculate_education_score(BACHELOR_CV, JOB_NO_DEGREE_TEXT, "master")
        assert 65 <= score <= 75

    def test_associate_two_below_master_requirement(self, svc):
        score = svc._calculate_education_score(ASSOCIATE_CV, JOB_NO_DEGREE_TEXT, "master")
        assert 50 <= score <= 60

    def test_no_education_extracted_returns_neutral(self, svc):
        score = svc._calculate_education_score(NO_DEGREE_CV, JOB_NO_DEGREE_TEXT, "master")
        assert score == 40.0

    def test_phd_required_bachelor_candidate_falls_low(self, svc):
        score = svc._calculate_education_score(BACHELOR_CV, JOB_NO_DEGREE_TEXT, "phd")
        assert 50 <= score <= 60


class TestNoPreferenceFallback:

    def test_none_string_treated_as_no_preference(self, svc):
        score_none_str = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, "none")
        score_null = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, None)
        assert score_none_str == score_null

    def test_no_preference_no_degree_in_text_rewards_qualification(self, svc):
        score = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, None)
        assert score == pytest.approx(70.0, abs=0.5)

    def test_empty_string_normalised_to_no_preference(self, svc):
        score_empty = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, "")
        score_null = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, None)
        assert score_empty == score_null


class TestInvalidInput:
    def test_unknown_level_string_falls_through_to_text_path(self, svc):
        # garbage level string falls through to text mining, should not crash
        score = svc._calculate_education_score(MASTER_CV, JOB_NO_DEGREE_TEXT, "wizard")
        assert score >= 85
