# Job description enhancer - biased language, clarity, missing keywords.
# GPT-4o-mini wrapper; degrades gracefully without an API key.
from typing import Dict, Any, List
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
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()

from ..llm.openai_client import OpenAIClient


class JobDescriptionEnhancer:
    # biased language, clarity, keywords, inclusivity nudges

    def __init__(self):
        self.client = None
        self.use_llm = False
        
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key.strip():
            try:
                self.client = OpenAIClient()
                self.use_llm = True
                logger.info("JobDescriptionEnhancer: Using OpenAI GPT-4o-mini")
            except Exception as e:
                logger.exception(f"JobDescriptionEnhancer: Failed to initialize OpenAI client: {e}")
                self.use_llm = False
        else:
            logger.info("JobDescriptionEnhancer: OpenAI API key not configured")
    
    def enhance_job_description(self, job_description: str, job_title: str = "") -> Dict[str, Any]:
        # returns dict: improved_description, identified_issues, explanation, bias_detected, improvements
        if not self.use_llm or not self.client:
            return {
                "improved_description": job_description,
                "identified_issues": [],
                "explanation": "AI enhancement not available. OpenAI API key not configured.",
                "bias_detected": False,
                "improvements": [],
                "llm_available": False
            }
        
        prompt = self._build_enhancement_prompt(job_description, job_title)
        
        try:
            logger.info("JobDescriptionEnhancer: Analyzing job description...")
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert HR consultant specializing in inclusive hiring and bias-free job descriptions. Analyze job descriptions for bias, clarity, and inclusivity."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = self.client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=1000
            )
            
            logger.info(f"JobDescriptionEnhancer: Received response (length: {len(response)})")
            
            # parse JSON
            result = self._parse_response(response)
            result["llm_available"] = True
            return result
            
        except Exception as e:
            import traceback
            logger.exception(f"JobDescriptionEnhancer: Error during enhancement: {e}")
            logger.info(f"JobDescriptionEnhancer: Traceback: {traceback.format_exc()}")
            
            return {
                "improved_description": job_description,
                "identified_issues": [],
                "explanation": f"Enhancement failed: {str(e)}",
                "bias_detected": False,
                "improvements": [],
                "llm_available": False,
                "error": str(e)
            }
    
    def _build_enhancement_prompt(self, job_description: str, job_title: str) -> str:
        prompt = f"""Analyze the following job description for clarity, inclusivity, and bias.

Job Title: {job_title if job_title else "Not specified"}

Job Description:
{job_description}

Identify and address:
1. **Biased language**: Words that may exclude certain groups (e.g., "young", "rockstar", "native speaker", gender-coded words)
2. **Clarity issues**: Unclear requirements, vague descriptions, ambiguous qualifications
3. **Keyword optimization**: Missing important keywords, poor SEO for job boards
4. **Inclusivity**: Language that may discourage diverse candidates

Return your analysis as JSON with this exact structure:
{{
  "improved_description": "<rewritten job description with improvements>",
  "identified_issues": ["<list of specific issues found>"],
  "explanation": "<2-3 sentence explanation of key changes and why>",
  "bias_detected": <true/false>,
  "improvements": ["<list of specific improvements made>"]
}}

Important:
- Keep the core requirements and responsibilities intact
- Only improve language, don't change the job requirements
- Be specific about what was changed and why
- Return ONLY valid JSON, no additional text"""
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        # strip the usual markdown fence the LLM sometimes wraps around JSON
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

            # backfill any missing keys with sane defaults
            return {
                "improved_description": result.get("improved_description", ""),
                "identified_issues": result.get("identified_issues", []),
                "explanation": result.get("explanation", ""),
                "bias_detected": result.get("bias_detected", False),
                "improvements": result.get("improvements", [])
            }
            
        except json.JSONDecodeError as e:
            logger.exception(f"JobDescriptionEnhancer: Failed to parse JSON: {e}")
            logger.info(f"JobDescriptionEnhancer: Response: {response[:200]}")
            
            # parse failed - empty fields + error message
            return {
                "improved_description": "",
                "identified_issues": ["Failed to parse AI response"],
                "explanation": "Could not parse enhancement response. Please try again.",
                "bias_detected": False,
                "improvements": []
            }

