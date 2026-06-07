# Central prompt templates - keeps LLM prompt strings in one place


class PromptTemplates:

    @staticmethod
    def candidate_summary(resume_text: str, skills: list, experience_years: float, job_description: str = None) -> str:
        prompt = f"""Summarize this candidate's profile in one concise paragraph (2-3 sentences). Focus on:
- Years of experience
- Key technical skills
- Notable work experience
- Education background
"""
        if job_description:
            prompt += f"\nConsider this job description for context:\n{job_description[:500]}"

        prompt += f"""
Resume Text:
{resume_text[:2000]}

Skills: {', '.join(skills[:10])}
Experience: {experience_years} years

Provide a professional summary:"""
        return prompt

    @staticmethod
    def interview_questions(resume_text: str, skills: list, job_description: str = None, num_questions: int = 5) -> str:
        prompt = f"""Generate {num_questions} relevant interview questions for this candidate based on their resume.

Resume Text:
{resume_text[:1500]}

Key Skills: {', '.join(skills[:10])}
"""
        if job_description:
            prompt += f"\nJob Description: {job_description[:500]}"

        prompt += f"""
Generate {num_questions} specific, actionable interview questions that:
1. Assess technical skills mentioned in the resume
2. Evaluate experience relevant to the role
3. Test problem-solving abilities
4. Are specific and actionable

Return only the questions, one per line, numbered 1-{num_questions}."""
        return prompt

    @staticmethod
    def candidate_fit_analysis(resume_text: str, skills: list, job_description: str, job_requirements: str = None) -> str:
        prompt = f"""Analyze how well this candidate matches the job requirements. Provide:
1. Match percentage (0-100)
2. Key strengths that align with the role
3. Potential gaps or weaknesses
4. Overall recommendation (Strong Match / Good Match / Moderate Match / Weak Match)

Candidate Resume:
{resume_text[:2000]}

Candidate Skills: {', '.join(skills[:15])}

Job Description:
{job_description[:1000]}
"""
        if job_requirements:
            prompt += f"\nJob Requirements: {job_requirements[:500]}"

        prompt += """
Provide your analysis in this format:
MATCH_SCORE: [0-100]
STRENGTHS: [comma-separated list]
WEAKNESSES: [comma-separated list]
RECOMMENDATION: [Strong Match / Good Match / Moderate Match / Weak Match]"""
        return prompt

    @staticmethod
    def rag_summary(resume_text: str, job_description: str, context: list = None) -> str:
        prompt = f"""Analyze the following resume and job description, then provide:
1. A concise summary of the candidate (2-3 sentences)
2. Key strengths that match the job requirements
3. Potential weaknesses or gaps
4. Recommendations for the recruiter

Resume:
{resume_text[:2000]}

Job Description:
{job_description[:1000]}
"""
        if context:
            prompt += f"\nAdditional Context:\n" + "\n".join(context[:3])

        prompt += "\n\nFormat your response as:\nSUMMARY: [summary text]\nSTRENGTHS: [comma-separated list]\nWEAKNESSES: [comma-separated list]\nRECOMMENDATIONS: [comma-separated list]"
        return prompt

    @staticmethod
    def feedback(resume_text: str, job_description: str, scores: dict) -> str:
        prompt = f"""Based on the resume, job description, and scoring results, provide constructive feedback:

Resume: {resume_text[:1500]}
Job: {job_description[:800]}
Scores: Match={scores.get('match_score', 0)}, Skills={scores.get('skill_score', 0)}, Experience={scores.get('experience_score', 0)}

Provide 2-3 paragraphs of feedback explaining:
- Why the candidate scored as they did
- What makes them a good or poor fit
- Specific areas for improvement if applicable"""
        return prompt

