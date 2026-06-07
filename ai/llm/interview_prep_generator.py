# Applicant interview prep - one GPT-4o-mini JSON call returns:
#   company_overview, position_questions (5), preparation_tips (4-6).
# No PII sent - job text + skill list only. Failures raise; caller handles 503/fallback.

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .openai_client import OpenAIClient

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "You are a friendly career coach helping a job applicant prepare for "
    "an interview. Respond ONLY with a valid JSON object, no prose around "
    "it. The JSON must have exactly three top-level keys: "
    '"company_overview" (string, 2-3 sentences), '
    '"position_questions" (array of exactly 5 short interview questions the '
    "recruiter is likely to ask, phrased from the recruiter's perspective), "
    'and "preparation_tips" (array of 4-6 short, actionable bullet points, '
    "each under 25 words)."
)


def _build_user_prompt(
    job_title: str,
    job_description: str,
    company_name: Optional[str],
    applicant_skills: Optional[List[str]],
) -> str:
    # build user message: title, optional company, JD, optional skills
    parts: List[str] = [
        f"Job title: {job_title.strip()}",
    ]
    if company_name and company_name.strip():
        parts.append(f"Company: {company_name.strip()}")
    parts.append("")
    parts.append("Job description:")
    parts.append(job_description.strip())
    if applicant_skills:
        skills_list = ", ".join(s.strip() for s in applicant_skills if s and s.strip())
        if skills_list:
            parts.append("")
            parts.append(
                "The candidate already lists these skills on their profile, "
                "so tailor the preparation tips to lean on or grow from these "
                f"strengths where relevant: {skills_list}."
            )
    parts.append("")
    parts.append(
        "Return the JSON described in the system instruction. Make the "
        "questions specific to the role above, not generic interview "
        "filler. The company_overview should describe what an applicant "
        "should know about this kind of role at a company like the one "
        "above; do not invent specific facts you cannot verify."
    )
    return "\n".join(parts)


def _extract_json_object(content: str) -> Dict[str, Any]:
    # pull out the first balanced { ... } block. The model is asked for raw JSON
    # but sometimes wraps it in a code fence or adds a stray sentence first.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(content[start : end + 1])


def _coerce_string_list(value: Any, *, label: str) -> List[str]:
    # normalise the model's array output into a clean list of strings
    if not isinstance(value, list):
        raise ValueError(f"LLM response field '{label}' was not an array.")
    out: List[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip().lstrip("-•*").strip()
            if cleaned:
                out.append(cleaned)
    return out


def generate_interview_prep(
    *,
    job_title: str,
    job_description: str,
    company_name: Optional[str] = None,
    applicant_skills: Optional[List[str]] = None,
) -> Dict[str, Any]:
    # returns {company_overview: str, position_questions: list[str] (5),
    # preparation_tips: list[str] (4-6)}.
    # Raises ValueError if no API key, LLM unreachable, or parse failure.
    if not job_title or not job_description:
        raise ValueError("job_title and job_description are required.")

    client = OpenAIClient()  # raises ValueError if no key set
    user_prompt = _build_user_prompt(
        job_title=job_title,
        job_description=job_description,
        company_name=company_name,
        applicant_skills=applicant_skills,
    )
    logger.info(
        "InterviewPrepGenerator: requesting prep for %r (job desc len=%d, "
        "skills=%d)",
        job_title,
        len(job_description),
        len(applicant_skills or []),
    )
    content = client.chat_completion(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=900,
        response_format={"type": "json_object"},
    )

    payload = _extract_json_object(content)

    overview = payload.get("company_overview", "")
    if not isinstance(overview, str):
        raise ValueError("LLM response field 'company_overview' was not a string.")
    overview = overview.strip()

    questions = _coerce_string_list(
        payload.get("position_questions", []), label="position_questions"
    )
    tips = _coerce_string_list(
        payload.get("preparation_tips", []), label="preparation_tips"
    )

    # if the model returns fewer than 3 questions, treat as a bad response
    # so the caller can retry or fall back
    if len(questions) < 3:
        raise ValueError(
            "LLM returned fewer than 3 position_questions; aborting."
        )
    questions = questions[:5]
    tips = tips[:6]

    logger.info(
        "InterviewPrepGenerator: produced overview=%d chars, %d questions, %d tips",
        len(overview),
        len(questions),
        len(tips),
    )
    return {
        "company_overview": overview,
        "position_questions": questions,
        "preparation_tips": tips,
    }
