# Interview question generator - OpenAI, HuggingFace T5, or deterministic templates.
# Deterministic path used by the no-LLM evaluation harness.
from typing import Dict, Any, List, Optional
import re
import sys
import os

import logging
logger = logging.getLogger(__name__)

# add backend to path so we can import config
backend_path = os.path.join(os.path.dirname(__file__), '../../../backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.config import settings  # type: ignore
except ImportError:
    # standalone-script fallback
    class Settings:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    settings = Settings()  # type: ignore

# model-selection env vars - decoupled from settings
_QUESTION_GENERATION_MODEL = os.environ.get("QUESTION_GENERATION_MODEL", "auto")
_HUGGINGFACE_QUESTION_MODEL = os.environ.get("HUGGINGFACE_QUESTION_MODEL", "t5-small")

from .openai_client import OpenAIClient


class QuestionGenerator:
    # contextual interview questions via OpenAI, HuggingFace T5, or templates

    def __init__(self):
        self.use_openai = False
        self.use_huggingface = False
        self.client = None
        self.t5_model = None
        self.t5_tokenizer = None

        model_choice = _QUESTION_GENERATION_MODEL.lower()

        # don't accept an empty key string as "set"
        api_key_set = settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip()

        if model_choice == "auto":
            # auto = openai if there's a key, else T5
            if api_key_set:
                model_choice = "openai"
            else:
                logger.info("QuestionGenerator: OPENAI_API_KEY not set or empty, using HuggingFace")
                model_choice = "huggingface"
        
        if model_choice == "openai" and api_key_set:
            try:
                logger.info(f"QuestionGenerator: Initializing OpenAI client with API key (length: {len(settings.OPENAI_API_KEY)})...")
                self.client = OpenAIClient()
                self.use_openai = True
                logger.info("QuestionGenerator: Successfully initialized OpenAI GPT-4o-mini")
            except ValueError as e:
                logger.exception(f"QuestionGenerator: OpenAI API key validation failed: {e}")
                if "not set" in str(e).lower():
                    logger.info("QuestionGenerator: Falling back to HuggingFace")
                    model_choice = "huggingface"
                else:
                    raise
            except Exception as e:
                import traceback
                logger.exception(f"QuestionGenerator: Failed to initialize OpenAI client: {e}")
                logger.info(f"QuestionGenerator: Traceback: {traceback.format_exc()}")
                logger.info("QuestionGenerator: Falling back to HuggingFace")
                model_choice = "huggingface"
        
        if model_choice == "huggingface" or not self.use_openai:
            try:
                from transformers import T5ForConditionalGeneration, T5Tokenizer
                model_name = _HUGGINGFACE_QUESTION_MODEL
                logger.info(f"QuestionGenerator: Loading HuggingFace model {model_name}...")
                self.t5_tokenizer = T5Tokenizer.from_pretrained(model_name)
                self.t5_model = T5ForConditionalGeneration.from_pretrained(model_name)
                self.use_huggingface = True
                logger.info(f"QuestionGenerator: Using HuggingFace {model_name}")
            except ImportError:
                # no OpenAI, no transformers - deterministic path still works
                # generator still works and ctor must succeed
                logger.info(
                    "QuestionGenerator: neither OpenAI key nor transformers "
                    "available; LLM-driven generation disabled. Deterministic "
                    "questions still work."
                )
            except Exception as e:
                logger.exception(f"Failed to load HuggingFace model: {e}")
                # same idea - fall back silently, ctor must still succeed
                logger.info(
                    "QuestionGenerator: LLM-driven generation unavailable "
                    "(%s); deterministic questions still work.", e,
                )
    
    def generate_interview_questions(
        self,
        parsed_data: Dict[str, Any],
        job_description: Optional[str] = None,
        num_questions: int = 5,
        context: Optional[List[str]] = None,
    ) -> List[str]:
        # `context` is optional retrieved RAG chunks (rubrics/role guides) the LLM can ground in
        resume_text = parsed_data.get("resume_text", "")
        skills = parsed_data.get("skills", [])
        work_experience = parsed_data.get("work_experience", [])

        context_block = ""
        if context:
            context_block = (
                "\nRetrieved interview / role rubrics (use to ground the questions):\n"
                + "\n".join(f"- {c}" for c in context[:3])
            )

        prompt = f"""Generate {num_questions} relevant interview questions for this candidate based on their resume.
        
Resume Text:
{resume_text[:1500]}

Key Skills: {', '.join(skills[:10])}
Work Experience: {len(work_experience)} positions

{f'Job Description: {job_description[:500]}' if job_description else ''}
{context_block}

Generate {num_questions} specific, actionable interview questions that:
1. Assess technical skills mentioned in the resume
2. Evaluate experience relevant to the role
3. Test problem-solving abilities
4. Are specific and actionable, grounded in any retrieved rubrics above

Return only the questions, one per line, numbered 1-{num_questions}."""
        
        try:
            if self.use_openai and self.client:
                logger.info(f"QuestionGenerator: Generating {num_questions} questions using OpenAI...")
                messages = [
                    {"role": "system", "content": "You are a professional recruiter. Generate relevant, specific interview questions."},
                    {"role": "user", "content": prompt}
                ]
                content = self.client.chat_completion(messages, max_tokens=500)
                
                logger.info(f"QuestionGenerator: Received response from OpenAI (length: {len(content)})")
                
                # parse numbered/dashed lines into individual questions
                questions = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-')):
                        question = re.sub(r'^\d+[\.\)]\s*|^-\s*', '', line)
                        if question:
                            questions.append(question)

                if questions:
                    logger.info(f"QuestionGenerator: Successfully parsed {len(questions)} questions")
                    return questions[:num_questions]
                else:
                    logger.info("QuestionGenerator: No questions parsed from response, using default questions")
                    logger.info(f"QuestionGenerator: Response content: {content[:200]}")
                    return self._default_questions()
            elif self.use_huggingface and self.t5_model and self.t5_tokenizer:
                # T5 - one question per prefix beats asking for a list
                questions = []

                context = f"Resume: {resume_text[:800]} Skills: {', '.join(skills[:10])}"
                if job_description:
                    context += f" Job: {job_description[:400]}"

                # rotate through prefixes to spread questions across themes
                question_prefixes = [
                    "generate interview question about experience:",
                    "generate interview question about skills:",
                    "generate interview question about problem solving:",
                    "generate interview question about motivation:",
                    "generate interview question about fit:"
                ]
                
                for i, prefix in enumerate(question_prefixes[:num_questions]):
                    try:
                        input_text = f"{prefix} {context}"

                        input_ids = self.t5_tokenizer.encode(
                            input_text,
                            max_length=512,
                            truncation=True,
                            return_tensors="pt"
                        )

                        output_ids = self.t5_model.generate(
                            input_ids,
                            max_length=100,
                            num_beams=3,
                            early_stopping=True,
                            do_sample=True,
                            temperature=0.7,
                            num_return_sequences=1
                        )

                        question = self.t5_tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()

                        # strip leading "Q:" / "question:" and force a trailing ?
                        question = re.sub(r'^(question|q):\s*', '', question, flags=re.IGNORECASE)
                        if question and len(question) > 15 and question.endswith('?'):
                            questions.append(question)
                        elif question and len(question) > 15:
                            questions.append(question + "?")
                    except Exception as e:
                        logger.exception(f"Error generating question {i+1} with T5: {e}")
                        continue

                # if T5 came up short, fill from skills with a simple template
                if len(questions) < num_questions:
                    remaining = num_questions - len(questions)
                    for skill in skills[:remaining]:
                        if len(questions) >= num_questions:
                            break
                        template = f"generate interview question: What is your experience with {skill}?"
                        try:
                            template_ids = self.t5_tokenizer.encode(template, return_tensors="pt", max_length=100, truncation=True)
                            template_output = self.t5_model.generate(template_ids, max_length=60, num_beams=2, do_sample=True)
                            question = self.t5_tokenizer.decode(template_output[0], skip_special_tokens=True).strip()
                            if question and len(question) > 10:
                                if not question.endswith('?'):
                                    question += "?"
                                questions.append(question)
                        except:
                            pass
                
                return questions[:num_questions] if questions else self._default_questions()
            else:
                # no model path worked - use defaults
                logger.info("QuestionGenerator: No OpenAI or HuggingFace model available, using default questions")
                return self._default_questions()
        except Exception as e:
            import traceback
            logger.exception(f"QuestionGenerator: Error generating interview questions: {e}")
            logger.info(f"QuestionGenerator: Traceback: {traceback.format_exc()}")
            return self._default_questions()
    
    def regenerate_questions_with_feedback(
        self,
        parsed_data: Dict[str, Any],
        current_questions: List[str],
        feedback: str,
        job_description: Optional[str] = None,
        num_questions: int = 5
    ) -> List[str]:
        # second pass - recruiter feedback -> LLM regenerates questions
        resume_text = parsed_data.get("resume_text", "")
        skills = parsed_data.get("skills", [])
        work_experience = parsed_data.get("work_experience", [])
        
        current_questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(current_questions)])
        
        prompt = f"""A recruiter has provided feedback on the following interview questions. Please regenerate {num_questions} improved questions based on their feedback.

Current Questions:
{current_questions_text}

Recruiter Feedback:
{feedback}

Candidate Resume:
{resume_text[:1500]}

Key Skills: {', '.join(skills[:10])}
Work Experience: {len(work_experience)} positions

{f'Job Description: {job_description[:500]}' if job_description else ''}

Please generate {num_questions} improved interview questions that address the recruiter's feedback. The new questions should:
1. Address the specific concerns mentioned in the feedback
2. Still be relevant to the candidate's resume and the job
3. Be specific and actionable
4. Be better than the original questions based on the feedback

Return only the questions, one per line, numbered 1-{num_questions}."""
        
        try:
            if self.use_openai and self.client:
                logger.info(f"QuestionGenerator: Regenerating {num_questions} questions with feedback using OpenAI...")
                messages = [
                    {"role": "system", "content": "You are a professional recruiter. Generate improved interview questions based on feedback."},
                    {"role": "user", "content": prompt}
                ]
                content = self.client.chat_completion(messages, max_tokens=600)
                
                logger.info(f"QuestionGenerator: Received regenerated response from OpenAI (length: {len(content)})")
                
                # parse numbered/dashed lines
                questions = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-')):
                        question = re.sub(r'^\d+[\.\)]\s*|^-\s*', '', line)
                        if question:
                            questions.append(question)

                if questions:
                    logger.info(f"QuestionGenerator: Successfully parsed {len(questions)} regenerated questions")
                    return questions[:num_questions]
                else:
                    logger.info("QuestionGenerator: No questions parsed from regenerated response, using default questions")
                    return self._default_questions()
            else:
                # no LLM - return existing questions unchanged
                logger.info("QuestionGenerator: OpenAI not available for regeneration, returning current questions")
                return current_questions
        except Exception as e:
            import traceback
            logger.exception(f"QuestionGenerator: Error regenerating questions: {e}")
            logger.info(f"QuestionGenerator: Traceback: {traceback.format_exc()}")
            return current_questions  # keep what we had on error

    def _default_questions(self) -> List[str]:
        # fallback list if generation fails
        return [
            "Tell me about your experience with the technologies mentioned in this role.",
            "Describe a challenging project you worked on and how you solved it.",
            "How do you stay updated with industry trends?",
            "What motivates you in your career?",
            "Why are you interested in this position?"
        ]

    def generate_deterministic_questions(
        self,
        parsed_data: Dict[str, Any],
        job_title: Optional[str] = None,
        job_description: Optional[str] = None,
        matched_skills: Optional[List[str]] = None,
        missing_skills: Optional[List[str]] = None,
        timeline_warnings: Optional[List[Dict[str, Any]]] = None,
        num_questions: int = 6,
    ) -> List[str]:
        # Deterministic interview Qs from matched/missing skills, recent role, timeline warnings.
        # No LLM - more useful than _default_questions. Same signature as generate_interview_questions.
        questions: List[str] = []
        matched = [s for s in (matched_skills or []) if s]
        missing = [s for s in (missing_skills or []) if s]
        work_experience = parsed_data.get("work_experience") or []
        exp_years = parsed_data.get("experience_years") or 0.0

        # 1. tech questions on the top 2 matched skills
        for skill in matched[:2]:
            questions.append(
                f"Walk me through a project where you used {skill}. "
                f"What was the most challenging technical decision you had to make, "
                f"and why did you make it that way?"
            )

        # 2. skill-gap probe on top missing skill
        if missing:
            top_missing = missing[0]
            questions.append(
                f"This role uses {top_missing}, which doesn't appear on your CV. "
                f"What is the closest related experience you have, and how would "
                f"you expect to ramp up on it?"
            )

        # 3. anchored in the most recent role
        if work_experience:
            recent = work_experience[0]
            title = (recent.get("title") or "your most recent role").strip()
            company = (recent.get("company") or "").strip()
            if company:
                questions.append(
                    f"Tell me about your work as {title} at {company}. "
                    f"What was the single biggest contribution you made there, "
                    f"and what did you learn from it?"
                )
            else:
                questions.append(
                    f"Tell me about your role as {title}. "
                    f"What was the single biggest contribution you made, "
                    f"and what did you learn from it?"
                )

        # 4. follow up on any timeline weirdness the validator flagged
        if timeline_warnings:
            codes = {w.get("code") for w in timeline_warnings if isinstance(w, dict)}
            if "experience_exceeds_work_history" in codes or "experience_exceeds_timeline" in codes:
                questions.append(
                    f"Your CV lists {exp_years:.0f} years of experience, but the work "
                    f"history we could parse doesn't fully account for that. Could you "
                    f"talk us through any earlier roles or projects we may have missed?"
                )
            elif "overlapping_roles" in codes:
                questions.append(
                    "Two of your work entries overlap by more than a year. Were these "
                    "part-time / consulting engagements running in parallel, or could "
                    "you clarify the dates?"
                )

        # 5. one open behavioural question
        questions.append(
            "Describe a time when you disagreed with a technical decision your team "
            "made. How did you handle the disagreement, and what was the outcome?"
        )

        # 6. role-fit closer - uses job title when available
        if job_title:
            questions.append(
                f"What about the {job_title} role specifically attracted you, and "
                f"where do you think you will need to stretch the most in the first "
                f"three months?"
            )
        else:
            questions.append(
                "What about this role specifically attracted you, and where do you "
                "think you will need to stretch the most in the first three months?"
            )

        # de-dup preserving order, then cap
        seen = set()
        deduped: List[str] = []
        for q in questions:
            if q not in seen:
                seen.add(q)
                deduped.append(q)
            if len(deduped) >= num_questions:
                break
        return deduped[:num_questions]

