# demo data seed via sqlalchemy orm
# creates 1 recruiter, 4 jobs, 9 applicants, scores through real ScoringService
# idempotent: re-run skips existing users/jobs/apps (lookup by email + title)
# usage: python scripts/seed_demo_data.py (from repo root, backend venv active)
# all demo passwords: DemoPassw0rd!

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# unicode checkmarks on windows consoles
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - non-critical
    pass

# backend importable no matter where you run from
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

# chdir to backend/ before db imports so sqlite path matches uvicorn (backend/smartrecruiter.db)
os.chdir(BACKEND_ROOT)

from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.auth_service import get_password_hash  # noqa: E402


DEMO_PASSWORD = "DemoPassw0rd!"


# static seed data (recruiter, jobs, applicants)

RECRUITER: Dict[str, Any] = {
    "email": "bora@smartrecruiter.demo",
    "first_name": "Bora",
    "last_name": "Vinca",
    "company_name": "SmartRecruiter Demo Co.",
}

JOBS: List[Dict[str, Any]] = [
    {
        "key": "senior-backend",
        "title": "Senior Backend Engineer",
        "description": (
            "We are building the next generation of our payments platform and "
            "we need a senior backend engineer to own a major service end to "
            "end. You will design APIs, mentor a small team, and work with "
            "product to ship features that thousands of customers depend on."
        ),
        "requirements": (
            "5+ years of professional backend experience, ideally on a high-"
            "throughput service. Comfortable with the full FastAPI/PostgreSQL "
            "stack and at least one major cloud."
        ),
        "location": "Remote (Europe)",
        "salary_range": "€70k – €95k",
        "required_education_level": "master",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "AWS", "Kubernetes"],
    },
    {
        "key": "junior-analyst",
        "title": "Junior Data Analyst",
        "description": (
            "Join our small but growing analytics team. You will turn raw "
            "product data into dashboards that the leadership team relies on "
            "every week, and work closely with the engineering side to define "
            "new events as features ship."
        ),
        "requirements": (
            "0–2 years of analytics experience. Strong SQL and Python. A "
            "portfolio of past dashboards is a plus."
        ),
        "location": "Thessaloniki, Greece",
        "salary_range": "€24k – €30k",
        "required_education_level": "bachelor",
        "required_skills": ["Python", "SQL", "Pandas", "Tableau"],
    },
    {
        "key": "mid-frontend",
        "title": "Mid-Level Frontend Engineer",
        "description": (
            "You will help us rebuild the recruiter dashboard with a focus on "
            "real-time data, accessibility, and a UI that does not feel like "
            "an enterprise product. Comfortable in a small team that owns "
            "design, code and review."
        ),
        "requirements": (
            "3–5 years of React experience, TypeScript fluency, strong "
            "fundamentals in CSS and accessibility."
        ),
        "location": "Hybrid (London)",
        "salary_range": "£55k – £70k",
        "required_education_level": "bachelor",
        "required_skills": ["JavaScript", "React", "TypeScript", "CSS", "Node.js"],
    },
    {
        "key": "lead-devops",
        "title": "Lead DevOps Engineer",
        "description": (
            "You will lead the platform team: Kubernetes clusters across three "
            "regions, Terraform-managed infrastructure, observability stack, "
            "and the on-call rotation. We are looking for someone who has "
            "scaled a real platform under load before."
        ),
        "requirements": (
            "7+ years of platform engineering experience. Deep Kubernetes and "
            "Terraform knowledge. Comfortable mentoring others."
        ),
        "location": "Remote (Europe)",
        "salary_range": "€85k – €110k",
        "required_education_level": "master",
        "required_skills": ["Kubernetes", "Terraform", "AWS", "Docker", "Linux"],
    },
]


