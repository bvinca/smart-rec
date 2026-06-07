from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# Auth Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    user: "UserResponse"


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: str  # "applicant" or "recruiter"
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None  # Required for recruiters
    
    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        # bcrypt caps inputs at 72 bytes - reject anything bigger
        if not v:
            raise ValueError('Password cannot be empty')
        # bytes, not chars
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            raise ValueError('Password cannot be longer than 72 bytes. Please use a shorter password.')
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        # bcrypt's 72-byte cap again - but no min length on login
        if not v:
            raise ValueError('Password cannot be empty')
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            raise ValueError('Password cannot be longer than 72 bytes.')
        return v


def _validate_new_password(v: str) -> str:
    # shared validator for "set a new password" fields
    if not v:
        raise ValueError('Password cannot be empty')
    password_bytes = v.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError('Password cannot be longer than 72 bytes. Please use a shorter password.')
    if len(v) < 8:
        raise ValueError('Password must be at least 8 characters long')
    return v


class PasswordChangeRequest(BaseModel):
    # POST /auth/change-password - authenticated user supplies both
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def _check_new_password(cls, v: str) -> str:
        return _validate_new_password(v)


class PasswordResetRequest(BaseModel):
    # POST /auth/request-password-reset - always returns 200 to dodge enumeration
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    # POST /auth/confirm-password-reset
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def _check_new_password(cls, v: str) -> str:
        return _validate_new_password(v)


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Job Schemas
_ALLOWED_EDU_LEVELS = {"none", "associate", "bachelor", "master", "phd"}


def _validate_edu_level(value: Optional[str]) -> Optional[str]:
    # normalise + validate the required_education_level enum
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if cleaned == "":
        return None
    if cleaned not in _ALLOWED_EDU_LEVELS:
        raise ValueError(
            f"required_education_level must be one of {sorted(_ALLOWED_EDU_LEVELS)} or null"
        )
    return cleaned


