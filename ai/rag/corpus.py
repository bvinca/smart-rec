# RAG seed corpus - role rubrics, interview guides, ethics/fairness primers.
# Indexed at bootstrap alongside recruiter job postings.

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CorpusDocument:
    doc_id: str
    title: str
    text: str
    source: str = "static_corpus"


_ROLE_RUBRICS: List[CorpusDocument] = [
    CorpusDocument(
        doc_id="rubric_python_dev",
        title="Python Developer rubric",
        text=(
            "A strong Python developer demonstrates fluency in modern Python (3.10+), "
            "writes idiomatic and well-tested code (pytest, hypothesis), is comfortable with "
            "type hints, virtual environments, and packaging, and has shipped at least one "
            "production service. Frameworks frequently expected: FastAPI, Django or Flask. "
            "Database literacy includes PostgreSQL or MySQL, ORM use (SQLAlchemy), and an "
            "understanding of indexing and N+1 queries. Senior candidates also discuss "
            "concurrency (asyncio, threads), profiling, and trade-offs between sync and async."
        ),
    ),
    CorpusDocument(
        doc_id="rubric_data_scientist",
        title="Data Scientist rubric",
        text=(
            "A competent data scientist owns the full analytics loop: framing a business "
            "question, sourcing and cleaning data with Pandas/NumPy, building baselines, "
            "applying ML models from scikit-learn / XGBoost / PyTorch, and communicating "
            "results to non-technical stakeholders. Strong candidates discuss feature "
            "engineering, leakage, cross-validation, calibration, and model monitoring. "
            "Familiarity with experiment tracking (MLflow, W&B) and notebook hygiene is a plus."
        ),
    ),
    CorpusDocument(
        doc_id="rubric_nlp_engineer",
        title="NLP Engineer rubric",
        text=(
            "An NLP engineer has hands-on experience with transformer-based models, "
            "fine-tuning and prompt engineering, retrieval-augmented generation, and "
            "evaluation methods (BLEU, ROUGE, BERTScore, human evaluation). Tooling: "
            "Hugging Face Transformers, sentence-transformers, spaCy, LangChain or "
            "LlamaIndex. Senior candidates can talk about latency budgets, quantisation, "
            "and deploying models behind a FastAPI / Triton endpoint."
        ),
    ),
    CorpusDocument(
        doc_id="rubric_devops",
        title="DevOps Engineer rubric",
        text=(
            "DevOps engineers automate the path from commit to production. Skills: "
            "Docker, Kubernetes, Terraform/Pulumi, GitHub Actions or GitLab CI, "
            "observability (Prometheus, Grafana, OpenTelemetry), one major cloud (AWS, "
            "GCP, Azure), Linux fundamentals and shell scripting. Behavioural cues: blameless "
            "post-mortems, on-call empathy, and willingness to invest in tooling that helps "
            "the rest of the team."
        ),
    ),
    CorpusDocument(
        doc_id="rubric_fullstack",
        title="Full-stack Developer rubric",
        text=(
            "Full-stack developers combine modern frontend skills (React, TypeScript, "
            "Tailwind, accessibility) with a backend stack (Node.js, Python, or .NET). They "
            "are comfortable designing REST/GraphQL APIs, writing meaningful tests at both "
            "tiers, and reasoning about authentication flows (OAuth2, JWT). Senior "
            "candidates can discuss performance budgets, web vitals, and SSR/edge rendering."
        ),
    ),
]


_INTERVIEW_GUIDES: List[CorpusDocument] = [
    CorpusDocument(
        doc_id="guide_behavioural_star",
        title="Behavioural interviews: STAR rubric",
        text=(
            "Behavioural interview answers are graded on STAR coverage: Situation (what was "
            "the context), Task (what was the candidate's responsibility), Action (specific "
            "actions they took, in first person), Result (measurable outcomes). Strong "
            "candidates volunteer numbers, attribute credit fairly to the team, and reflect "
            "on what they would do differently. Probes: 'Walk me through a project where X "
            "went wrong.', 'How did you measure success?', 'Who else was involved?'."
        ),
    ),
    CorpusDocument(
        doc_id="guide_technical_design",
        title="Technical design interview rubric",
        text=(
            "A good system-design interview covers requirements gathering, capacity "
            "estimation, data modelling, API contracts, scalability and reliability "
            "discussion, and trade-off analysis. Strong candidates ask clarifying questions, "
            "explain decisions in writing on the whiteboard, and explicitly address failure "
            "modes (cache stampedes, partial outages, data consistency)."
        ),
    ),
    CorpusDocument(
        doc_id="guide_fairness",
        title="Fair interview practice",
        text=(
            "Interview questions should be job-relevant, structured, and consistent across "
            "candidates. Avoid questions that probe protected characteristics (age, "
            "ethnicity, marital status, sexual orientation, disability, nationality). When "
            "possible, redact identity fields from CVs during initial screening to mitigate "
            "implicit bias. Calibrate scoring rubrics with multiple interviewers and review "
            "disagreements before final decisions."
        ),
    ),
]


_ETHICS: List[CorpusDocument] = [
    CorpusDocument(
        doc_id="ethics_eu_ai_act",
        title="EU AI Act — recruitment risk classification",
        text=(
            "The EU AI Act classifies AI systems used in recruitment and worker management "
            "as high-risk. Operators must implement data governance, transparency, human "
            "oversight, and risk management. Candidates have a right to know that an AI "
            "system was used, the main parameters considered, and to contest the decision. "
            "Logging of inputs, outputs, and explanations is mandatory."
        ),
    ),
    CorpusDocument(
        doc_id="ethics_fairness_metrics",
        title="Fairness metrics primer",
        text=(
            "Key fairness measures used in recruitment auditing: Mean Score Difference "
            "(MSD) — the absolute difference of mean scores between groups, target < 10 "
            "points. Disparate Impact Ratio (DIR) — the ratio of selection rates between "
            "the lowest and highest scoring groups, target between 0.8 and 1.25 (the four-"
            "fifths rule). Statistical Parity Difference (SPD) — the difference between "
            "selection rates, target close to zero. Equal Opportunity Difference — the "
            "difference of true positive rates across groups."
        ),
    ),
]


def default_corpus() -> List[CorpusDocument]:
    # what RAGRetriever.bootstrap() loads on first start
    return [*_ROLE_RUBRICS, *_INTERVIEW_GUIDES, *_ETHICS]


__all__ = ["CorpusDocument", "default_corpus"]
