# SmartRecruiter â€” Demo Data Seed Script
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\seed_demo_data.ps1
#
# Creates: 1 recruiter, 3 jobs, 6 applicants, 6 applications
# All requests go to http://localhost:8000 â€” start the backend first.

$BASE = "http://localhost:8000"
$H    = @{ "Content-Type" = "application/json" }

function Post($url, $body) {
    Invoke-RestMethod -Uri "$BASE$url" -Method POST -Body ($body | ConvertTo-Json -Depth 5) -Headers $H
}

Write-Host "`n=== SmartRecruiter Demo Seed ===" -ForegroundColor Cyan

# â”€â”€ 1. Register recruiter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host "`n[1/4] Creating recruiter account..." -ForegroundColor Yellow
$rec = Post "/auth/register" @{
    email        = "recruiter@acme.com"
    password     = "Recruiter123!"
    role         = "recruiter"
    first_name   = "Sarah"
    last_name    = "Connor"
    company_name = "ACME Technologies"
}
$token = $rec.access_token
$H["Authorization"] = "Bearer $token"
Write-Host "  Recruiter: $($rec.user.email)  token=...$(($token)[-10..-1] -join '')" -ForegroundColor Green

# â”€â”€ 2. Create jobs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host "`n[2/4] Creating jobs..." -ForegroundColor Yellow

$job1 = Post "/jobs/" @{
    title       = "Senior Python Backend Engineer"
    description = "We are looking for a Senior Python Backend Engineer to join our platform team. You will architect and scale FastAPI microservices, design PostgreSQL schemas, and lead technical decisions. You will mentor junior engineers and collaborate with product."
    requirements= "5+ years Python, FastAPI or Django, PostgreSQL, AWS or GCP, Docker, Kubernetes, REST API design, Git. Experience with microservices architecture preferred. MSc or BSc in Computer Science or equivalent."
    location    = "London, UK (Hybrid)"
    salary_range= "GBP 70,000 - 90,000"
}
Write-Host "  Job 1: $($job1.title) (id=$($job1.id))" -ForegroundColor Green

$job2 = Post "/jobs/" @{
    title       = "Machine Learning Engineer"
    description = "Join our AI/ML team to build production ML pipelines and recommendation systems. You will implement model training workflows, deploy models via REST APIs, and maintain model monitoring dashboards."
    requirements= "3+ years Python, scikit-learn, PyTorch or TensorFlow, MLflow or similar. Experience with data pipelines (Airflow, Spark). Familiarity with NLP and transformer models a bonus. BSc in Computer Science, Mathematics or Statistics."
    location    = "Remote (UK)"
    salary_range= "GBP 60,000 - 80,000"
}
Write-Host "  Job 2: $($job2.title) (id=$($job2.id))" -ForegroundColor Green

$job3 = Post "/jobs/" @{
    title       = "Junior Frontend Developer"
    description = "We are hiring a Junior Frontend Developer to help build modern React applications. You will work closely with senior engineers, contribute to UI components, and implement responsive designs from Figma specs."
    requirements= "1+ year React, HTML5, CSS3, JavaScript (ES6+). Familiarity with REST APIs and Git. Tailwind CSS or similar utility framework a bonus. BSc in any field or bootcamp equivalent."
    location    = "Manchester, UK (On-site)"
    salary_range= "GBP 28,000 - 35,000"
}
Write-Host "  Job 3: $($job3.title) (id=$($job3.id))" -ForegroundColor Green

# â”€â”€ 3. Register applicant accounts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host "`n[3/4] Registering applicant accounts..." -ForegroundColor Yellow

$applicants = @(
    @{ email="alice.zhang@email.com";   password="Pass1234!"; first_name="Alice";  last_name="Zhang"    },
    @{ email="ben.okafor@email.com";    password="Pass1234!"; first_name="Ben";    last_name="Okafor"   },
    @{ email="carlos.mendez@email.com"; password="Pass1234!"; first_name="Carlos"; last_name="Mendez"   },
    @{ email="diana.patel@email.com";   password="Pass1234!"; first_name="Diana";  last_name="Patel"    },
    @{ email="eli.foster@email.com";    password="Pass1234!"; first_name="Eli";    last_name="Foster"   },
    @{ email="fatima.ali@email.com";    password="Pass1234!"; first_name="Fatima"; last_name="Ali"      }
)

