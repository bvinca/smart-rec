# hybrid candidate scoring. the shape I settled on:
#   1. embeddings: SBERT by default, OpenAI if configured (EmbeddingVectorizer picks)
#   2. weights: 40% skills / 40% experience / 20% education
#   3. hybrid blend: semantic + LLM when an OpenAI key exists
#
# response includes feature_contributions for the XAI explainer.
# no protected-attribute shortcuts - education match comes from the JD text, not a lookup table.
from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

# add the repo root so `ai/` imports work from inside backend/
ai_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ai_path not in sys.path:
    sys.path.insert(0, ai_path)

from ai import utils as ai_utils  # noqa: E402
from ai.embeddings import EmbeddingVectorizer, SimilarityCalculator  # noqa: E402
from ai.evaluation import CandidateEvaluator  # noqa: E402
from ai.nlp.skill_ontology import ontology  # noqa: E402

logger = logging.getLogger(__name__)


# default scoring weights
DEFAULT_WEIGHTS: Dict[str, float] = {
    "skill_weight": 0.40,
    "experience_weight": 0.40,
    "education_weight": 0.20,
    # semantic similarity is folded into the hybrid skill/experience scores
    # already - kept here for back-compat with the adaptive learner, default 0
    "semantic_similarity_weight": 0.0,
}


_DEGREE_KEYWORDS = (
    "phd", "doctorate", "ph.d", "msc", "m.sc", "m.s.", "m.s",
    "master", "mba", "mca", "ma ", "ma,", " ma", "ms ", "ms,",
    "bsc", "b.sc", "b.s.", "b.s", "bachelor", "ba ", "ba,", " ba",
    "bs ", "bs,", "btech", "b.tech", "be ", "b.e.", "associate",
    "diploma", "degree",
)


# numeric ladder for education levels - used to compare the candidate's
# top qualification against the structured requirement on the job
_EDU_LEVEL_RANK: Dict[str, int] = {
    "none": 0,
    "associate": 1,
    "bachelor": 2,
    "master": 3,
    "phd": 4,
}