APPLICANTS: List[Dict[str, Any]] = [
    {
        "first_name": "Sofia",
        "last_name": "Hadjiyianni",
        "email": "sofia.hadjiyianni@demo.com",
        "phone": "+30 694 555 0101",
        "experience_years": 8.0,
        "skills": [
            "Python", "FastAPI", "PostgreSQL", "AWS", "Kubernetes", "Docker",
            "Terraform", "Microservices", "PyTest",
        ],
        "education": [
            {
                "degree": "MSc Computer Science",
                "institution": "University of York Europe Campus",
                "year": "2017",
            },
            {
                "degree": "BSc Computer Science",
                "institution": "Aristotle University of Thessaloniki",
                "year": "2015",
            },
        ],
        "work_experience": [
            {
                "title": "Senior Backend Engineer",
                "company": "FintechPay",
                "duration": "2020 – present",
                "description": (
                    "Led the payments platform team. Designed and shipped "
                    "FastAPI services on PostgreSQL, deployed to AWS using "
                    "Kubernetes managed by Terraform. Mentored two engineers."
                ),
            },
            {
                "title": "Backend Engineer",
                "company": "DataMesh Labs",
                "duration": "2017 – 2020",
                "description": (
                    "Built Python microservices and ETL pipelines on AWS. "
                    "Owned the Docker-based deployment story for the team."
                ),
            },
        ],
        "resume_text": (
            "Sofia is a senior backend engineer with 8 years of professional "
            "experience. She has led teams shipping FastAPI services on "
            "PostgreSQL, deployed via Kubernetes on AWS, with Terraform-"
            "managed infrastructure. She also enjoys mentoring junior "
            "engineers and writing technical documentation."
        ),
        "applies_to": "senior-backend",
        "application_status": "shortlisted",
    },
    {
        "first_name": "Marcus",
        "last_name": "Thompson",
        "email": "marcus.thompson@demo.com",
        "phone": "+44 7700 900142",
        "experience_years": 1.5,
        "skills": ["Python", "SQL", "Pandas", "Matplotlib", "Excel"],
        "education": [{
            "degree": "BSc Computer Science",
            "institution": "University of Manchester",
            "year": "2024",
        }],
        "work_experience": [{
            "title": "Junior Data Analyst",
            "company": "BrightInsights",
            "duration": "2024 – present",
            "description": (
                "Built recurring SQL reports and Python notebooks for the "
                "marketing team. Used Pandas and Matplotlib for ad-hoc "
                "analyses."
            ),
        }],
        "resume_text": (
            "Recent CS graduate with 1.5 years of analytics experience. "
            "Comfortable in SQL and Python, learning Tableau."
        ),
        "applies_to": "junior-analyst",
        "application_status": "pending",
    },
    {
        "first_name": "Aria",
        "last_name": "Patel",
        "email": "aria.patel@demo.com",
        "phone": "+44 7700 900221",
        "experience_years": 4.0,
        "skills": [
            "JavaScript", "TypeScript", "React", "Node.js", "CSS", "HTML",
            "Jest", "Webpack", "GraphQL",
        ],
        "education": [{
            "degree": "BSc Computing",
            "institution": "Imperial College London",
            "year": "2021",
        }],
        "work_experience": [
            {
                "title": "Frontend Engineer",
                "company": "MapleHealth",
                "duration": "2022 – present",
                "description": (
                    "Built a React + TypeScript patient dashboard. Owned "
                    "accessibility audits, design-system migration, and the "
                    "Node.js BFF layer."
                ),
            },
            {
                "title": "Frontend Intern",
                "company": "StackUp",
                "duration": "2021 – 2022",
                "description": (
                    "Contributed React components, set up Jest test infra."
                ),
            },
        ],
        "resume_text": (
            "Frontend engineer with 4 years of professional experience. "
            "Specialises in React + TypeScript dashboards, with strong CSS "
            "and accessibility skills. Comfortable with Node.js BFFs and "
            "GraphQL."
        ),
        "applies_to": "mid-frontend",
        "application_status": "shortlisted",
    },
    {
        "first_name": "Daniel",
        "last_name": "Kovač",
        "email": "daniel.kovac@demo.com",
        "phone": "+49 152 9000 0334",
        "experience_years": 7.0,
        "skills": [
            "Kubernetes", "Terraform", "AWS", "Docker", "Linux", "Ansible",
            "Python", "Bash", "Prometheus",
        ],
        "education": [{
            "degree": "MSc Informatics",
            "institution": "Technical University of Munich",
            "year": "2018",
        }],
        "work_experience": [
            {
                "title": "Senior DevOps Engineer",
                "company": "FleetOps",
                "duration": "2020 – present",
                "description": (
                    "Owned the production Kubernetes platform across three "
                    "AWS regions. All infrastructure as Terraform. Wrote "
                    "Ansible playbooks for legacy fleet."
                ),
            },
            {
                "title": "DevOps Engineer",
                "company": "BlueBay Systems",
                "duration": "2018 – 2020",
                "description": (
                    "Migrated the entire CI/CD stack to Docker and "
                    "Kubernetes. Wrote Python automation around AWS."
                ),
            },
        ],
        "resume_text": (
            "Senior DevOps engineer with 7 years of platform experience. "
            "Deep Kubernetes, Terraform, and AWS expertise. Has scaled real "
            "production workloads under load and mentored two junior SREs."
        ),
        "applies_to": "lead-devops",
        "application_status": "shortlisted",
    },
    {
        "first_name": "Yuki",
        "last_name": "Tanaka",
        "email": "yuki.tanaka@demo.com",
        "phone": "+81 90 5550 1199",
        "experience_years": 2.0,
        "skills": ["Python", "SQL", "Tableau", "R", "Pandas", "Looker"],
        "education": [{
            "degree": "BSc Statistics",
            "institution": "University of Tokyo",
            "year": "2023",
        }],
        "work_experience": [{
            "title": "Data Analyst",
            "company": "RetailEdge",
            "duration": "2023 – present",
            "description": (
                "Tableau dashboards for the merchandising team. SQL "
                "warehouse modelling and ad-hoc Python analyses."
            ),
        }],
        "resume_text": (
            "Data analyst with 2 years of post-graduation experience. Comfortable "
            "in SQL, Tableau and Python for Pandas-driven reporting."
        ),
        "applies_to": "junior-analyst",
        "application_status": "pending",
    },
    {
        "first_name": "Rohan",
        "last_name": "Singh",
        "email": "rohan.singh@demo.com",
        "phone": "+91 98765 41200",
        "experience_years": 5.0,
        "skills": [
            "Python", "FastAPI", "PostgreSQL", "AWS", "Docker", "Redis",
        ],
        "education": [{
            "degree": "BTech Computer Science",
            "institution": "Indian Institute of Technology Bombay",
            "year": "2020",
        }],
        "work_experience": [
            {
                "title": "Backend Engineer",
                "company": "LedgerCloud",
                "duration": "2022 – present",
                "description": (
                    "Built FastAPI services on PostgreSQL deployed to AWS. "
                    "Owned the Redis caching layer."
                ),
            },
            {
                "title": "Software Engineer",
                "company": "Pixar India",
                "duration": "2020 – 2022",
                "description": (
                    "Python tooling for animation pipeline. Dockerised the "
                    "internal review tool."
                ),
            },
        ],
        "resume_text": (
            "Mid-level backend engineer with 5 years of Python and FastAPI "
            "experience. Comfortable with PostgreSQL, AWS, and Docker, "
            "interested in scaling up to senior-level platform work."
        ),
        # bsc applying to senior role with master requirement (education gap demo)
        "applies_to": "senior-backend",
        "application_status": "pending",
    },
    {
        "first_name": "Chiamaka",
        "last_name": "Okonkwo",
        "email": "chiamaka.okonkwo@demo.com",
        "phone": "+234 803 555 0099",
        "experience_years": 3.0,
        "skills": [
            "JavaScript", "React", "TypeScript", "CSS", "HTML", "Tailwind",
        ],
        # fake uni name to demo institution claim validation
        "education": [{
            "degree": "BSc Software Engineering",
            "institution": "Pacific Tech University",
            "year": "2022",
        }],
        "work_experience": [{
            "title": "Frontend Engineer",
            "company": "GreenLeaf Apps",
            "duration": "2022 – present",
            "description": (
                "Built React + TypeScript marketing sites and a CMS-driven "
                "landing-page builder."
            ),
        }],
        "resume_text": (
            "Frontend engineer with 3 years of experience building React + "
            "TypeScript applications. Strong CSS skills, comfortable in "
            "design-system work."
        ),
        "applies_to": "mid-frontend",
        "application_status": "pending",
    },
    {
        "first_name": "Liam",
        "last_name": "O'Brien",
        "email": "liam.obrien@demo.com",
        "phone": "+353 87 555 0033",
        # adversarial: 8 yrs claimed, no work history, stuffed skills (evidence + timeline warnings)
        "experience_years": 8.0,
        "skills": [
            "Python", "FastAPI", "PostgreSQL", "AWS", "Kubernetes",
            "Docker", "Terraform", "Java", "Go", "Rust",
            "React", "Vue", "Angular", "TensorFlow", "PyTorch",
        ],
        "education": [{
            "degree": "MSc Computer Science",
            "institution": "Stanford University",
            "year": "2018",
        }],
        "work_experience": [],
        "resume_text": (
            "Application for the senior backend role. Available immediately."
        ),
        "applies_to": "senior-backend",
        "application_status": "pending",
    },
    {
        "first_name": "Elena",
        "last_name": "Popescu",
        "email": "elena.popescu@demo.com",
        "phone": "+40 723 555 0044",
        "experience_years": 4.0,
        "skills": ["Python", "SQL", "Pandas", "Tableau", "PowerBI"],
        "education": [{
            "degree": "BSc Statistics",
            "institution": "University of Bucharest",
            "year": "2019",
        }],
        # overlapping full-time roles trigger overlapping_roles warning
        "work_experience": [
            {
                "title": "Data Analyst",
                "company": "DataFlow",
                "duration": "2020 – 2023",
                "description": (
                    "SQL reporting and Python notebooks for the operations "
                    "team. Pandas analyses, Tableau dashboards."
                ),
            },
            {
                "title": "Senior Data Analyst",
                "company": "Insightful",
                "duration": "2021 – 2024",
                "description": (
                    "Built PowerBI dashboards for the leadership team. "
                    "Owned the SQL warehouse schema."
                ),
            },
        ],
        "resume_text": (
            "Data analyst with 4 years of experience across SQL, Python, "
            "Tableau and PowerBI. Comfortable owning the full pipeline from "
            "ingestion to dashboarding."
        ),
        "applies_to": "junior-analyst",
        "application_status": "pending",
    },
]