def _normalise_required_skills(value) -> Optional[List[str]]:
    # accept either a list[str] or a CSV/newline-separated string from the
    # form input. drop empties, dedupe case-insensitive. ontology
    # normalisation happens in the scoring service - we just sanitise here.
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip():
            return None
        # split on commas or newlines
        parts = [p.strip() for p in value.replace("\n", ",").split(",")]
        items = [p for p in parts if p]
    elif isinstance(value, list):
        items = [str(p).strip() for p in value if str(p).strip()]
    else:
        raise ValueError("required_skills must be a list or comma-separated string")
    # dedupe case-insensitively, preserve first occurrence
    seen = set()
    out: List[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out or None


class JobBase(BaseModel):
    title: str
    description: str
    requirements: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    status: str = "active"
    required_education_level: Optional[str] = None  # none|associate|bachelor|master|phd
    required_skills: Optional[List[str]] = None

    @field_validator("required_education_level", mode="before")
    @classmethod
    def _check_edu_level(cls, v):
        return _validate_edu_level(v)

    @field_validator("required_skills", mode="before")
    @classmethod
    def _check_required_skills(cls, v):
        return _normalise_required_skills(v)


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    status: Optional[str] = None
    required_education_level: Optional[str] = None
    required_skills: Optional[List[str]] = None

    @field_validator("required_education_level", mode="before")
    @classmethod
    def _check_edu_level(cls, v):
        return _validate_edu_level(v)

    @field_validator("required_skills", mode="before")
    @classmethod
    def _check_required_skills(cls, v):
        return _normalise_required_skills(v)


class Job(JobBase):
    id: int
    recruiter_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Applicant Schemas
class ApplicantBase(BaseModel):
    job_id: int
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None


class ApplicantCreate(ApplicantBase):
    pass


class ApplicantUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class Applicant(ApplicantBase):
    id: int
    resume_text: Optional[str] = None
    resume_file_path: Optional[str] = None
    resume_file_type: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = None
    education: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None
    match_score: float = 0.0
    skill_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    overall_score: float = 0.0
    ai_summary: Optional[str] = None
    ai_feedback: Optional[str] = None
    interview_questions: Optional[List[str]] = None
    status: str = "pending"
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Scoring Schemas
class ScoreRequest(BaseModel):
    applicant_id: int
    job_id: int


class ScoreResponse(BaseModel):
    applicant_id: int
    job_id: int
    match_score: float
    skill_score: float
    experience_score: float
    education_score: float
    overall_score: float
    explanation: Dict[str, Any]


# Summary Schemas
class SummaryRequest(BaseModel):
    applicant_id: int
    job_id: int


class SummaryResponse(BaseModel):
    applicant_id: int
    summary: str
    feedback: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


# Upload Schemas
class UploadResponse(BaseModel):
    applicant_id: int
    message: str
    extracted_data: Dict[str, Any]


# Application Schemas
class ApplicationBase(BaseModel):
    job_id: int


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class RegenerateQuestionsRequest(BaseModel):
    feedback: str
    num_questions: Optional[int] = 5


# AI Enhancement Schemas
class JobDescriptionEnhancementRequest(BaseModel):
    description: str
    title: Optional[str] = None


class JobDescriptionEnhancementResponse(BaseModel):
    improved_description: str
    identified_issues: List[str]
    explanation: str
    bias_detected: bool
    improvements: List[str]
    llm_available: bool


class ResumeFeedbackRequest(BaseModel):
    resume_text: str
    job_description: Optional[str] = None
    job_requirements: Optional[str] = None


class ResumeFeedbackResponse(BaseModel):
    missing_skills: List[str]
    suggested_phrasing: List[Dict[str, str]]
    summary_feedback: str
    strengths: List[str]
    weaknesses: List[str]
    keyword_suggestions: List[str]
    llm_available: bool


class FairnessAuditRequest(BaseModel):
    job_id: Optional[int] = None
    # Allowed group_key values:
    #   "education_tier" - STEM vs non-STEM (heuristic, default)
    #   "experience_tier" - junior / mid / senior bands derived from years
    #   "gender" / "age_band" / "ethnicity" / "disability" - require consenting users
    group_key: Optional[str] = "experience_tier"
    score_key: Optional[str] = "overall_score"
    threshold: Optional[float] = 10.0
    pass_threshold: Optional[float] = 70.0


class FairnessAuditResponse(BaseModel):
    bias_detected: bool
    bias_magnitude: float
    group_analysis: Dict[str, Dict[str, Any]]
    recommendations: List[str]
    statistical_significance: float
    message: str
    mean_score_difference: Optional[float] = None
    disparate_impact_ratio: Optional[float] = None
    statistical_parity_difference: Optional[float] = None
    fairness_status: Optional[str] = None
    metrics_summary: Optional[Dict[str, Any]] = None
    candidates_analysed: Optional[int] = None
    group_key: Optional[str] = None


class DemographicUpdate(BaseModel):
    # voluntary demographics - for the fairness dashboard only
    consent: bool
    gender: Optional[str] = None
    age_band: Optional[str] = None  # e.g. "<25", "25-34", "35-44", "45-54", "55+"
    ethnicity: Optional[str] = None
    disability: Optional[str] = None  # "yes", "no", "prefer_not_to_say"


class DemographicResponse(BaseModel):
    consent: bool
    gender: Optional[str] = None
    age_band: Optional[str] = None
    ethnicity: Optional[str] = None
    disability: Optional[str] = None


class XAIExplanationRequest(BaseModel):
    applicant_id: int
    job_id: Optional[int] = None


class XAIExplanationResponse(BaseModel):
    skills_explanation: str
    experience_explanation: str
    education_explanation: str
    soft_skills_explanation: str
    strengths: List[str]
    weaknesses: List[str]
    overall_summary: str
    score_breakdown: Dict[str, Dict[str, Any]]
    feature_attributions: Optional[Dict[str, Dict[str, Any]]] = None
    counterfactuals: Optional[List[Dict[str, Any]]] = None
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    llm_available: bool


class SkillGapAnalysisRequest(BaseModel):
    job_id: int
    applicant_id: int


class SkillGapAnalysisResponse(BaseModel):
    skill_matches: Dict[str, float]
    missing_skills: List[str]
    strong_matches: List[str]
    weak_matches: List[str]
    overall_alignment: float
    total_job_skills: int
    matched_skills: int
    message: str


class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    applicant_id: Optional[int] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    job: Optional["Job"] = None
    applicant: Optional[Dict[str, Any]] = None  # Include applicant data with scores and AI content (if resume uploaded)
    user: Optional[Dict[str, Any]] = None  # Include user data if no resume uploaded
    match_score: Optional[float] = None  # For applicants to see their match score

    # Background AI processing state. ``ai_status`` transitions:
    #   "queued" -> "processing" -> "ready" | "failed" | "skipped"
    ai_status: Optional[str] = None
    ai_processed_at: Optional[datetime] = None
    ai_error: Optional[str] = None

    class Config:
        from_attributes = True


# Profile Schemas
class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None


class ProfileResponse(BaseModel):
    id: int
    email: str
    role: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Interview Schemas
class InterviewBase(BaseModel):
    application_id: int
    scheduled_at: datetime
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


class InterviewCreate(InterviewBase):
    pass


class InterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None  # scheduled, completed, cancelled


class InterviewResponse(InterviewBase):
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Analytics Schemas
class AnalyticsResponse(BaseModel):
    total_jobs: int
    active_jobs: int
    total_applications: int
    pending_applications: int
    shortlisted_applications: int
    rejected_applications: int
    hired_applications: int
    average_score: float
    top_skills: List[Dict[str, Any]]
    applications_by_job: List[Dict[str, Any]]


# Resume Analysis Schemas (for POST /resume/analyze)
class ResumeAnalysisRequest(BaseModel):
    resume_text: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = None
    education: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None
    job_description: Optional[str] = None  # Optional for context-aware questions


class ResumeAnalysisResponse(BaseModel):
    summary: str
    interview_questions: List[str]


# Ranking Schemas
class RankedCandidateResponse(BaseModel):
    rank: int
    applicant_id: int
    name: str
    email: str
    match_score: float
    overall_score: float
    skills: List[str]
    experience_years: float
    ai_summary: Optional[str] = None
    status: str


# Application Response with Parsed Data
class ParsedResumeData(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str]
    education: List[Dict[str, Any]]
    experience_years: float
    work_experience: List[Dict[str, Any]]


# Email Schemas
class EmailGenerateRequest(BaseModel):
    message_type: str  # acknowledgment, feedback, rejection, interview_invitation
    tone: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None


class EmailGenerateResponse(BaseModel):
    email_id: int
    content: str
    recipient_email: str
    candidate_name: str
    job_title: str
    message_type: str
    generated_at: str


class EmailHistoryResponse(BaseModel):
    id: int
    recipient_email: str
    message_type: str
    email_content: str
    sent: bool
    sent_at: Optional[str] = None
    created_at: str


class EmailSendRequest(BaseModel):
    subject: Optional[str] = None


class EmailSendResponse(BaseModel):
    success: bool
    email_id: int
    recipient_email: str
    sent_at: str
    message: str


# Adaptive Learning / Feedback Schemas
class FeedbackEntry(BaseModel):
    # one (application, decision, scores) tuple for the learner
    application_id: int
    hired: bool
    ai_score: Optional[float] = None
    skill_score: Optional[float] = None
    experience_score: Optional[float] = None
    education_score: Optional[float] = None
    semantic_score: Optional[float] = None


class FeedbackRequest(BaseModel):
    # POST /feedback - batch of recruiter decisions for the weight learner
    feedback_data: List[FeedbackEntry]
    learning_rate: Optional[float] = 0.1  # 0.0 to 1.0
    recruiter_id: Optional[int] = None
    job_id: Optional[int] = None


class FeedbackResponse(BaseModel):
    # what the learner did with the batch
    success: bool
    message: str
    updated_weights: Dict[str, float]
    iteration_count: int


class WeightsResponse(BaseModel):
    # current scoring weights for the (recruiter, job) scope
    skill_weight: float
    experience_weight: float
    education_weight: float
    semantic_similarity_weight: float
    iteration_count: int
    last_updated: Optional[str] = None


class ApplicationDecisionRequest(BaseModel):
    # POST /applications/{id}/decision - recruiter hire/reject signal
    application_id: int
    hired: bool  # True = hired, False = rejected
    notes: Optional[str] = None


# threaded application notes -----------------------------------------------

class ApplicationNoteCreate(BaseModel):
    # POST /applications/{id}/notes
    body: str

    @field_validator("body")
    @classmethod
    def _body_not_empty(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned:
            raise ValueError("Note body cannot be empty")
        if len(cleaned) > 4000:
            raise ValueError("Note body cannot exceed 4000 characters")
        return cleaned


class ApplicationNoteAuthor(BaseModel):
    # minimal author payload embedded on every note
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ApplicationNoteResponse(BaseModel):
    # single note as returned by the API
    id: int
    application_id: int
    body: str
    created_at: datetime
    author: ApplicationNoteAuthor

    class Config:
        from_attributes = True


class InterviewPrepResponse(BaseModel):
    # LLM-generated interview-prep package for one application
    application_id: int
    company_overview: str
    position_questions: List[str]
    preparation_tips: List[str]
    cached: bool  # True when served from ai_audit_logs cache, False when freshly generated
    generated_at: datetime