class ScoringService:
    # computes (CV, job) match scores with a per-component breakdown the XAI
    # explainer can consume

    def __init__(self, db: Optional[Session] = None) -> None:
        self.vectorizer = EmbeddingVectorizer()
        self.evaluator = CandidateEvaluator()
        self.db = db
        # 50% semantic + 50% LLM when LLM is available
        self.semantic_weight = 0.5
        # text_hash → vector cache, keyed by active backend
        self._cache = None
        if db is not None:
            try:
                from app.services.embedding_cache import EmbeddingCache

                self._cache = EmbeddingCache(db, model_name=self.vectorizer.backend)
            except Exception:
                logger.exception("Embedding cache unavailable; scoring will re-embed every call.")
                self._cache = None

    def _embed(self, text: str) -> List[float]:
        # cached embed - generate on miss, look up on hit
        if not text or not text.strip():
            return self.vectorizer.generate_embedding("")
        if self._cache is not None:
            cached = self._cache.get(text)
            if cached:
                return cached
        vector = self.vectorizer.generate_embedding(text)
        if self._cache is not None and vector:
            try:
                self._cache.put(text, vector)
            except Exception:
                logger.exception("Embedding cache put failed (non-fatal).")
        return vector

    # ----------------------------------------------------------------- main
    def calculate_scores(
        self,
        resume_text: str,
        job_description: str,
        job_requirements: str,
        applicant_skills: List[str],
        applicant_experience_years: float,
        applicant_education: List[Dict[str, Any]],
        applicant_work_experience: List[Dict[str, Any]],
        recruiter_id: Optional[int] = None,
        job_id: Optional[int] = None,
        use_adaptive_weights: bool = True,
        required_education_level: Optional[str] = None,
        required_skills_override: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # full scoring breakdown for one (CV, job) pair
        # normalise up front so downstream comparisons match
        normalised_skills = ontology.normalise_list(applicant_skills or [])
        job_text = (job_description or "") + "\n" + (job_requirements or "")

        # required skills: prefer the structured list the recruiter set,
        # otherwise text-mine the JD through the ontology. structured wins
        # because it doesn't depend on the recruiter spelling out every skill.
        if required_skills_override:
            required_skills = ontology.normalise_list(required_skills_override)
        else:
            required_skills = ontology.find_in_text(job_text)

        # stage 1: semantic similarity
        resume_embedding = self._embed(resume_text)
        job_embedding = self._embed(job_description)
        semantic_match_score = SimilarityCalculator.calculate_match_score(
            resume_embedding, job_embedding
        )

        # per-component scores (each 0-100)
        skill_breakdown = self._calculate_skill_score(
            candidate_skills=normalised_skills,
            required_skills=required_skills,
            resume_text=resume_text,
            work_experience=applicant_work_experience,
        )
        semantic_skill_score = skill_breakdown["score"]
        semantic_experience_score = self._calculate_experience_score(
            applicant_experience_years, applicant_work_experience, job_description
        )
        semantic_education_score = self._calculate_education_score(
            applicant_education, job_description, required_education_level
        )

        # stage 2: LLM evaluation (optional)
        llm_evaluation = self.evaluator.evaluate_candidate(
            cv_text=resume_text,
            job_text=job_description,
            job_requirements=job_requirements,
            candidate_skills=normalised_skills,
            candidate_experience_years=applicant_experience_years,
        )
        llm_overall = llm_evaluation.get("overall_score", 50.0)
        llm_skill = llm_evaluation.get("skill_score", 50.0)
        llm_experience = llm_evaluation.get("experience_score", 50.0)
        llm_explanation = llm_evaluation.get("explanation", "")
        llm_available = llm_evaluation.get("llm_available", False)

        # stage 3: hybrid component scores
        if llm_available:
            hybrid_overall = ai_utils.combine_scores(
                semantic_match_score, llm_overall, self.semantic_weight
            )
            hybrid_skill = ai_utils.combine_scores(
                semantic_skill_score, llm_skill, self.semantic_weight
            )
            hybrid_experience = ai_utils.combine_scores(
                semantic_experience_score, llm_experience, self.semantic_weight
            )
        else:
            # no LLM - lean on the semantic/heuristic side only
            hybrid_overall = semantic_match_score
            hybrid_skill = semantic_skill_score
            hybrid_experience = semantic_experience_score

        education_score = semantic_education_score

        # stage 4: weighted overall (40/40/20)
        weights = self._resolve_weights(use_adaptive_weights, recruiter_id, job_id)
        overall_score = (
            hybrid_skill * weights["skill_weight"]
            + hybrid_experience * weights["experience_weight"]
            + education_score * weights["education_weight"]
            + hybrid_overall * weights["semantic_similarity_weight"]
        )

        # diagnostic only - flags when the candidate is way above the
        # requested seniority. never folded into the score; the LLM handles
        # the down-weighting naturally.
        seniority_gap = self._estimate_seniority_gap(
            applicant_experience_years, job_description
        )

        explanation = self._generate_hybrid_explanation(
            semantic_match_score,
            semantic_skill_score,
            semantic_experience_score,
            llm_overall,
            llm_skill,
            llm_experience,
            llm_explanation,
            hybrid_overall,
            hybrid_skill,
            hybrid_experience,
            normalised_skills,
            applicant_experience_years,
            llm_available,
        )

        feature_contributions = self._feature_contributions(
            weights=weights,
            skill=hybrid_skill,
            experience=hybrid_experience,
            education=education_score,
            semantic=hybrid_overall,
            matched_skills=skill_breakdown["matched_skills"],
            missing_skills=skill_breakdown["missing_skills"],
        )

        return {
            "match_score": round(hybrid_overall, 2),
            "skill_score": round(hybrid_skill, 2),
            "experience_score": round(hybrid_experience, 2),
            "education_score": round(education_score, 2),
            "overall_score": round(overall_score, 2),
            "explanation": explanation,
            "resume_embedding": resume_embedding,
            "job_embedding": job_embedding,
            "feature_contributions": feature_contributions,
            "seniority_gap": seniority_gap,
            "weights_used": weights,
            "matched_skills": skill_breakdown["matched_skills"],
            "missing_skills": skill_breakdown["missing_skills"],
            "skill_evidence": skill_breakdown.get("evidence", {}),
            "score_breakdown": {
                "semantic": {
                    "match": round(semantic_match_score, 2),
                    "skill": round(semantic_skill_score, 2),
                    "experience": round(semantic_experience_score, 2),
                    "education": round(semantic_education_score, 2),
                },
                "llm": {
                    "overall": round(llm_overall, 2),
                    "skill": round(llm_skill, 2),
                    "experience": round(llm_experience, 2),
                    "available": llm_available,
                },
                "hybrid": {
                    "match": round(hybrid_overall, 2),
                    "skill": round(hybrid_skill, 2),
                    "experience": round(hybrid_experience, 2),
                },
                "scoring_method": (
                    "Hybrid (50% semantic + 50% LLM)" if llm_available
                    else "Semantic-only (LLM unavailable)"
                ),
            },
        }

    # evidence weighting per matched skill. keyword-stuffing without work context
    # only gets ~0.3 credit - tuned so fake skill lists lose most of their impact.
    _EVIDENCE_STRONG: float = 1.0   # skill in a dated work entry
    _EVIDENCE_MEDIUM: float = 0.6   # skill in the CV body
    _EVIDENCE_WEAK: float = 0.3     # skill only in the structured list

    # ------------------------------------------------------------------ skill
    def _calculate_skill_score(
        self,
        candidate_skills: List[str],
        required_skills: List[str],
        resume_text: str = "",
        work_experience: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # ontology-weighted skill match with per-skill evidence weighting.
        # each required skill contributes weight × evidence_factor:
        #   STRONG (1.0) - skill in a work entry (title/description)
        #   MEDIUM (0.6) - skill in the CV body
        #   WEAK   (0.3) - skill only in the structured list, no context
        # stops the keyword-stuffing trick (21 fake skills used to jump 0 -> 100).
        # with evidence weighting, a stuffed CV caps around 30% of the raw match.
        # returns {score, matched_skills, missing_skills, evidence}.
        if not required_skills:
            # nothing specific to match → score from breadth alone, capped
            # at 70 so "any CV" doesn't get inflated
            breadth = min(70.0, 25.0 + 5.0 * len(candidate_skills))
            return {
                "score": breadth,
                "matched_skills": [],
                "missing_skills": [],
                "evidence": {},
            }

        # build the evidence index per canonical skill. ontology.find_in_text
        # does longest-first alias matching, so "JavaScript" never leaks into
        # "Java" evidence.
        body_skills = set(ontology.find_in_text(resume_text or ""))
        workexp_skills: set = set()
        for exp in work_experience or []:
            blob = ((exp.get("title") or "") + " " + (exp.get("description") or "")).strip()
            if blob:
                workexp_skills.update(ontology.find_in_text(blob))

        candidate_set = set(candidate_skills)
        matched: List[str] = []
        missing: List[str] = []
        matched_weight = 0.0
        total_weight = 0.0
        evidence_map: Dict[str, str] = {}

        for skill in required_skills:
            weight = ontology.weight_for(skill)
            total_weight += weight
            if skill in candidate_set:
                matched.append(skill)
                if skill in workexp_skills:
                    factor = self._EVIDENCE_STRONG
                    evidence_map[skill] = "work_experience"
                elif skill in body_skills:
                    factor = self._EVIDENCE_MEDIUM
                    evidence_map[skill] = "body"
                else:
                    factor = self._EVIDENCE_WEAK
                    evidence_map[skill] = "claim_only"
                matched_weight += weight * factor
            else:
                missing.append(skill)

        if total_weight == 0:
            return {
                "score": 50.0,
                "matched_skills": matched,
                "missing_skills": missing,
                "evidence": evidence_map,
            }

        score = (matched_weight / total_weight) * 100.0
        return {
            "score": round(min(score, 100.0), 2),
            "matched_skills": matched,
            "missing_skills": missing,
            "evidence": evidence_map,
        }

    # ------------------------------------------------------------------ exp
    def _calculate_experience_score(
        self,
        experience_years: float,
        work_experience: List[Dict[str, Any]],
        job_description: str,
    ) -> float:
        # heuristic experience score - quantity + relevance
        years = max(float(experience_years or 0.0), 0.0)
        # logistic-ish cap so 10+ years doesn't dominate
        if years >= 8:
            year_score = 70.0
        elif years >= 5:
            year_score = 55.0
        elif years >= 3:
            year_score = 40.0
        elif years >= 1:
            year_score = 25.0
        else:
            year_score = 10.0

        relevance_score = 0.0
        if work_experience:
            job_text_lower = (job_description or "").lower()
            relevant = 0
            for exp in work_experience:
                title = (exp.get("title") or "").lower()
                description = (exp.get("description") or "").lower()
                blob = f"{title} {description}"
                if any(token in blob for token in (
                    "developer", "engineer", "scientist", "analyst",
                    "researcher", "architect", "designer", "manager",
                )):
                    relevant += 1
                # token overlap with the JD - small bump per match
                for token in re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", job_text_lower):
                    if token in blob:
                        relevant += 0.05
                        break
            relevance_score = min(30.0, 10.0 * relevant)

        return min(100.0, year_score + relevance_score)

    # ----------------------------------------------------------------- edu
    def _calculate_education_score(
        self,
        education: List[Dict[str, Any]],
        job_description: str,
        required_education_level: Optional[str] = None,
    ) -> float:
        # education score - structured-requirement aware.
        # if required_education_level is set on the job, score by distance
        # from the candidate's top qualification on the ladder (associate→1,
        # bachelor→2, master→3, phd→4). otherwise fall back to text-mining
        # the JD - preserves back-compat for jobs predating the structured field.
        # returns 0-100. 50-ish baseline so candidates with no extracted
        # education aren't crushed when the JD has no requirement either.
        if not education:
            # nothing extracted → neutral baseline. even when the JD requires
            # something, don't zero out - the parser can miss, and the
            # recruiter still sees the underlying field
            return 40.0

        candidate_text = " ".join(
            (edu.get("degree") or "") + " " + (edu.get("institution") or "")
            for edu in education
        ).lower()

        # candidate's top degree → numeric rank
        if any(t in candidate_text for t in ("phd", "doctorate", "ph.d")):
            candidate_rank = 4
        elif any(t in candidate_text for t in ("master", "msc", "m.sc", "m.s", "mba")):
            candidate_rank = 3
        elif any(t in candidate_text for t in ("bachelor", "bsc", "b.sc", "b.s", "btech")):
            candidate_rank = 2
        elif any(t in candidate_text for t in ("associate", "diploma")):
            candidate_rank = 1
        else:
            candidate_rank = 0

        # path A: structured requirement - use it directly
        normalised_req = (required_education_level or "").strip().lower() or None
        if normalised_req and normalised_req != "none":
            required_rank = _EDU_LEVEL_RANK.get(normalised_req, 0)
            if candidate_rank >= required_rank:
                base = 90.0
            elif candidate_rank == required_rank - 1:
                base = 70.0
            elif candidate_rank == required_rank - 2:
                base = 55.0
            else:
                base = 40.0
            bonus = self._topical_bonus(candidate_text, job_description)
            return min(100.0, base + bonus)

        # path B: null / "none" on the job → text-mine the JD
        job_text = (job_description or "").lower()
        job_mentions_degree = any(token in job_text for token in _DEGREE_KEYWORDS)

        if not job_mentions_degree:
            # JD doesn't require a degree - reward "has any qualification"
            return 50.0 + 10.0 * min(candidate_rank, 2)

        # JD implies a degree - try to match the level
        if any(t in job_text for t in ("phd", "doctorate", "ph.d")):
            required_level = 4
        elif any(t in job_text for t in ("master", "msc", "m.sc", "mba")):
            required_level = 3
        else:
            required_level = 2  # "a degree" with no specifier → assume bachelor

        if candidate_rank >= required_level:
            base = 90.0
        elif candidate_rank == required_level - 1:
            base = 70.0
        else:
            base = 50.0

        bonus = self._topical_bonus(candidate_text, job_description)
        return min(100.0, base + bonus)

    @staticmethod
    def _topical_bonus(candidate_text: str, job_description: str) -> float:
        # small bump when the candidate's field-of-study overlaps with the
        # JD text (e.g. "computer science" mentioned in both)
        job_text = (job_description or "").lower()
        if not job_text or not candidate_text:
            return 0.0
        for token in re.findall(r"[A-Za-z]{4,}", candidate_text):
            if token in job_text:
                return 10.0
        return 0.0

    # -------------------------------------------------------------- weights
    def _resolve_weights(
        self,
        use_adaptive_weights: bool,
        recruiter_id: Optional[int],
        job_id: Optional[int],
    ) -> Dict[str, float]:
        if not use_adaptive_weights or not self.db:
            return DEFAULT_WEIGHTS.copy()
        try:
            from app.services.learning_service import AdaptiveWeightLearner

            learner = AdaptiveWeightLearner(self.db)
            weights = learner.get_weights(recruiter_id, job_id)
            total = sum(weights.values())
            if total <= 0:
                return DEFAULT_WEIGHTS.copy()
            # renormalise - the learner can drift from sum=1 when only one
            # dimension was bumped
            return {k: v / total for k, v in weights.items()}
        except Exception:  # pragma: no cover - defensive
            logger.exception("Falling back to default weights.")
            return DEFAULT_WEIGHTS.copy()

    # -------------------------------------------------------------- helpers
    def _estimate_seniority_gap(self, experience_years: float, job_description: str) -> float:
        # years_above_required (positive when overqualified). diagnostic only.
        text = (job_description or "").lower()
        match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)", text)
        if not match:
            return 0.0
        try:
            required = float(match.group(1))
        except ValueError:
            return 0.0
        return float(experience_years or 0.0) - required

    def _feature_contributions(
        self,
        weights: Dict[str, float],
        skill: float,
        experience: float,
        education: float,
        semantic: float,
        matched_skills: List[str],
        missing_skills: List[str],
    ) -> Dict[str, Any]:
        # SHAP-style additive contributions to the overall
        contributions = {
            "skills": round(skill * weights["skill_weight"], 2),
            "experience": round(experience * weights["experience_weight"], 2),
            "education": round(education * weights["education_weight"], 2),
            "semantic_match": round(semantic * weights.get("semantic_similarity_weight", 0.0), 2),
        }
        return {
            "weighted": contributions,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "weights": weights,
        }

    # --------------------------------------------------------- explanation
    def _generate_hybrid_explanation(
        self,
        semantic_match: float,
        semantic_skill: float,
        semantic_experience: float,
        llm_overall: float,
        llm_skill: float,
        llm_experience: float,
        llm_explanation: str,
        hybrid_match: float,
        hybrid_skill: float,
        hybrid_experience: float,
        skills: List[str],
        experience_years: float,
        llm_available: bool,
    ) -> Dict[str, Any]:
        explanations: List[str] = []

        if hybrid_match >= 80:
            explanations.append("Excellent match with the job requirements.")
        elif hybrid_match >= 60:
            explanations.append("Good alignment with the job description.")
        elif hybrid_match >= 40:
            explanations.append("Moderate match with the job requirements.")
        else:
            explanations.append("Limited alignment with the job description.")

        if hybrid_skill >= 80:
            explanations.append(
                f"Strong skill coverage: {len(skills)} canonical skills detected."
            )
        elif hybrid_skill >= 60:
            explanations.append(
                f"Reasonable skill coverage: {len(skills)} canonical skills detected."
            )
        else:
            explanations.append("Limited skill overlap with the requirements.")

        if hybrid_experience >= 80:
            explanations.append(
                f"Extensive relevant experience ({experience_years:.1f} years)."
            )
        elif hybrid_experience >= 60:
            explanations.append(f"Solid experience ({experience_years:.1f} years).")
        else:
            explanations.append(f"Entry-level experience ({experience_years:.1f} years).")

        llm_insight = llm_explanation if llm_available and llm_explanation else (
            "LLM evaluation unavailable; relying on Sentence-BERT similarity."
        )

        return {
            "match_explanation": explanations[0],
            "skill_explanation": explanations[1],
            "experience_explanation": explanations[2],
            "llm_insight": llm_insight,
            "overall_assessment": self._overall_assessment(
                hybrid_match, hybrid_skill, hybrid_experience
            ),
            "scoring_method": (
                "Hybrid (50% Sentence-BERT semantic + 50% LLM reasoning)"
                if llm_available
                else "Sentence-BERT semantic similarity only"
            ),
        }

    @staticmethod
    def _overall_assessment(match: float, skill: float, exp: float) -> str:
        avg_score = (match + skill + exp) / 3
        if avg_score >= 80:
            return "Highly qualified candidate with strong alignment to the role."
        if avg_score >= 60:
            return "Qualified candidate with a good potential fit."
        if avg_score >= 40:
            return "Moderate candidate; may require additional training."
        return "Limited qualifications for this role."
