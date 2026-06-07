# RAG pipeline entry point for API routers.
# Sentence-BERT retriever (seed corpus + jobs) + OpenAI generator.

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ai.rag.generator import RAGGenerator
from ai.rag.retriever import RAGRetriever, get_retriever

logger = logging.getLogger(__name__)


class RAGPipeline:
    # end-to-end retrieve + generate

    def __init__(self, retriever: Optional[RAGRetriever] = None) -> None:
        self.retriever = retriever or get_retriever()
        self.generator = RAGGenerator()
        self._question_generator = None  # lazy - most calls skip interview Qs

    # summary
    def generate_summary(
        self,
        resume_text: str,
        job_description: str,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        chunks = self.retriever.retrieve_chunks(job_description, k=top_k)
        context = [chunk.as_context() for chunk in chunks]
        result = self.generator.generate_summary(resume_text, job_description, context)
        result["retrieved_documents"] = [
            {"doc_id": c.doc_id, "title": c.title, "score": round(c.score, 4)}
            for c in chunks
        ]
        return result

    # feedback
    def generate_feedback(
        self,
        resume_text: str,
        job_description: str,
        scores: Dict[str, float],
        top_k: int = 2,
    ) -> str:
        chunks = self.retriever.retrieve_chunks(job_description, k=top_k)
        context = [chunk.as_context() for chunk in chunks]
        return self.generator.generate_feedback(
            resume_text, job_description, scores, context
        )

    # interview Qs
    def generate_interview_questions(
        self,
        resume_text: str,
        job_description: str,
        num_questions: int = 5,
        top_k: int = 3,
    ) -> List[str]:
        if self._question_generator is None:
            from ai.llm.question_generator import QuestionGenerator

            self._question_generator = QuestionGenerator()

        # pull behavioural / technical rubrics from the retriever so the
        # question generator has something concrete to ground in
        chunks = self.retriever.retrieve_chunks(
            f"interview rubric for: {job_description}", k=top_k
        )
        parsed_data = {
            "resume_text": resume_text,
            "skills": [],
            "work_experience": [],
        }
        return self._question_generator.generate_interview_questions(
            parsed_data,
            job_description,
            num_questions,
            context=[c.as_context() for c in chunks],
        )

    def regenerate_questions_with_feedback(
        self,
        resume_text: str,
        current_questions: List[str],
        feedback: str,
        job_description: str,
        num_questions: int = 5,
    ) -> List[str]:
        if self._question_generator is None:
            from ai.llm.question_generator import QuestionGenerator

            self._question_generator = QuestionGenerator()

        parsed_data = {
            "resume_text": resume_text,
            "skills": [],
            "work_experience": [],
        }
        return self._question_generator.regenerate_questions_with_feedback(
            parsed_data,
            current_questions,
            feedback,
            job_description,
            num_questions,
        )
