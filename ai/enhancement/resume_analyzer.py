# Resume analyzer - actionable CV feedback vs an optional job description.
# Flags missing skills, weak phrasing, ATS keyword gaps. No-op without OpenAI key.
from typing import Dict, Any, List, Optional
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


class ResumeAnalyzer:
    # resume feedback - missing skills, weak phrasing, keyword tips

    def __init__(self):
        self.client = None
        self.use_llm = False
        
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key.strip():
            try:
                self.client = OpenAIClient()
                self.use_llm = True
                logger.info("ResumeAnalyzer: Using OpenAI GPT-4o-mini")
            except Exception as e:
                logger.exception(f"ResumeAnalyzer: Failed to initialize OpenAI client: {e}")
                self.use_llm = False
        else:
            logger.info("ResumeAnalyzer: OpenAI API key not configured")
    
    def analyze_resume(
        self,
        resume_text: str,
        job_description: Optional[str] = None,
        job_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        # returns dict: missing_skills, suggested_phrasing, summary_feedback,
        # strengths, weaknesses, keyword_suggestions
        if not self.use_llm or not self.client:
            return {
                "missing_skills": [],
                "suggested_phrasing": [],
                "summary_feedback": "AI analysis not available. OpenAI API key not configured.",
                "strengths": [],
                "weaknesses": [],
                "keyword_suggestions": [],
                "llm_available": False
            }
        
        prompt = self._build_analysis_prompt(resume_text, job_description, job_requirements)
        
        try:
            logger.info("ResumeAnalyzer: Analyzing resume...")
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional career counselor. Provide constructive, actionable feedback to help candidates improve their resumes."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = self.client.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=800
            )
            
            logger.info(f"ResumeAnalyzer: Received response (length: {len(response)})")
            
            # parse JSON
            result = self._parse_response(response)
            result["llm_available"] = True
            return result
            
        except Exception as e:
            import traceback
            logger.exception(f"ResumeAnalyzer: Error during analysis: {e}")
            logger.info(f"ResumeAnalyzer: Traceback: {traceback.format_exc()}")
            
            return {
                "missing_skills": [],
                "suggested_phrasing": [],
                "summary_feedback": f"Analysis failed: {str(e)}",
                "strengths": [],
                "weaknesses": [],
                "keyword_suggestions": [],
                "llm_available": False,
                "error": str(e)
            }
    
    def _build_analysis_prompt(
        self,
        resume_text: str,
        job_description: Optional[str],
        job_requirements: Optional[str]
    ) -> str:
        # truncate aggressively to stay under the token limit
        resume_truncated = resume_text[:2000] if len(resume_text) > 2000 else resume_text
        
        prompt = f"""Review the candidate's resume and provide constructive feedback.

Resume:
{resume_truncated}
"""
        
        if job_description:
            job_desc_truncated = job_description[:1500] if len(job_description) > 1500 else job_description
            prompt += f"""
Job Description:
{job_desc_truncated}
"""
        
        if job_requirements:
            req_truncated = job_requirements[:1000] if len(job_requirements) > 1000 else job_requirements
            prompt += f"""
Job Requirements:
{req_truncated}
"""
        
        prompt += """
Provide feedback on:
1. Missing skills or experience that would strengthen the resume
2. Weak phrasing that could be improved
3. Keyword suggestions for better ATS compatibility
4. Overall strengths and weaknesses

Return your analysis as JSON with this exact structure:
{
  "missing_skills": ["<list of skills that could be added>"],
  "suggested_phrasing": [
    {
      "original": "<weak phrase from resume>",
      "improved": "<suggested improvement>",
      "reason": "<why this is better>"
    }
  ],
  "summary_feedback": "<2-3 paragraph overall feedback>",
  "strengths": ["<list of resume strengths>"],
  "weaknesses": ["<list of areas for improvement>"],
  "keyword_suggestions": ["<keywords to add for better matching>"]
}

Important:
- Be constructive and specific
- Provide actionable suggestions
- Focus on improvements that would increase job match
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
                "missing_skills": result.get("missing_skills", []),
                "suggested_phrasing": result.get("suggested_phrasing", []),
                "summary_feedback": result.get("summary_feedback", ""),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "keyword_suggestions": result.get("keyword_suggestions", [])
            }
            
        except json.JSONDecodeError as e:
            logger.exception(f"ResumeAnalyzer: Failed to parse JSON: {e}")
            logger.info(f"ResumeAnalyzer: Response: {response[:200]}")
            
            return {
                "missing_skills": [],
                "suggested_phrasing": [],
                "summary_feedback": "Could not parse analysis response. Please try again.",
                "strengths": [],
                "weaknesses": [],
                "keyword_suggestions": []
            }

