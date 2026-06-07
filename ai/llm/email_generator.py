# Email generator - context-aware candidate messages.
# Supports: acknowledgment, feedback, rejection, interview_invitation, hired.
# Falls back to canned templates when no OpenAI key is configured.
from typing import Dict, Any, Optional, List
import json
import sys
import os

import logging
logger = logging.getLogger(__name__)

# add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '../../backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings
except ImportError:
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()

from .openai_client import OpenAIClient
from ai.ai_utils.pii import maybe_redact


class EmailGenerator:
    # personalised candidate emails. Five message types supported (see _build_prompt).

    def __init__(self):
        self.client = None
        self.use_llm = False
        self.default_tone = "professional, concise, and encouraging"
        
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key.strip():
            try:
                self.client = OpenAIClient()
                self.use_llm = True
                logger.info("EmailGenerator: Using OpenAI GPT-4o-mini")
            except Exception as e:
                logger.exception(f"EmailGenerator: Failed to initialize OpenAI client: {e}")
                self.use_llm = False
        else:
            logger.info("EmailGenerator: OpenAI API key not configured")
    
    def generate_email(
        self,
        candidate_name: str,
        job_title: str,
        message_type: str = "feedback",
        score_data: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        tone: Optional[str] = None
    ) -> str:
        # generate a personalised email; falls back to the static template if no LLM
        if not self.use_llm:
            return self._generate_fallback_email(candidate_name, job_title, message_type, score_data)

        tone = tone or self.default_tone

        # PII redaction before LLM - name/title first
        pii_enabled: bool = getattr(settings, "LLM_PII_REDACTION", True)
        safe_name = maybe_redact(candidate_name, enabled=pii_enabled, candidate_names=[candidate_name])
        safe_job_title = maybe_redact(job_title, enabled=pii_enabled)

        # build score-summary lines from whatever score_data we got
        score_context = ""
        if score_data:
            score_parts = []
            if "overall_score" in score_data:
                score_parts.append(f"Overall match score: {score_data['overall_score']:.1f}%")
            if "skill_score" in score_data:
                score_parts.append(f"Skills score: {score_data['skill_score']:.1f}%")
            if "experience_score" in score_data:
                score_parts.append(f"Experience score: {score_data['experience_score']:.1f}%")
            if "education_score" in score_data:
                score_parts.append(f"Education score: {score_data['education_score']:.1f}%")
            score_context = "\n".join(score_parts)
        
        # extra context - missing skills, strengths, weaknesses (capped)
        context_str = ""
        if additional_context:
            context_parts = []
            if "missing_skills" in additional_context and additional_context["missing_skills"]:
                skills = ", ".join(additional_context["missing_skills"][:5])  # Limit to 5
                context_parts.append(f"Missing skills: {skills}")
            if "strengths" in additional_context and additional_context["strengths"]:
                strengths = ", ".join(additional_context["strengths"][:3])  # Limit to 3
                context_parts.append(f"Key strengths: {strengths}")
            if "weaknesses" in additional_context and additional_context["weaknesses"]:
                weaknesses = ", ".join(additional_context["weaknesses"][:3])  # Limit to 3
                context_parts.append(f"Areas for improvement: {weaknesses}")
            context_str = "\n".join(context_parts)
        
        # prompt depends on message type
        system_prompt = "You are a professional HR recruiter writing emails to candidates. Write clear, respectful, and personalized messages."
        
        user_prompt = self._build_prompt(
            safe_name, safe_job_title, message_type, score_context, context_str, tone
        )
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            email_content = self.client.chat_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=500
            )
            
            return email_content.strip()
        except Exception as e:
            logger.exception(f"EmailGenerator: Error generating email: {e}")
            return self._generate_fallback_email(candidate_name, job_title, message_type, score_data)
    
    def _build_prompt(
        self,
        candidate_name: str,
        job_title: str,
        message_type: str,
        score_context: str,
        context_str: str,
        tone: str
    ) -> str:
        # picks the right template per message_type
        
        base_info = f"""
Candidate name: {candidate_name}
Job title: {job_title}
Tone: {tone}
"""
        
        if message_type == "acknowledgment":
            return f"""{base_info}
Write an acknowledgment email thanking the candidate for applying to the {job_title} position.
Keep it brief (80-120 words), professional, and welcoming.
Include:
- Thank you for applying
- Confirmation that their application was received
- Next steps (e.g., "We will review your application and get back to you")
- Professional closing
"""
        
        elif message_type == "feedback":
            feedback_info = f"""
{base_info}
{score_context}
{context_str}
"""
            return f"""{feedback_info}
Write a constructive feedback email to the candidate about their application for {job_title}.
Keep it encouraging and professional (100-150 words).
Include:
- Acknowledgment of their application
- Positive feedback on their strengths
- Constructive suggestions for areas of improvement (if applicable)
- Encouragement for future opportunities
- Professional closing
"""
        
        elif message_type == "rejection":
            rejection_info = f"""
{base_info}
{score_context}
{context_str}
"""
            return f"""{rejection_info}
Write a respectful rejection email to the candidate for the {job_title} position.
Be empathetic and professional (80-120 words).
Include:
- Thank you for their interest and time
- Acknowledge that this was a difficult decision
- Keep it brief and avoid overly detailed explanations
- Encourage them for future opportunities
- Professional closing
"""
        
        elif message_type == "interview_invitation":
            return f"""{base_info}
Write an interview invitation email to the candidate for the {job_title} position.
Be enthusiastic and clear (100-150 words).
Include:
- Congratulations on being shortlisted
- Excitement about their candidacy
- Request to schedule an interview
- Next steps (they can expect a follow-up to schedule)
- Professional closing
"""
        
        elif message_type == "hired":
            return f"""{base_info}
Write a job offer/hiring confirmation email to the candidate for the {job_title} position.
Be enthusiastic, congratulatory, and clear (120-180 words).
Include:
- Congratulations on being selected
- Excitement about them joining the team
- Next steps (onboarding, start date discussion, etc.)
- Professional closing
"""
        
        else:
            # generic catch-all
            return f"""{base_info}
{score_context}
{context_str}

Write a professional email to the candidate about the {job_title} position.
Keep it concise (100-150 words) and maintain a {tone} tone.
"""
    
    def _generate_fallback_email(
        self,
        candidate_name: str,
        job_title: str,
        message_type: str,
        score_data: Optional[Dict[str, Any]] = None
    ) -> str:
        # static templates when no OpenAI key
        
        if message_type == "acknowledgment":
            return f"""Dear {candidate_name},

Thank you for your interest in the {job_title} position. We have received your application and will review it carefully.

We will be in touch soon regarding the next steps in our hiring process.

Best regards,
Recruitment Team"""
        
        elif message_type == "feedback":
            score_text = ""
            if score_data and "overall_score" in score_data:
                score_text = f" Your application received a match score of {score_data['overall_score']:.1f}%."  # tack the score onto the body if we have one
            return f"""Dear {candidate_name},

Thank you for applying to the {job_title} position.{score_text}

We appreciate your interest and will keep your application on file for future opportunities.

Best regards,
Recruitment Team"""
        
        elif message_type == "rejection":
            return f"""Dear {candidate_name},

Thank you for your interest in the {job_title} position. After careful consideration, we have decided not to move forward with your application at this time.

We appreciate the time you invested in the application process and wish you the best in your career search.

Best regards,
Recruitment Team"""
        
        elif message_type == "interview_invitation":
            return f"""Dear {candidate_name},

Congratulations! We were impressed with your application for the {job_title} position and would like to invite you for an interview.

We will contact you shortly to schedule a convenient time.

We look forward to speaking with you.

Best regards,
Recruitment Team"""
        
        elif message_type == "hired":
            return f"""Dear {candidate_name},

Congratulations! We are thrilled to offer you the {job_title} position. We were very impressed with your qualifications and believe you will be a great addition to our team.

We will contact you shortly to discuss the next steps, including your start date and onboarding process.

We look forward to welcoming you to our team!

Best regards,
Recruitment Team"""
        
        else:
            return f"""Dear {candidate_name},

Thank you for your interest in the {job_title} position.

We will be in touch regarding next steps.

Best regards,
Recruitment Team"""