# helpers

def _get_or_create_user(db: Session, *, email: str, role: str, **fields) -> models.User:
    # find by email or create with demo password
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        return user
    user = models.User(
        email=email,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        role=role,
        is_active=True,
        **fields,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_or_create_job(db: Session, *, recruiter_id: int, payload: Dict[str, Any]) -> models.Job:
    job = (
        db.query(models.Job)
        .filter(models.Job.recruiter_id == recruiter_id, models.Job.title == payload["title"])
        .first()
    )
    if job:
        # keep structured fields in sync when re-seeding after schema changes
        job.description = payload["description"]
        job.requirements = payload["requirements"]
        job.location = payload["location"]
        job.salary_range = payload["salary_range"]
        job.required_education_level = payload["required_education_level"]
        job.required_skills = payload["required_skills"]
        job.status = "active"
        db.commit()
        return job
    job = models.Job(
        recruiter_id=recruiter_id,
        title=payload["title"],
        description=payload["description"],
        requirements=payload["requirements"],
        location=payload["location"],
        salary_range=payload["salary_range"],
        status="active",
        required_education_level=payload["required_education_level"],
        required_skills=payload["required_skills"],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _annotate_education_with_institution_check(education: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # precompute institution_check (parser would do this in the live path)
    try:
        from ai.nlp.institution_lookup import get_verifier
        verifier = get_verifier()
    except Exception:
        verifier = None

    annotated: List[Dict[str, Any]] = []
    for entry in education:
        annotated_entry = dict(entry)
        institution = entry.get("institution", "") or ""
        if verifier and institution:
            annotated_entry["institution_check"] = verifier.verify(institution)
        else:
            annotated_entry["institution_check"] = {
                "recognized": False,
                "matched_name": None,
                "confidence": 0.0,
                "country": None,
            }
        annotated.append(annotated_entry)
    return annotated


def _get_or_create_applicant_application(
    db: Session,
    *,
    user: models.User,
    job: models.Job,
    profile: Dict[str, Any],
) -> Optional[models.Application]:
    # create Applicant + Application, or None if user already applied
    existing = (
        db.query(models.Application)
        .filter(models.Application.user_id == user.id, models.Application.job_id == job.id)
        .first()
    )
    if existing:
        return None

    applicant = models.Applicant(
        job_id=job.id,
        first_name=profile["first_name"],
        last_name=profile["last_name"],
        email=profile["email"],
        phone=profile.get("phone"),
        resume_text=profile["resume_text"],
        resume_file_path=None,
        resume_file_type="txt",
        skills=profile["skills"],
        experience_years=profile["experience_years"],
        education=_annotate_education_with_institution_check(profile["education"]),
        work_experience=profile["work_experience"],
        status=profile.get("application_status", "pending"),
    )
    db.add(applicant)
    db.flush()

    application = models.Application(
        user_id=user.id,
        job_id=job.id,
        applicant_id=applicant.id,
        status=profile.get("application_status", "pending"),
        ai_status="queued",
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def _score_application(application_id: int) -> None:
    # run production ai_processor (same path as live apply)
    from app.services.ai_processor import process_application_ai

    try:
        process_application_ai(application_id)
    except Exception as exc:  # pragma: no cover - best-effort
        print(f"    ! AI scoring failed for application {application_id}: {exc}")


def main() -> None:
    # create tables on fresh db
    Base.metadata.create_all(bind=engine)

    print("\n=== SmartRecruiter — Python seed ===\n")
    db: Session = SessionLocal()
    try:
        # recruiter
        print("[1/4] Recruiter")
        recruiter = _get_or_create_user(
            db,
            email=RECRUITER["email"],
            role="recruiter",
            first_name=RECRUITER["first_name"],
            last_name=RECRUITER["last_name"],
            company_name=RECRUITER["company_name"],
        )
        print(f"   ✓ {recruiter.email} (id={recruiter.id})")

        # jobs
        print("\n[2/4] Jobs")
        jobs_by_key: Dict[str, models.Job] = {}
        for spec in JOBS:
            job = _get_or_create_job(db, recruiter_id=recruiter.id, payload=spec)
            jobs_by_key[spec["key"]] = job
            print(
                f"   ✓ {spec['key']:<16} id={job.id}  "
                f"edu={job.required_education_level or '-':<8} "
                f"skills={len(job.required_skills or [])}"
            )

        # applicants + applications
        print("\n[3/4] Applicants + applications")
        created_application_ids: List[int] = []
        for profile in APPLICANTS:
            user = _get_or_create_user(
                db,
                email=profile["email"],
                role="applicant",
                first_name=profile["first_name"],
                last_name=profile["last_name"],
            )
            job = jobs_by_key[profile["applies_to"]]
            application = _get_or_create_applicant_application(
                db, user=user, job=job, profile=profile,
            )
            if application is None:
                print(f"   · {user.email}: already applied to {job.title}")
                continue
            created_application_ids.append(application.id)
            print(f"   ✓ {user.email:<32} → {job.title}")

        # score new applications
        if created_application_ids:
            print(f"\n[4/4] Running AI processor over {len(created_application_ids)} new application(s)…")
            for app_id in created_application_ids:
                _score_application(app_id)
            print("   ✓ scoring complete")
        else:
            print("\n[4/4] No new applications; skipping AI processor.")

        # login summary
        print("\n──────────────────────────────────────────────")
        print("Demo accounts (password for ALL accounts):")
        print(f"   {DEMO_PASSWORD}")
        print("\nRecruiter login:")
        print(f"   {RECRUITER['email']}")
        print("\nApplicant logins (pick any):")
        for profile in APPLICANTS:
            print(f"   {profile['email']:<32}  → {profile['applies_to']}")
        print("──────────────────────────────────────────────\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
