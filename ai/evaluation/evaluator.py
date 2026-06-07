# GPT-4o-mini candidate evaluator - contextual reasoning beyond keyword/embedding match.
# Neutral 50s when no API key.
from typing import Dict, Any, Optional
import json
import sys
import os

import logging
logger = logging.getLogger(__name__)

# add backend to path so we can import config
backend_path = os.path.join(os.path.dirname(__file__), '../../../backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings
except ImportError:
    # fallback for standalone-script use
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()

from ..ai_utils.pii import maybe_redact
from ..llm.openai_client import OpenAIClient


class CandidateEvaluator:
    # LLM-driven candidate-vs-job reasoning + scores

    def __init__(self):
        self.client = None
        self.use_llm = False

        # only spin up the client if a key is actually set
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key.strip():
            try:
                self.client = OpenAIClient()
                self.use_llm = True
                logger.info("CandidateEvaluator: Using OpenAI GPT-4o-mini for evaluation")
            except Exception as e:
                logger.exception(f"CandidateEvaluator: Failed to initialize OpenAI client: {e}")
                self.use_llm = False
        else:
            logger.info("CandidateEvaluator: OpenAI API key not configured, LLM evaluation disabled")
    
    def evaluate_candidate(
        self,
        cv_text: str,
        job_text: str,
        job_requirements: Optional[str] = None,
        candidate_skills: Optional[list] = None,
        candidate_experience_years: Optional[float] = None
    ) -> Dict[str, Any]:
        # returns dict: overall_score, experience_score, skill_score, explanation (+ llm_available)
        if not self.use_llm or not self.client:
            # no LLM - neutral 50s so callers don't crash
            return {
                "overall_score": 50,
                "experience_score": 50,
                "skill_score": 50,
                "explanation": "LLM evaluation not available. Using fallback scores.",
                "llm_available": False
            }
        
        prompt = self._build_evaluation_prompt(
            cv_text, job_text, job_requirements, candidate_skills, candidate_experience_years
        )
        
        try:
            logger.info("CandidateEvaluator: Evaluating candidate with LLM...")
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert AI recruiter. Evaluate candidates objectively and provide detailed reasoning for your scores."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = self.client.chat_completion(
                messages=messages,
                temperature=0.3,  # keep it low so scores are stable across runs
                max_tokens=500
            )

            logger.info(f"CandidateEvaluator: Received LLM response (length: {len(response)})")

            result = self._parse_llm_response(response)
            result["llm_available"] = True
            return result
            
        except Exception as e:
            import traceback
            logger.exception(f"CandidateEvaluator: Error during LLM evaluation: {e}")
            logger.info(f"CandidateEvaluator: Traceback: {traceback.format_exc()}")
            
            # error path - same neutral 50s
            return {
                "overall_score": 50,
                "experience_score": 50,
                "skill_score": 50,
                "explanation": f"LLM evaluation failed: {str(e)}. Using fallback scores.",
                "llm_available": False,
                "error": str(e)
            }
    
    def _build_evaluation_prompt(
        self,
        cv_text: str,
        job_text: str,
        job_requirements: Optional[str],
        candidate_skills: Optional[list],
        candidate_experience_years: Optional[float]
    ) -> str:
        # redact PII before the CV hits the LLM - non-negotiable
        redaction_enabled = bool(getattr(settings, "LLM_PII_REDACTION", True))
        cv_text_safe = maybe_redact(cv_text or "", enabled=redaction_enabled)
        cv_text_truncated = cv_text_safe[:2000]
        job_text_truncated = (job_text or "")[:1500]
        
        prompt = f"""You are an AI recruiter. Evaluate how well this candidate fits the job.

Job Description:
{job_text_truncated}
"""
        
        if job_requirements:
            requirements_truncated = job_requirements[:800] if len(job_requirements) > 800 else job_requirements
            prompt += f"""
Job Requirements:
{requirements_truncated}
"""
        
        prompt += f"""
Candidate CV:
{cv_text_truncated}
"""
        
        if candidate_skills:
            prompt += f"""
Candidate Skills: {', '.join(candidate_skills[:20])}
"""
        
        if candidate_experience_years is not None:
            prompt += f"""
Candidate Experience: {candidate_experience_years} years
"""
        
        prompt += """
Evaluate the candidate's suitability for this role. Consider:
1. Technical skills alignment
2. Relevant work experience
3. Education and qualifications
4. Overall fit for the role

Rate suitability on a scale 0-100 for each dimension.

Return your evaluation as JSON in this exact format:
{
  "overall_score": <integer 0-100>,
  "experience_score": <integer 0-100>,
  "skill_score": <integer 0-100>,
  "explanation": "<2-3 sentence explanation of your evaluation>"
}

Important:
- Be objective and fair
- Consider both strengths and weaknesses
- Provide specific reasoning in the explanation
- Return ONLY valid JSON, no additional text
"""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        # strip markdown fences, parse JSON, clamp scores
        try:
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()

            result = json.loads(response_clean)

            overall_score = self._normalize_score(result.get("overall_score", 50))
            experience_score = self._normalize_score(result.get("experience_score", 50))
            skill_score = self._normalize_score(result.get("skill_score", 50))
            explanation = result.get("explanation", "Evaluation completed")
            
            return {
                "overall_score": overall_score,
                "experience_score": experience_score,
                "skill_score": skill_score,
                "explanation": explanation
            }
            
        except json.JSONDecodeError as e:
            logger.exception(f"CandidateEvaluator: Failed to parse JSON response: {e}")
            logger.info(f"CandidateEvaluator: Response was: {response[:200]}")
            
            # JSON parse failed - regex sweep as last resort
            import re
            overall_match = re.search(r'"overall_score":\s*(\d+)', response)
            experience_match = re.search(r'"experience_score":\s*(\d+)', response)
            skill_match = re.search(r'"skill_score":\s*(\d+)', response)
            explanation_match = re.search(r'"explanation":\s*"([^"]+)"', response)
            
            return {
                "overall_score": int(overall_match.group(1)) if overall_match else 50,
                "experience_score": int(experience_match.group(1)) if experience_match else 50,
                "skill_score": int(skill_match.group(1)) if skill_match else 50,
                "explanation": explanation_match.group(1) if explanation_match else "Evaluation completed (parsed with fallback)"
            }
    
    def _normalize_score(self, score: Any) -> int:
        # clamp to 0-100, default 50 on garbage input
        try:
            score_int = int(float(score))
            return max(0, min(100, score_int))
        except (ValueError, TypeError):
            return 50

