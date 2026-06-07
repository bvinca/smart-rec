# Skill-gap analyser - semantic similarity so K8s/Kubernetes still match.
# Buckets: strong (>=70), weak (30-70), missing (<30).
from typing import Dict, List, Any, Optional
import sys
import os

import logging
logger = logging.getLogger(__name__)

# add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '../../../backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from ..embeddings.vectorizer import EmbeddingVectorizer
from ..embeddings.similarity import SimilarityCalculator
from .. import utils as ai_utils


class SkillGapVisualizer:
    # job_skills vs candidate_skills alignment via embeddings

    def __init__(self):
        self.vectorizer = EmbeddingVectorizer()

    def compute_skill_similarity(
        self,
        job_skills: List[str],
        candidate_skills: List[str]
    ) -> Dict[str, Any]:
        # returns dict: skill_matches (per-skill %), missing_skills, strong_matches,
        # weak_matches, overall_alignment, total_job_skills, matched_skills, message
        if not job_skills:
            return {
                "skill_matches": {},
                "missing_skills": [],
                "strong_matches": [],
                "weak_matches": [],
                "overall_alignment": 0.0,
                "message": "No job skills provided"
            }
        
        if not candidate_skills:
            return {
                "skill_matches": {skill: 0.0 for skill in job_skills},
                "missing_skills": job_skills,
                "strong_matches": [],
                "weak_matches": [],
                "overall_alignment": 0.0,
                "message": "No candidate skills provided"
            }
        
        try:
            # embed everything once up front
            logger.info(f"SkillGapVisualizer: Computing similarity for {len(job_skills)} job skills vs {len(candidate_skills)} candidate skills")
            
            job_embeddings = {}
            candidate_embeddings = {}
            
            # job skills
            for skill in job_skills:
                try:
                    job_embeddings[skill] = self.vectorizer.generate_embedding(skill)
                except Exception as e:
                    logger.exception(f"SkillGapVisualizer: Error embedding job skill '{skill}': {e}")
                    job_embeddings[skill] = None
            
            # candidate skills
            for skill in candidate_skills:
                try:
                    candidate_embeddings[skill] = self.vectorizer.generate_embedding(skill)
                except Exception as e:
                    logger.exception(f"SkillGapVisualizer: Error embedding candidate skill '{skill}': {e}")
                    candidate_embeddings[skill] = None
            
            # for each job skill, find its best-matching candidate skill
            skill_matches = {}
            candidate_skill_vectors = [
                emb for emb in candidate_embeddings.values() if emb is not None
            ]
            
            for job_skill in job_skills:
                if job_embeddings[job_skill] is None:
                    skill_matches[job_skill] = 0.0
                    continue
                
                # take the max similarity across all candidate skills
                best_similarity = 0.0
                for cand_emb in candidate_skill_vectors:
                    if cand_emb:
                        similarity = ai_utils.calculate_cosine_similarity(
                            job_embeddings[job_skill],
                            cand_emb
                        )
                        # -1..1 -> 0..100
                        similarity_percent = ai_utils.similarity_to_score(similarity)
                        best_similarity = max(best_similarity, similarity_percent)
                
                skill_matches[job_skill] = round(best_similarity, 2)
            
            # bucket: strong >= 70, weak 30-70, missing < 30
            strong_matches = [skill for skill, score in skill_matches.items() if score >= 70]
            weak_matches = [skill for skill, score in skill_matches.items() if 30 <= score < 70]
            missing_skills = [skill for skill, score in skill_matches.items() if score < 30]

            # overall = mean of per-skill scores
            if skill_matches:
                overall_alignment = sum(skill_matches.values()) / len(skill_matches)
            else:
                overall_alignment = 0.0
            
            return {
                "skill_matches": skill_matches,
                "missing_skills": missing_skills,
                "strong_matches": strong_matches,
                "weak_matches": weak_matches,
                "overall_alignment": round(overall_alignment, 2),
                "total_job_skills": len(job_skills),
                "matched_skills": len(strong_matches),
                "message": f"Overall skill alignment: {overall_alignment:.1f}%"
            }
            
        except Exception as e:
            import traceback
            logger.exception(f"SkillGapVisualizer: Error computing similarity: {e}")
            logger.info(f"SkillGapVisualizer: Traceback: {traceback.format_exc()}")
            
            return {
                "skill_matches": {},
                "missing_skills": job_skills,
                "strong_matches": [],
                "weak_matches": [],
                "overall_alignment": 0.0,
                "error": str(e)
            }
    
    def extract_skills_from_text(self, text: str) -> List[str]:
        # quick-and-dirty keyword sweep. The real ontology-based extractor lives in nlp/.
        # quick keyword sweep - use skill ontology find_in_text for real extraction
        common_skills = [
            'python', 'java', 'javascript', 'typescript', 'react', 'vue', 'angular',
            'node', 'express', 'fastapi', 'django', 'flask', 'spring',
            'sql', 'postgresql', 'mongodb', 'mysql', 'redis',
            'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'terraform',
            'git', 'ci/cd', 'jenkins', 'github actions',
            'machine learning', 'deep learning', 'nlp', 'tensorflow', 'pytorch',
            'html', 'css', 'sass', 'redux', 'graphql', 'rest api',
            'microservices', 'agile', 'scrum', 'devops', 'linux', 'bash'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in common_skills:
            if skill in text_lower:
                found_skills.append(skill.title())
        
        return found_skills

