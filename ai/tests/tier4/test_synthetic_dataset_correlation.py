# tier 4: synthetic cv/jd correlation regression
# production ScoringService scores should track seniority labels (pearson r >= 0.6)
# uses real scorer, heuristic 40/40/20 path, no llm, no sbert dependency

from __future__ import annotations

import functools
import os
import sys
from typing import Any, Dict

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# backend scorer importable from ai/ or repo root
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# inline synthetic dataset, no external files

_JUNIOR_CV = {
    "level": "junior",
    "seniority_rank": 0,
    "skills": ["Python", "Flask", "PostgreSQL", "Git"],
    "experience_years": 1.0,
    "education": [{"degree": "Bachelor of Science in Computer Science"}],
    "resume_text": (
        "Junior Python developer with 1 year of experience. Built REST APIs "
        "with Flask and PostgreSQL, used Git and Docker. BSc Computer Science."
    ),
}

_MID_CV = {
    "level": "mid",
    "seniority_rank": 1,
    "skills": ["Python", "FastAPI", "PostgreSQL", "AWS", "Docker", "Kubernetes"],
    "experience_years": 4.0,
    "education": [{"degree": "MSc Software Engineering"}],
    "resume_text": (
        "Software engineer with 4 years of experience using Python, FastAPI, "
        "and PostgreSQL. Led microservices on AWS. MSc Software Engineering."
    ),
}

_SENIOR_CV = {
    "level": "senior",
    "seniority_rank": 2,
    "skills": ["Python", "FastAPI", "PostgreSQL", "AWS", "Kubernetes", "Terraform", "Microservices"],
    "experience_years": 9.0,
    "education": [{"degree": "MSc Computer Science"}],
    "resume_text": (
        "Senior backend engineer with 9 years. Designed and scaled FastAPI "
        "microservices, PostgreSQL, AWS, Kubernetes, Terraform. Tech lead, mentor. MSc."
    ),
}

_SENIOR_JD = {
    "title": "Senior Python Developer",
    "description": (
        "Senior Python developer with 5+ years. FastAPI, PostgreSQL, AWS, "
        "Kubernetes, Terraform, microservices. MSc preferred."
    ),
    "requirements": "5+ years Python, FastAPI, AWS, Kubernetes",
}

_JUNIOR_JD = {
    "title": "Junior Python Developer",
    "description": (
        "Junior Python developer role. Required: Python, Flask or FastAPI, "
        "PostgreSQL, Git. 1+ year experience. BSc preferred."
    ),
    "requirements": "1 year Python, Flask, PostgreSQL, Git",
}

SYNTHETIC_CVS = [_JUNIOR_CV, _MID_CV, _SENIOR_CV]


@functools.lru_cache(maxsize=1)
def _scoring_service():
    # one scorer per session; skip module if backend deps missing
    try:
        from app.services.scoring_service import ScoringService
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"Production ScoringService unavailable: {exc}")
    # db=None turns off embedding cache, fine for these tests
    return ScoringService(db=None)


def _score_candidate(cv: Dict[str, Any], jd: Dict[str, Any]) -> float:
    # production overall_score with adaptive weights + llm off
    service = _scoring_service()
    result = service.calculate_scores(
        resume_text=cv["resume_text"],
        job_description=jd["description"],
        job_requirements=jd.get("requirements", ""),
        applicant_skills=cv.get("skills", []),
        applicant_experience_years=cv.get("experience_years", 0.0),
        applicant_education=cv.get("education", []),
        applicant_work_experience=[],
        recruiter_id=None,
        job_id=None,
        use_adaptive_weights=False,
    )
    return float(result["overall_score"])


class TestSyntheticDatasetCorrelation:
    # scores should correlate with seniority rank

    def test_senior_beats_junior_on_senior_jd(self):
        # senior cv must outscore junior on senior jd
        senior_score = _score_candidate(_SENIOR_CV, _SENIOR_JD)
        junior_score = _score_candidate(_JUNIOR_CV, _SENIOR_JD)
        assert senior_score > junior_score, (
            f"Senior score ({senior_score:.1f}) should exceed junior score "
            f"({junior_score:.1f}) for a senior JD."
        )

    def test_junior_competitive_on_junior_jd(self):
        # junior should stay within 30 pts of senior on a junior jd
        junior_score = _score_candidate(_JUNIOR_CV, _JUNIOR_JD)
        senior_score = _score_candidate(_SENIOR_CV, _JUNIOR_JD)
        assert junior_score >= senior_score - 30, (
            f"Junior score ({junior_score:.1f}) is too far below senior score "
            f"({senior_score:.1f}) on a junior JD — experience weight too high."
        )

    def test_monotone_ordering_on_senior_jd(self):
        # scores non-decreasing with seniority on senior jd (5pt slack)
        scores = [(cv["seniority_rank"], _score_candidate(cv, _SENIOR_JD)) for cv in SYNTHETIC_CVS]
        scores.sort(key=lambda x: x[0])
        for i in range(len(scores) - 1):
            assert scores[i][1] <= scores[i + 1][1] + 5.0, (
                f"Scoring is not monotone: rank {scores[i][0]} scored {scores[i][1]:.1f} "
                f"but rank {scores[i+1][0]} scored {scores[i+1][1]:.1f}."
            )

    def test_pearson_correlation_positive(self):
        # pearson r >= 0.6 (only 3 points; guards ordering reversal, not stats)
        try:
            from scipy.stats import pearsonr
        except ImportError:
            pytest.skip("scipy not installed")

        ranks = [cv["seniority_rank"] for cv in SYNTHETIC_CVS]
        ai_scores = [_score_candidate(cv, _SENIOR_JD) for cv in SYNTHETIC_CVS]

        r, _ = pearsonr(ranks, ai_scores)
        assert r >= 0.6, (
            f"Pearson correlation between seniority rank and AI score is {r:.3f}, "
            f"expected ≥ 0.6. Check scoring weights."
        )

    def test_scores_in_valid_range(self):
        # all scores in [0, 100]
        for cv in SYNTHETIC_CVS:
            for jd in [_SENIOR_JD, _JUNIOR_JD]:
                score = _score_candidate(cv, jd)
                assert 0.0 <= score <= 100.0, (
                    f"Score {score:.1f} is out of [0, 100] for CV level={cv['level']}."
                )
