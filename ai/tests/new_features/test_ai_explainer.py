from ai.explanation.xai_explainer import XAIExplainer

def test_explainability_output():
    cv_text = "Python developer with FastAPI experience and PostgreSQL skills."
    job_text = "Looking for Python developer with FastAPI experience."

    explanation = XAIExplainer().explain_scoring(
        resume_text=cv_text,
        job_description=job_text,
        scores={"skill_score": 85, "experience_score": 70, "education_score": 60, "match_score": 90, "overall_score": 80},
        candidate_skills=["Python", "FastAPI", "PostgreSQL"],
        candidate_experience_years=2.5
    )

    assert isinstance(explanation, dict)
    assert "skills_explanation" in explanation
    assert "experience_explanation" in explanation
    assert "overall_summary" in explanation
    assert "score_breakdown" in explanation
    assert isinstance(explanation["strengths"], list)
    assert isinstance(explanation["weaknesses"], list)
