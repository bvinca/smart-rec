# pytest setup for ai tests
# puts project root on sys.path so ai.* imports work from ai/ or repo root

from __future__ import annotations

import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def synthetic_cvs():
    # tiny cv corpus, same shape as the synthetic dataset in the dissertation

    return [
        {
            "name": "Junior 1",
            "level": "junior",
            "text": (
                "Junior Python developer with 1 year of experience. Built REST APIs "
                "with Flask and PostgreSQL, used Git and Docker. Bachelor of Science "
                "in Computer Science."
            ),
            "skills": ["Python", "Flask", "PostgreSQL", "Git", "Docker"],
            "experience_years": 1.0,
            "education": [{"degree": "Bachelor of Science in Computer Science"}],
        },
        {
            "name": "Mid 1",
            "level": "mid",
            "text": (
                "Software engineer with 4 years of experience using Python, FastAPI, "
                "and PostgreSQL. Led microservices on AWS with Docker and Kubernetes. "
                "Master's degree in Software Engineering."
            ),
            "skills": ["Python", "FastAPI", "PostgreSQL", "AWS", "Docker", "Kubernetes"],
            "experience_years": 4.0,
            "education": [{"degree": "MSc Software Engineering"}],
        },
        {
            "name": "Senior 1",
            "level": "senior",
            "text": (
                "Senior backend engineer with 9 years of experience. Designed and "
                "scaled FastAPI microservices, PostgreSQL, AWS, Kubernetes, "
                "Terraform. Mentor and tech lead. Master of Science."
            ),
            "skills": [
                "Python", "FastAPI", "PostgreSQL", "AWS", "Kubernetes",
                "Terraform", "Microservices", "Mentoring",
            ],
            "experience_years": 9.0,
            "education": [{"degree": "MSc Computer Science"}],
        },
    ]


@pytest.fixture(scope="session")
def synthetic_jobs():
    return [
        {
            "title": "Junior Python Developer",
            "level": "junior",
            "description": (
                "We're hiring a junior Python developer. Required: Python, Flask "
                "or FastAPI, PostgreSQL, Git. 1+ years of experience. Bachelor "
                "degree preferred."
            ),
        },
        {
            "title": "Senior Python Developer",
            "level": "senior",
            "description": (
                "Senior Python developer with 5+ years of experience. Strong "
                "background in FastAPI, PostgreSQL, AWS, Kubernetes, Terraform "
                "and microservices. Master's degree preferred."
            ),
        },
    ]