$appUsers = @()
foreach ($a in $applicants) {
    $u = Post "/auth/register" @{ email=$a.email; password=$a.password; role="applicant"; first_name=$a.first_name; last_name=$a.last_name }
    $appUsers += $u
    Write-Host "  Applicant: $($u.user.email)" -ForegroundColor Green
}

# â”€â”€ 4. Submit applications with CVs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host "`n[4/4] Submitting applications (applicant-side)..." -ForegroundColor Yellow

$cvs = @(
    # Alice â€” Senior Python, strong match for Job 1
    @{
        job_id         = $job1.id
        applicant_token= $appUsers[0].access_token
        cv = @"
Alice Zhang â€” Senior Backend Engineer
Email: alice.zhang@email.com | London, UK

EXPERIENCE
Senior Software Engineer â€” TechCorp Ltd, London (2020â€“present, 4 years)
- Designed FastAPI microservices handling 50k req/s on AWS EKS
- Led migration from monolith to Kubernetes-based architecture
- PostgreSQL schema design and query optimisation
- Mentored 3 junior engineers

Software Engineer â€” StartupXYZ (2018â€“2020, 2 years)
- Python/Django REST API development
- Docker containerisation and CI/CD pipelines

EDUCATION
MSc Computer Science â€” University of Cambridge (2018)
BSc Software Engineering â€” University of Manchester (2016)

SKILLS
Python, FastAPI, Django, PostgreSQL, AWS, Kubernetes, Docker, Terraform, Redis, Git, REST APIs, Microservices
"@
    },
    # Ben â€” ML Engineer, strong match for Job 2
    @{
        job_id         = $job2.id
        applicant_token= $appUsers[1].access_token
        cv = @"
Ben Okafor â€” Machine Learning Engineer
Email: ben.okafor@email.com | Remote, UK

EXPERIENCE
ML Engineer â€” DataStream AI (2021â€“present, 3 years)
- Built PyTorch NLP models for sentiment classification (F1 0.91)
- MLflow model registry and A/B experiment tracking
- Apache Airflow pipelines for daily model retraining
- Deployed models via FastAPI + Docker on GCP

Data Scientist â€” FinTech Ltd (2019â€“2021, 2 years)
- scikit-learn classification models for fraud detection
- Feature engineering with Spark on Databricks

EDUCATION
BSc Mathematics with Statistics â€” University of Edinburgh (2019)

SKILLS
Python, PyTorch, TensorFlow, scikit-learn, MLflow, Airflow, Spark, SQL, Docker, GCP, NLP, Transformers, HuggingFace
"@
    },
    # Carlos â€” Mid-level Python, partial match for Job 1
    @{
        job_id         = $job1.id
        applicant_token= $appUsers[2].access_token
        cv = @"
Carlos Mendez â€” Python Developer
Email: carlos.mendez@email.com | Birmingham, UK

EXPERIENCE
Python Developer â€” WebAgency Co (2021â€“present, 3 years)
- Django REST Framework API development
- PostgreSQL database design
- Docker and basic AWS deployments
- Git-based team workflow

Junior Developer â€” Freelance (2020â€“2021, 1 year)
- Flask web applications
- Basic CI/CD with GitHub Actions

EDUCATION
BSc Computer Science â€” Aston University (2020)

SKILLS
Python, Django, Flask, PostgreSQL, Docker, AWS, Git, REST APIs, HTML, CSS
"@
    },
    # Diana â€” Senior ML + Python, applying to Job 2
    @{
        job_id         = $job2.id
        applicant_token= $appUsers[3].access_token
        cv = @"
Diana Patel â€” Senior Machine Learning Engineer
Email: diana.patel@email.com | London, UK

EXPERIENCE
Lead ML Engineer â€” AI Ventures (2019â€“present, 5 years)
- Led NLP research team: BERT fine-tuning, sentence transformers
- Production ML systems in PyTorch on Azure Kubernetes
- Designed MLflow + Airflow retraining pipelines
- Published internal paper on bias detection in ranking models

ML Researcher â€” University College London (2017â€“2019, 2 years)
- Deep learning research, 2 published papers

EDUCATION
PhD Machine Learning â€” Imperial College London (2017)
MEng Computer Science â€” IIT Delhi (2013)

SKILLS
Python, PyTorch, TensorFlow, HuggingFace, scikit-learn, MLflow, Airflow, Azure, Kubernetes, NLP, Computer Vision, Spark, SQL
"@
    },
    # Eli â€” Junior Frontend, strong match for Job 3
    @{
        job_id         = $job3.id
        applicant_token= $appUsers[4].access_token
        cv = @"
Eli Foster â€” Junior Frontend Developer
Email: eli.foster@email.com | Manchester, UK

EXPERIENCE
Frontend Developer â€” DigitalAgency (2023â€“present, 1 year)
- React functional components and hooks
- Tailwind CSS responsive layouts from Figma designs
- REST API integration with axios
- Git pull-request workflow

Intern Developer â€” LocalStartup (2022â€“2023, 6 months)
- HTML5, CSS3, JavaScript ES6
- Basic React and state management

EDUCATION
BSc Computer Science â€” Manchester Metropolitan University (2022)

SKILLS
React, JavaScript, HTML5, CSS3, Tailwind CSS, REST APIs, Git, Figma, Responsive Design, axios
"@
    },
    # Fatima â€” Graduate, weak match for Job 1 (for contrast)
    @{
        job_id         = $job1.id
        applicant_token= $appUsers[5].access_token
        cv = @"
Fatima Ali â€” Graduate Software Developer
Email: fatima.ali@email.com | Leeds, UK

EXPERIENCE
Graduate Developer â€” SmallAgency (2024â€“present, 6 months)
- Python scripting and data analysis
- Basic Flask web application
- PostgreSQL queries

Final Year Project â€” University of Leeds (2024)
- Built a REST API with FastAPI and SQLite for a university timetable system

EDUCATION
BSc Computer Science â€” University of Leeds (2024)

SKILLS
Python, Flask, FastAPI, PostgreSQL, SQLite, Git, HTML, CSS, Java
"@
    }
)

