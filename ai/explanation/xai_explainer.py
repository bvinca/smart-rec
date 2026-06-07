# XAI - numeric breakdown + optional narrative for each score.
# Not a LIME/SHAP surrogate - just Shapley-style additive split from the 50-pt baseline
# across skills, experience, education, semantic_match.
# Counterfactuals ("add Kubernetes for ~6 pts") from missing_skills + ontology weights.
# LLM narrative needs an OpenAI key; the numbers always work without one.
# Stored in AIAuditLog.explanation_json for the audit trail.

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings  # type: ignore
except Exception:  # pragma: no cover
    class _Fallback:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    settings = _Fallback()  # type: ignore

from ai.llm.openai_client import OpenAIClient
from ai.nlp.skill_ontology import ontology

logger = logging.getLogger(__name__)


# default 40/40/20 hybrid scoring weights when caller passes none
_DEFAULT_WEIGHTS: Dict[str, float] = {
    "skill_weight": 0.40,
    "experience_weight": 0.40,
    "education_weight": 0.20,
    "semantic_similarity_weight": 0.0,
}


class XAIExplainer:
    # explain candidate scoring in numbers + prose

    def __init__(self) -> None:
        self.client: Optional[OpenAIClient] = None
        api_key = (settings.OPENAI_API_KEY or "").strip()
        if api_key:
            try:
                self.client = OpenAIClient()
                logger.info("XAIExplainer: LLM narrative enabled (%s).", self.client.default_model)
            except Exception as exc:  # pragma: no cover
                logger.warning("XAIExplainer: LLM narrative disabled: %s", exc)
                self.client = None

    # entry point
    def explain_scoring(
        self,
        resume_text: str,
        job_description: str,
        scores: Dict[str, float],
        candidate_skills: Optional[List[str]] = None,
        candidate_experience_years: Optional[float] = None,
        weights: Optional[Dict[str, float]] = None,
        matched_skills: Optional[List[str]] = None,
        missing_skills: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # returns numeric attributions + narrative + counterfactuals
        weights = weights or _DEFAULT_WEIGHTS
        feature_attributions = self._compute_attributions(scores, weights)
        counterfactuals = self._counterfactual_hints(
            missing_skills or [], scores.get("skill_score", 0.0), weights
        )

        narrative = self._build_fallback_narrative(
            scores=scores,
            attributions=feature_attributions,
            matched_skills=matched_skills or candidate_skills or [],
            missing_skills=missing_skills or [],
        )

        if self.client:
            try:
                llm_narrative = self._build_llm_narrative(
                    resume_text=resume_text,
                    job_description=job_description,
                    scores=scores,
                    attributions=feature_attributions,
                    matched_skills=matched_skills or candidate_skills or [],
                    missing_skills=missing_skills or [],
                    candidate_experience_years=candidate_experience_years,
                )
                if llm_narrative:
                    narrative = llm_narrative
            except Exception:  # pragma: no cover - LLM errors are recoverable
                logger.exception("LLM narrative generation failed; using fallback.")

        return {
            "feature_attributions": feature_attributions,
            "counterfactuals": counterfactuals,
            "matched_skills": (matched_skills or [])[:20],
            "missing_skills": (missing_skills or [])[:20],
            "skills_explanation": narrative.get("skills_explanation", ""),
            "experience_explanation": narrative.get("experience_explanation", ""),
            "education_explanation": narrative.get("education_explanation", ""),
            "soft_skills_explanation": narrative.get("soft_skills_explanation", ""),
            "strengths": narrative.get("strengths", []),
            "weaknesses": narrative.get("weaknesses", []),
            "overall_summary": narrative.get("overall_summary", ""),
            "score_breakdown": self._score_breakdown(scores, weights, feature_attributions),
            "llm_available": self.client is not None,
        }

    # internals
    @staticmethod
    def _compute_attributions(
        scores: Dict[str, float],
        weights: Dict[str, float],
    ) -> Dict[str, Dict[str, Any]]:
        # additive Shapley-ish decomposition around a 50-point baseline
        # (exact for the additive scorer used by ScoringService)
        skill = float(scores.get("skill_score") or 0.0)
        experience = float(scores.get("experience_score") or 0.0)
        education = float(scores.get("education_score") or 0.0)
        match = float(scores.get("match_score") or 0.0)

        components = {
            "skills": (skill, weights.get("skill_weight", 0.4)),
            "experience": (experience, weights.get("experience_weight", 0.4)),
            "education": (education, weights.get("education_weight", 0.2)),
            "semantic_match": (match, weights.get("semantic_similarity_weight", 0.0)),
        }

        attributions: Dict[str, Dict[str, Any]] = {}
        for name, (value, weight) in components.items():
            contribution = (value - 50.0) * weight
            attributions[name] = {
                "raw_score": round(value, 2),
                "weight": round(weight, 4),
                "contribution_to_overall": round(contribution, 2),
                "weighted_score": round(value * weight, 2),
                "direction": "positive" if contribution >= 0 else "negative",
            }
        return attributions

    @staticmethod
    def _counterfactual_hints(
        missing_skills: List[str],
        skill_score: float,
        weights: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        # counterfactual: "what if they added this skill?" - each missing skill takes
        # its ontology weight share of the skill-component gap to 100, then
        # multiplied by skill_weight. Simple, interpretable, and exact for the
        # additive scorer.
        if not missing_skills:
            return []
        total_weight = sum(ontology.weight_for(s) for s in missing_skills) or 1.0
        skill_weight = weights.get("skill_weight", 0.4)
        hints: List[Dict[str, Any]] = []
        for skill in missing_skills[:8]:
            share = ontology.weight_for(skill) / total_weight
            # assume adding the skill closes `share` of the gap to 100 on the skill component
            gap = max(0.0, 100.0 - skill_score)
            delta = round(share * gap * skill_weight, 2)
            if delta <= 0.05:
                continue
            hints.append({
                "skill": skill,
                "expected_overall_score_gain": delta,
                "narrative": (
                    f"Adding '{skill}' to the CV would raise the overall score by "
                    f"~{delta:.1f} points."
                ),
            })
        return hints

    # narrative fallback - no LLM required
    def _build_fallback_narrative(
        self,
        scores: Dict[str, float],
        attributions: Dict[str, Dict[str, Any]],
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Dict[str, Any]:
        skill = scores.get("skill_score", 0.0)
        experience = scores.get("experience_score", 0.0)
        education = scores.get("education_score", 0.0)
        overall = scores.get("overall_score", 0.0)

        strengths = []
        weaknesses = []
        if matched_skills:
            strengths.append(
                f"Direct skill matches: {', '.join(matched_skills[:5])}"
                + ("..." if len(matched_skills) > 5 else "")
            )
        if attributions.get("experience", {}).get("direction") == "positive":
            strengths.append("Experience contributes positively to the overall score.")
        if missing_skills:
            weaknesses.append(
                f"Missing skills: {', '.join(missing_skills[:5])}"
                + ("..." if len(missing_skills) > 5 else "")
            )
        if attributions.get("education", {}).get("direction") == "negative":
            weaknesses.append("Education score is below the 50-point neutral baseline.")

        return {
            "skills_explanation": (
                f"Skills score {skill:.1f}/100. Top contribution to overall score: "
                f"{attributions['skills']['contribution_to_overall']:+.1f}."
            ),
            "experience_explanation": (
                f"Experience score {experience:.1f}/100. "
                f"Contribution: {attributions['experience']['contribution_to_overall']:+.1f}."
            ),
            "education_explanation": (
                f"Education score {education:.1f}/100. "
                f"Contribution: {attributions['education']['contribution_to_overall']:+.1f}."
            ),
            "soft_skills_explanation": (
                "Soft skills are evaluated within the LLM narrative when available."
            ),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "overall_summary": (
                f"Overall score: {overall:.1f}/100. "
                "The breakdown above quantifies how each component contributed."
            ),
        }

    def _build_llm_narrative(
        self,
        resume_text: str,
        job_description: str,
        scores: Dict[str, float],
        attributions: Dict[str, Dict[str, Any]],
        matched_skills: List[str],
        missing_skills: List[str],
        candidate_experience_years: Optional[float],
    ) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        prompt = self._build_prompt(
            resume_text=resume_text,
            job_description=job_description,
            scores=scores,
            attributions=attributions,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            candidate_experience_years=candidate_experience_years,
        )

        response = self.client.chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a recruitment assistant. Explain candidate scoring decisions "
                        "in clear, neutral language. Reference the provided numeric "
                        "attributions; never invent new numbers. Reply with JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
        )
        return self._parse_response(response)

    @staticmethod
    def _build_prompt(
        resume_text: str,
        job_description: str,
        scores: Dict[str, float],
        attributions: Dict[str, Dict[str, Any]],
        matched_skills: List[str],
        missing_skills: List[str],
        candidate_experience_years: Optional[float],
    ) -> str:
        resume = (resume_text or "")[:1800]
        job = (job_description or "")[:1200]
        attribution_lines = [
            f"- {name}: raw={info['raw_score']}, weight={info['weight']}, "
            f"contribution={info['contribution_to_overall']:+.2f}"
            for name, info in attributions.items()
        ]
        return (
            "Job description (truncated):\n"
            f"{job}\n\n"
            "Candidate résumé (truncated, identity already redacted upstream):\n"
            f"{resume}\n\n"
            f"Matched skills: {', '.join(matched_skills[:15]) or 'none'}\n"
            f"Missing skills: {', '.join(missing_skills[:15]) or 'none'}\n"
            f"Years of experience: {candidate_experience_years if candidate_experience_years is not None else 'unknown'}\n\n"
            "Numeric component attributions (additive, baseline 50):\n"
            + "\n".join(attribution_lines)
            + "\n\n"
            "Return STRICT JSON with these keys:\n"
            "{\n"
            '  "skills_explanation": "...",\n'
            '  "experience_explanation": "...",\n'
            '  "education_explanation": "...",\n'
            '  "soft_skills_explanation": "...",\n'
            '  "strengths": ["..."],\n'
            '  "weaknesses": ["..."],\n'
            '  "overall_summary": "..."\n'
            "}\n"
        )

    @staticmethod
    def _parse_response(response: str) -> Optional[Dict[str, Any]]:
        if not response:
            return None
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        try:
            parsed = json.loads(cleaned.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            logger.warning("XAIExplainer: LLM response was not valid JSON.")
        return None

    @staticmethod
    def _score_breakdown(
        scores: Dict[str, float],
        weights: Dict[str, float],
        attributions: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        # legacy shape - frontend dashboard still reads this
        return {
            "skills": {
                "score": scores.get("skill_score", 0.0),
                "weight": weights.get("skill_weight", 0.4),
                "explanation": "Token-based skill match against the job description",
                "contribution": f"{int(weights.get('skill_weight', 0.4) * 100)}%",
                "attribution": attributions["skills"]["contribution_to_overall"],
            },
            "experience": {
                "score": scores.get("experience_score", 0.0),
                "weight": weights.get("experience_weight", 0.4),
                "explanation": "Years of experience and relevance heuristic",
                "contribution": f"{int(weights.get('experience_weight', 0.4) * 100)}%",
                "attribution": attributions["experience"]["contribution_to_overall"],
            },
            "education": {
                "score": scores.get("education_score", 0.0),
                "weight": weights.get("education_weight", 0.2),
                "explanation": "Degree level vs job requirement",
                "contribution": f"{int(weights.get('education_weight', 0.2) * 100)}%",
                "attribution": attributions["education"]["contribution_to_overall"],
            },
            "match": {
                "score": scores.get("match_score", 0.0),
                "weight": weights.get("semantic_similarity_weight", 0.0),
                "explanation": "Sentence-BERT cosine similarity",
                "contribution": f"{int(weights.get('semantic_similarity_weight', 0.0) * 100)}%",
                "attribution": attributions["semantic_match"]["contribution_to_overall"],
            },
        }
