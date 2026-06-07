# SmartRecruiter

BSc Individual Project

An applicant tracking system built to see if semantic matching, explainable scoring, and fairness auditing could work together in one small-team hiring tool - not just as separate research demos.

Most ATS tools still filter on keywords. SmartRecruiter parses CVs, scores candidates against a job with Sentence-BERT, shows *why* a score came out the way it did, and lets recruiters run MSD / DIR / SPD fairness checks on a cohort. The model recommends; the recruiter still decides.

## What it does

- **CV parsing** - PDF and Word via PyMuPDF / python-docx. spaCy helps when installed; regex fallback when it is not. Skills normalised through a 101-entry ontology (`JS` → `JavaScript`, `k8s` → `Kubernetes`, etc.).
- **Scoring** - 40% skills, 40% experience, 20% education. Sentence-BERT (`all-MiniLM-L6-v2`) for semantic match. Optional 50/50 LLM blend when `OPENAI_API_KEY` is set.
- **Explanations** - Per-component score breakdown and counterfactual hints (e.g. missing skills). Numeric explanation always works; LLM narrative is optional.
- **Fairness audit** - MSD, DIR, SPD on experience/education tiers by default. Self-declared demographics only when the user has opted in - never used in scoring.
- **RAG** - Retrieves job context and static rubrics, then generates summaries and interview questions (needs OpenAI).
- **Recruiter workflow** - Jobs, ranked applicants, notes thread, email drafts, blind-screening mode, analytics.
- **Applicant workflow** - Browse jobs, apply with a CV, track applications, manage profile.

Human-in-the-loop by design: `Application.status` and hire decisions are recruiter-owned fields. The scorer does not auto-reject anyone.

## Repo layout

```
SmartRecruiter/
├── backend/     FastAPI API, auth, database, routes
├── ai/          Parsing, embeddings, scoring helpers, RAG, fairness, XAI
├── frontend/    React 18 UI
├── docs/        Figures and viva notes
└── docker-compose.yml
```

`backend/` handles HTTP and persistence. `ai/` is the Python ML layer the API calls into. `frontend/` is a standard Create React App client.

## Quick start

**You need:** Python 3.11+ (3.12 in Docker), Node 18+, and optionally PostgreSQL. SQLite works fine locally. OpenAI is optional - leave the key blank to run on Sentence-BERT only.

**Backend**

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
copy .env.example .env

uvicorn main:app --reload
```

**Frontend** (separate terminal)

```powershell
cd frontend
npm install
npm start
```

- App: http://localhost:3000  
- API docs: http://localhost:8000/docs  

Or from the repo root: `npm run dev` (starts both).

**Docker**

```powershell
docker compose up
```

## Config

Everything lives in `backend/.env`. Copy from `.env.example` and edit.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite file | Postgres for production-style runs |
| `OPENAI_API_KEY` | empty | LLM scoring, RAG narrative, email polish |
| `EMBEDDING_BACKEND` | `sbert` | `sbert`, `openai`, or `auto` |
| `SECRET_KEY` | placeholder | Must be set properly when `DEBUG=False` |
| `LLM_PII_REDACTION` | `True` | Strip names/emails/phones before external LLM calls |
| `SMTP_ENABLED` | `False` | Password-reset emails |

## Tests

```powershell
# from repo root
pytest backend/tests ai/tests
```

Backend covers auth, RBAC, applications, notes. AI covers scoring order, XAI arithmetic, fairness scenarios, prompt-injection probe, and more.

**Benchmark** (24 synthetic CVs, dissertation Section 5.7):

```powershell
python ai/benchmark/run_benchmark.py
```

Outputs land in `ai/benchmark/` (`results.json`, `results.md`, `scatter.png`).

## A few honest notes

- `backend/app/routers/recommendations.py` exists but is not wired up in `main.py` - started it, quality was not good enough on a small dataset, left for later.
- Evaluation uses synthetic CVs, not real applicants. Usability pilot was 5 postgrads (mean SUS ~84) - useful signal, not a production claim.
- Fairness metrics flag statistical disparity; interpreting whether that is bias or legitimate job signal is still on the recruiter.
- This repo is the implementation artefact. It is not a certified compliance product for the EU AI Act or NYC Local Law 144, though audit logs and fairness tooling are there if you want to build toward that.

## Ethics / security

- Do not commit `.env` - pre-commit hook blocks obvious secret patterns.
- PII redaction runs before CV text hits an external LLM (`ai/ai_utils/pii.py`).
- Demographic fields require explicit consent and are excluded from the scoring path.
- Score decisions can be logged in `ai_audit_logs` with the numeric explanation attached.

## Author

**Bora Vinca** 

Dissertation title: *SmartRecruiter: AI-Powered Application Tracking System*
[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/Xqsle5Fb)
