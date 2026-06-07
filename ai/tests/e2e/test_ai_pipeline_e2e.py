# e2e ai pipeline: parse, score, explain, fairness, visualize

import json
import os
import pytest
import sys

import logging
logger = logging.getLogger(__name__)

# project root on path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai.nlp.parser import ResumeParser
from backend.app.services.scoring_service import ScoringService
from ai.explanation.xai_explainer import XAIExplainer
from ai.evaluation.fairness_checker import FairnessChecker
from ai.visualization.skill_gap_visualizer import SkillGapVisualizer


def get_test_data_path(relative_path: str) -> str:
    # resolve path under ai/tests/test_data
    test_data_dir = os.path.join(os.path.dirname(__file__), '../test_data')
    return os.path.join(test_data_dir, relative_path)


@pytest.mark.parametrize("cv_file, job_file", [
    ("resumes/emily_watson_cv.txt", "jobs/job_junior_python.txt"),
    ("resumes/oliver_clarke_cv.txt", "jobs/job_mid_python.txt"),
    ("resumes/sophia_reed_cv.txt", "jobs/job_senior_python.txt")
])
def test_end_to_end_pipeline(cv_file, job_file):
    # full pipeline: parse, score, xai, fairness, viz
    cv_path = get_test_data_path(cv_file)
    job_path = get_test_data_path(job_file)
    
    if not os.path.exists(cv_path):
        pytest.skip(f"Test data file not found: {cv_path}")
    if not os.path.exists(job_path):
        pytest.skip(f"Test data file not found: {job_path}")
    
    with open(cv_path, encoding="utf-8") as f:
        cv_text = f.read()
    with open(job_path, encoding="utf-8") as f:
        job_text = f.read()
    
    # 1 parse resume
    logger.info(f"\n[Step 1] Parsing resume: {cv_file}")
    parser = ResumeParser()
    parsed_resume = parser.parse_file(cv_text.encode("utf-8"), "resume.txt", use_ai=False)
    
    assert parsed_resume is not None, "Resume parsing failed"
    assert "skills" in parsed_resume, "Parsed resume should contain skills"
    
    # 2 score
    logger.info(f"[Step 2] Scoring candidate against job: {job_file}")
    scoring_service = ScoringService()
    
    job_requirements = job_text
    
    scores = scoring_service.calculate_scores(
        resume_text=cv_text,
        job_description=job_text,
        job_requirements=job_requirements,
        applicant_skills=parsed_resume.get("skills", []),
        applicant_experience_years=parsed_resume.get("experience_years", 0),
        applicant_education=parsed_resume.get("education", []),
        applicant_work_experience=parsed_resume.get("work_experience", [])
    )
    
    assert scores is not None, "Scoring failed"
    assert "overall_score" in scores, "Scores should contain overall_score"
    assert 0 <= scores["overall_score"] <= 100, f"Overall score should be between 0-100, got {scores['overall_score']}"
    
    # 3 xai explanation
    logger.info(f"[Step 3] Generating explanation")
    explainer = XAIExplainer()
    explanation = explainer.explain_scoring(
        resume_text=cv_text,
        job_description=job_text,
        scores=scores,
        candidate_skills=parsed_resume.get("skills", []),
        candidate_experience_years=parsed_resume.get("experience_years", 0)
    )
    
    assert explanation is not None, "Explanation generation failed"
    assert "overall_summary" in explanation or "skills_explanation" in explanation, \
        "Explanation should contain at least summary or skills explanation"
    
    # 4 fairness audit (dummy second group so audit has something to compare)
    logger.info(f"[Step 4] Auditing fairness")
    fairness_checker = FairnessChecker()
    
    candidate_data = [{
        "group": "test_group",
        "overall_score": scores["overall_score"],
        "skill_score": scores.get("skill_score", 0),
        "experience_score": scores.get("experience_score", 0),
        "education_score": scores.get("education_score", 0)
    }]
    
    candidate_data.append({
        "group": "test_group_2",
        "overall_score": scores["overall_score"] + 5,
        "skill_score": scores.get("skill_score", 0) + 3,
        "experience_score": scores.get("experience_score", 0) + 2,
        "education_score": scores.get("education_score", 0) + 1
    })
    
    fairness_result = fairness_checker.audit_fairness(
        candidate_data=candidate_data,
        group_key="group",
        score_key="overall_score",
        threshold=10.0
    )
    
    assert fairness_result is not None, "Fairness audit failed"
    assert "bias_detected" in fairness_result, "Fairness result should contain bias_detected"
    
    # 5 skill gap viz
    logger.info(f"[Step 5] Generating skill gap visualization")
    visualizer = SkillGapVisualizer()
    
    job_skills = visualizer.extract_skills_from_text(job_text)
    candidate_skills = parsed_resume.get("skills", [])
    
    visualization = visualizer.compute_skill_similarity(
        job_skills=job_skills,
        candidate_skills=candidate_skills
    )
    
    assert visualization is not None, "Visualization generation failed"
    assert "overall_alignment" in visualization, "Visualization should contain overall_alignment"
    
    # 6 dump results json
    result = {
        "cv_file": os.path.basename(cv_file),
        "job_file": os.path.basename(job_file),
        "scores": scores,
        "explanation": explanation,
        "fairness": fairness_result,
        "visualization": visualization,
        "parsed_resume": {
            "skills": parsed_resume.get("skills", []),
            "experience_years": parsed_resume.get("experience_years", 0),
            "education_count": len(parsed_resume.get("education", [])),
            "work_experience_count": len(parsed_resume.get("work_experience", []))
        }
    }
    
    output_dir = os.path.join(project_root, "ai/test_results")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "e2e_results.json")
    
    results_list = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results_list = json.load(f)
        except (json.JSONDecodeError, Exception):
            results_list = []
    
    results_list.append(result)
    
    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(results_list, out, indent=4, default=str)
    
    logger.info(f"\n✅ E2E Pipeline completed successfully!")
    logger.info(f"   CV: {cv_file}")
    logger.info(f"   Job: {job_file}")
    logger.info(f"   Overall Score: {scores['overall_score']:.1f}%")
    logger.info(f"   Skill Alignment: {visualization.get('overall_alignment', 0):.1f}%")
    logger.info(f"   Results saved to: {output_path}")
    
    assert 0 <= scores["overall_score"] <= 100, "Overall score must be between 0-100"
    assert isinstance(explanation, dict), "Explanation must be a dictionary"
    assert isinstance(fairness_result, dict), "Fairness result must be a dictionary"
    assert isinstance(visualization, dict), "Visualization must be a dictionary"


