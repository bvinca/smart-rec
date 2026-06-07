# end-to-end scoring smoke tests (ch5 style)
# checks ordering on the synthetic corpus: senior beats junior on senior roles, etc.
# skips exact dissertation accuracy numbers; just sanity-checks recruiter expectations

from __future__ import annotations

import os

import pytest

# skip whole module if sentence-transformers missing (e.g. ci without torch)
pytest.importorskip("sentence_transformers")

# force sbert backend regardless of env openai key
os.environ.setdefault("EMBEDDING_BACKEND", "sbert")
os.environ.setdefault("OPENAI_API_KEY", "")

from backend.app.services.scoring_service import ScoringService  # noqa: E402


@pytest.fixture(scope="module")
def scorer():
    return ScoringService()


def _score(scorer: ScoringService, cv: dict, job: dict) -> dict:
    return scorer.calculate_scores(
        resume_text=cv["text"],
        job_description=job["description"],
        job_requirements="",
        applicant_skills=cv["skills"],
        applicant_experience_years=cv["experience_years"],
        applicant_education=cv["education"],
        applicant_work_experience=[],
        use_adaptive_weights=False,
    )


def test_senior_outranks_junior_on_senior_role(scorer, synthetic_cvs, synthetic_jobs):
    senior_role = next(j for j in synthetic_jobs if j["level"] == "senior")
    senior_cv = next(c for c in synthetic_cvs if c["level"] == "senior")
    junior_cv = next(c for c in synthetic_cvs if c["level"] == "junior")

    senior_score = _score(scorer, senior_cv, senior_role)["overall_score"]
    junior_score = _score(scorer, junior_cv, senior_role)["overall_score"]

    assert senior_score > junior_score, (
        f"Senior CV ({senior_score}) should outrank junior CV ({junior_score}) on a senior role."
    )


def test_junior_role_does_not_punish_junior_candidate(scorer, synthetic_cvs, synthetic_jobs):
    junior_role = next(j for j in synthetic_jobs if j["level"] == "junior")
    junior_cv = next(c for c in synthetic_cvs if c["level"] == "junior")

    score = _score(scorer, junior_cv, junior_role)["overall_score"]
    assert score >= 50.0, f"Junior on junior role should score at least 50, got {score}."


def test_feature_contributions_sum_recoverable(scorer, synthetic_cvs, synthetic_jobs):
    junior_role = next(j for j in synthetic_jobs if j["level"] == "junior")
    junior_cv = next(c for c in synthetic_cvs if c["level"] == "junior")
    result = _score(scorer, junior_cv, junior_role)

    weighted = result["feature_contributions"]["weighted"]
    weights = result["weights_used"]

    expected = (
        result["skill_score"] * weights["skill_weight"]
        + result["experience_score"] * weights["experience_weight"]
        + result["education_score"] * weights["education_weight"]
        + result["match_score"] * weights["semantic_similarity_weight"]
    )

    assert abs(sum(weighted.values()) - expected) < 0.5
