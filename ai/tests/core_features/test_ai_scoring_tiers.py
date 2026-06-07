import pytest
import sys
import os

# project root on path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.services.scoring_service import ScoringService
from ai.nlp.parser import ResumeParser


def score_candidate_against_job(cv_text: str, job_text: str) -> float:
    # parse cv then run ScoringService; returns overall_score 0-100
    parser = ResumeParser()
    file_content = cv_text.encode('utf-8')
    parsed_data = parser.parse_file(file_content, "resume.txt", use_ai=False)
    
    skills = parsed_data.get("skills", [])
    experience_years = parsed_data.get("experience_years", 0.0)
    education = parsed_data.get("education", [])
    work_experience = parsed_data.get("work_experience", [])
    
    scoring_service = ScoringService()
    scores = scoring_service.calculate_scores(
        resume_text=cv_text,
        job_description=job_text,
        job_requirements="",
        applicant_skills=skills,
        applicant_experience_years=experience_years,
        applicant_education=education,
        applicant_work_experience=work_experience
    )
    
    return scores["overall_score"]


@pytest.mark.parametrize("cv_file,job_file,expected_range", [
    ("test_data/resumes/emily_watson_cv.txt", "test_data/jobs/job_junior_python.txt", (70, 100)),
    ("test_data/resumes/emily_watson_cv.txt", "test_data/jobs/job_senior_python.txt", (30, 60)),
    ("test_data/resumes/thomas_evans_cv.txt", "test_data/jobs/job_junior_python.txt", (50, 75)),
    ("test_data/resumes/thomas_evans_cv.txt", "test_data/jobs/job_senior_python.txt", (60, 100)),
])
def test_tiered_scoring(cv_file, job_file, expected_range):
    # paths relative to ai/tests/
    tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    cv_path = os.path.join(tests_dir, cv_file)
    job_path = os.path.join(tests_dir, job_file)
    
    with open(cv_path, encoding='utf-8') as cv, open(job_path, encoding='utf-8') as job:
        cv_text, job_text = cv.read(), job.read()

    score = score_candidate_against_job(cv_text, job_text)
    assert expected_range[0] <= score <= expected_range[1], f"Score {score} out of expected range {expected_range}"