def test_e2e_pipeline_integration():
    # single cv/job pair, all components wired together
    cv_path = get_test_data_path("resumes/emily_watson_cv.txt")
    job_path = get_test_data_path("jobs/job_junior_python.txt")
    
    if not os.path.exists(cv_path) or not os.path.exists(job_path):
        pytest.skip("Test data files not found")
    
    with open(cv_path, encoding="utf-8") as f:
        cv_text = f.read()
    with open(job_path, encoding="utf-8") as f:
        job_text = f.read()
    
    parser = ResumeParser()
    scoring_service = ScoringService()
    explainer = XAIExplainer()
    fairness_checker = FairnessChecker()
    visualizer = SkillGapVisualizer()
    
    parsed_resume = parser.parse_file(cv_text.encode("utf-8"), "resume.txt", use_ai=False)
    scores = scoring_service.calculate_scores(
        resume_text=cv_text,
        job_description=job_text,
        job_requirements=job_text,
        applicant_skills=parsed_resume.get("skills", []),
        applicant_experience_years=parsed_resume.get("experience_years", 0),
        applicant_education=parsed_resume.get("education", []),
        applicant_work_experience=parsed_resume.get("work_experience", [])
    )
    explanation = explainer.explain_scoring(
        resume_text=cv_text,
        job_description=job_text,
        scores=scores
    )
    
    candidate_data = [
        {"group": "group1", "overall_score": scores["overall_score"]},
        {"group": "group2", "overall_score": scores["overall_score"] + 2}
    ]
    fairness_result = fairness_checker.audit_fairness(candidate_data)
    
    job_skills = visualizer.extract_skills_from_text(job_text)
    visualization = visualizer.compute_skill_similarity(
        job_skills=job_skills,
        candidate_skills=parsed_resume.get("skills", [])
    )
    
    assert scores["overall_score"] >= 0
    assert "overall_summary" in explanation or "skills_explanation" in explanation
    assert "bias_detected" in fairness_result
    assert "overall_alignment" in visualization
    
    logger.info("\n✅ Integration test passed - all components work together correctly")
