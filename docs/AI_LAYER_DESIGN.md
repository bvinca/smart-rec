# 🧠 AI_LAYER_DESIGN.md
### SmartRecruiter — AI Evaluation and Scoring System
**Version:** 1.0  
**Author:** Bora Vinca  
**Project:** SmartRecruiter: Intelligent Applicant Tracking System  
**Purpose:** This document describes the design, architecture, and implementation plan of the AI layer used in SmartRecruiter to evaluate candidate CVs against job postings using a hybrid RAG + LLM approach.

---

## 1️⃣ Overview

The **AI layer** is the core intelligence of SmartRecruiter.  
It is responsible for evaluating candidates automatically by:
1. Parsing uploaded resumes.
2. Matching them against job postings.
3. Generating semantic similarity scores.
4. Producing explainable AI-based evaluations (LLM reasoning).

This module ensures fairness, transparency, and contextual understanding — addressing the limitations of traditional keyword-based Applicant Tracking Systems (ATS).

---

## 2️⃣ Architecture Overview

### 📦 High-Level Structure
/smartRecruiter
│
├── backend/
│ ├── main.py
│ ├── database.py
│ ├── models.py
│ └── routers/
│ └── jobs.py
│ └── applicants.py
│
├── ai/
│ ├── parser.py ← CV parsing & skill extraction
│ ├── embeddings.py ← Text vectorization using embeddings
│ ├── retriever.py ← Context retrieval (RAG)
│ ├── evaluator.py ← LLM-based reasoning and scoring
│ └── utils.py ← Helper functions
│
└── frontend/
└── (React UI components)

python
Copy code

---

## 3️⃣ Pipeline Stages

### 🧩 Stage 1: Resume Parsing (parser.py)
**Goal:** Convert raw text or PDF CVs into structured data.

**Tools:**  
- `PyMuPDF` or `pdfminer.six` (for PDF → text)  
- `spaCy` (NER extraction for names, skills, experience)  
- Regex (for years of experience, emails, etc.)

**Example:**
```python
import re, spacy
nlp = spacy.load("en_core_web_sm")

def extract_experience(text):
    match = re.search(r'([0-9]+)\s*(?:\+?\s*)?(?:years|yrs)\s+of\s+experience', text)
    return int(match.group(1)) if match else 0

def parse_cv(cv_text):
    doc = nlp(cv_text)
    skills = [ent.text for ent in doc.ents if ent.label_ == "SKILL"]
    exp = extract_experience(cv_text)
    return {"skills": skills, "experience_years": exp}
Output Example:

json
Copy code
{
  "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
  "experience_years": 3
}
🔍 Stage 2: Text Embeddings (embeddings.py)
Goal: Convert both job descriptions and CVs into vector representations.

Tools:

sentence-transformers (local, free option)

or OpenAI Embeddings API (text-embedding-3-small for accuracy)

Example:

python
Copy code
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
Usage:
Embed both job descriptions and candidate CVs → store them in a local database or FAISS vector index.

🗂️ Stage 3: Retrieval-Augmented Generation (retriever.py)
Goal: Retrieve the most relevant job sections for each candidate CV.
Tool: FAISS / Chroma vector database.

Example:

python
Copy code
import faiss
import numpy as np

def retrieve_context(cv_embedding, job_embeddings, job_texts, top_k=3):
    index = faiss.IndexFlatL2(len(cv_embedding))
    index.add(np.array(job_embeddings).astype("float32"))
    _, I = index.search(np.array([cv_embedding]).astype("float32"), top_k)
    return [job_texts[i] for i in I[0]]
🤖 Stage 4: LLM Evaluation (evaluator.py)
Goal: Use an LLM (e.g., GPT-4-turbo or GPT-4o-mini) to reason contextually.

Prompt Design (very important):

python
Copy code
from openai import OpenAI
import os, json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def evaluate_candidate(cv_text, job_text):
    prompt = f"""
    You are an AI recruiter. Evaluate how well this candidate fits the job.

    Job Description:
    {job_text}

    Candidate CV:
    {cv_text}

    Rate suitability on a scale 0–100.
    Return JSON:
    {{
      "overall_score": int,
      "experience_score": int,
      "skill_score": int,
      "explanation": "text"
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        return {"error": str(e)}
Sample Output:

json
Copy code
{
  "overall_score": 87,
  "experience_score": 83,
  "skill_score": 91,
  "explanation": "Candidate has 3 years of backend experience using FastAPI and PostgreSQL. Good alignment with required skills but lacks leadership exposure."
}
⚖️ Stage 5: Weighted Hybrid Scoring (utils.py)
Goal: Combine embedding similarity + LLM reasoning for final score.

Formula:

ini
Copy code
final_score = (0.5 * semantic_similarity) + (0.5 * llm_score)
python
Copy code
def combine_scores(semantic, llm):
    return round((semantic * 0.5) + (llm * 0.5), 2)
This hybrid score ensures stability even when the LLM fails or OpenAI quota is exceeded.

🧮 Stage 6: Normalisation and Ranking
Each score is normalized per job posting so candidates are ranked relative to each other.

python
Copy code
def normalize_scores(scores):
    min_s, max_s = min(scores), max(scores)
    return [(s - min_s) / (max_s - min_s) * 100 for s in scores]
4️⃣ Implementation Steps (Sequential)
Step	Action	File	Description
1	Create /ai folder in root	—	Holds all AI logic
2	Implement parser.py	CV Parsing	Extract skills, education, and years
3	Implement embeddings.py	Vectorisation	Use OpenAI or SentenceTransformers
4	Implement retriever.py	Context fetcher	Retrieves top relevant job sections
5	Implement evaluator.py	LLM Reasoning	GPT-based contextual scoring
6	Implement utils.py	Scoring helpers	Combine, normalize, and rank
7	Integrate in backend	main.py	Add route /evaluate_candidate
8	Store results	DB	Save CV/job ID, scores, and explanation
9	Display frontend results	React	Show overall score + reasoning

5️⃣ Integration Example (FastAPI Endpoint)
backend/main.py

python
Copy code
from fastapi import FastAPI, UploadFile
from ai.evaluator import evaluate_candidate
from ai.embeddings import get_embedding

app = FastAPI()

@app.post("/evaluate")
async def evaluate(cv: UploadFile, job_id: int):
    cv_text = (await cv.read()).decode("utf-8")
    job_text = get_job_description(job_id)
    result = evaluate_candidate(cv_text, job_text)
    return result