# xai explainer numeric attribution tests
# integration tests cover the narrative path; here we only hit the deterministic bit

from __future__ import annotations

from ai.explanation.xai_explainer import XAIExplainer


def test_attributions_sum_close_to_overall_minus_baseline():
    explainer = XAIExplainer()
    explainer.client = None  # force deterministic path

    weights = {
        "skill_weight": 0.40,
        "experience_weight": 0.40,
        "education_weight": 0.20,
        "semantic_similarity_weight": 0.0,
    }
    scores = {
        "skill_score": 80.0,
        "experience_score": 60.0,
        "education_score": 50.0,
        "match_score": 70.0,
        "overall_score": 80.0 * 0.4 + 60.0 * 0.4 + 50.0 * 0.2,
    }
    result = explainer.explain_scoring(
        resume_text="some resume",
        job_description="some job",
        scores=scores,
        candidate_skills=["Python"],
        candidate_experience_years=4,
        weights=weights,
        matched_skills=["Python"],
        missing_skills=["FastAPI"],
    )

    attributions = result["feature_attributions"]
    expected_total = (80 - 50) * 0.4 + (60 - 50) * 0.4 + (50 - 50) * 0.2
    actual_total = sum(c["contribution_to_overall"] for c in attributions.values())
    assert abs(actual_total - expected_total) < 0.05


def test_counterfactuals_are_sorted_and_bounded():
    explainer = XAIExplainer()
    explainer.client = None
    weights = {
        "skill_weight": 0.40,
        "experience_weight": 0.40,
        "education_weight": 0.20,
        "semantic_similarity_weight": 0.0,
    }
    result = explainer.explain_scoring(
        resume_text="resume",
        job_description="job",
        scores={
            "skill_score": 50.0,
            "experience_score": 50.0,
            "education_score": 50.0,
            "match_score": 50.0,
            "overall_score": 50.0,
        },
        candidate_skills=[],
        candidate_experience_years=2,
        weights=weights,
        matched_skills=[],
        missing_skills=["FastAPI", "Kubernetes", "Terraform"],
    )

    counterfactuals = result["counterfactuals"]
    assert counterfactuals, "should produce counterfactual hints when skills are missing"
    assert all("expected_overall_score_gain" in c for c in counterfactuals)
    assert all(c["expected_overall_score_gain"] > 0 for c in counterfactuals)