foreach ($app in $cvs) {
    $appH = @{ "Content-Type" = "application/json"; "Authorization" = "Bearer $($app.applicant_token)" }
    try {
        $result = Invoke-RestMethod -Uri "$BASE/applications/apply/$($app.job_id)" `
            -Method POST `
            -Body (@{ cv_text = $app.cv } | ConvertTo-Json) `
            -Headers $appH
        Write-Host "  Applied: $($result.id) â†’ job $($app.job_id)" -ForegroundColor Green
    } catch {
        Write-Host "  WARN: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host @"

Recruiter login:
  Email   : recruiter@acme.com
  Password: Recruiter123!

Applicant logins (all password: Pass1234!):
  alice.zhang@email.com   â€” Senior Python Engineer (Job: Senior Backend)
  ben.okafor@email.com    â€” ML Engineer            (Job: ML Engineer)
  carlos.mendez@email.com â€” Mid Python Dev          (Job: Senior Backend)
  diana.patel@email.com   â€” Senior ML Engineer      (Job: ML Engineer)
  eli.foster@email.com    â€” Junior Frontend          (Job: Junior Frontend)
  fatima.ali@email.com    â€” Graduate Dev             (Job: Senior Backend)

Open http://localhost:3000 and log in as the recruiter to see ranked candidates.
For AI scoring use http://localhost:8000/docs â†’ POST /applicants/{id}/score
"@ -ForegroundColor White

