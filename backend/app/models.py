from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # "applicant" or "recruiter"
    first_name = Column(String(100))
    last_name = Column(String(100))
    company_name = Column(String(255))  # recruiters only
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # voluntary demographics - fairness dashboard only, never fed into scoring
    demographic_gender = Column(String(50), nullable=True)
    demographic_age_band = Column(String(20), nullable=True)
    demographic_ethnicity = Column(String(100), nullable=True)
    demographic_disability = Column(String(50), nullable=True)
    demographic_consent = Column(Boolean, default=False, nullable=False)

    # relationships
    jobs = relationship("Job", back_populates="recruiter")
    applications = relationship("Application", back_populates="applicant_user")


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(Text)
    location = Column(String(255))
    salary_range = Column(String(100))
    status = Column(String(50), default="active")  # active, closed, draft
    # structured education requirement. when set, the scorer uses this
    # directly instead of text-mining the JD. one of: "none" | "associate"
    # | "bachelor" | "master" | "phd". null = no preference, fall back to
    # description text mining.
    required_education_level = Column(String(20), nullable=True)
    # structured required-skills list. when set, the scorer uses this
    # directly instead of running the JD through the ontology. items should
    # be canonical ontology terms (schema validator normalises them).
    required_skills = Column(JSON, nullable=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # relationships
    recruiter = relationship("User", back_populates="jobs")
    applicants = relationship("Applicant", back_populates="job")
    applications = relationship("Application", back_populates="job")


class Applicant(Base):
    __tablename__ = "applicants"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)  # not unique - same person can apply to multiple jobs
    phone = Column(String(50))

    # résumé data
    resume_text = Column(Text)
    resume_file_path = Column(String(500))
    resume_file_type = Column(String(50))  # pdf, docx, txt

    # extracted info
    skills = Column(JSON)  # list of skills
    experience_years = Column(Float)
    education = Column(JSON)  # list of education entries
    work_experience = Column(JSON)  # list of work experiences

    # scoring
    match_score = Column(Float, default=0.0)
    skill_score = Column(Float, default=0.0)
    experience_score = Column(Float, default=0.0)
    education_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)

    # AI-generated content
    ai_summary = Column(Text)
    ai_feedback = Column(Text)
    interview_questions = Column(JSON)  # list of generated questions

    # status
    status = Column(String(50), default="pending")  # pending, reviewing, shortlisted, rejected, hired
    notes = Column(Text)

    # metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    job = relationship("Job", back_populates="applicants")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=True)  # link to parsed applicant data
    status = Column(String(50), default="pending")  # pending, reviewing, shortlisted, rejected, hired
    notes = Column(Text)
    # adaptive learning - what the recruiter ended up doing
    hire_decision = Column(Boolean, nullable=True)  # True = hired, False = rejected, None = pending
    ai_score_at_decision = Column(Float, nullable=True)  # AI score at the moment the decision was made

    # background AI processing state.
    # `ai_status` transitions: queued -> processing -> ready | failed | skipped
    # "skipped" is used when no résumé file was uploaded.
    ai_status = Column(String(20), default="skipped", nullable=False)
    ai_processed_at = Column(DateTime(timezone=True), nullable=True)
    ai_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    applicant_user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")


class Embedding(Base):
    # cached embedding for a (résumé, model) tuple. the text_hash index lets
    # us skip a re-embed when the same CV gets scored against a different job.
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    text_hash = Column(String(64), nullable=True, index=True)
    model_name = Column(String(100), nullable=True, index=True)
    embedding_vector = Column(JSON)  # stored as a JSON array
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Interview(Base):
    __tablename__ = "interviews"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    location = Column(String(500))
    meeting_link = Column(String(500))
    notes = Column(Text)
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    application = relationship("Application", backref="interviews")


class EmailLog(Base):
    __tablename__ = "email_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=True)  # nullable for user-based applications
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    message_type = Column(String(50), nullable=False)  # acknowledgment, feedback, rejection, interview_invitation
    email_content = Column(Text, nullable=False)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relationships
    applicant = relationship("Applicant", backref="email_logs")
    job = relationship("Job", backref="email_logs")


class ScoringWeights(Base):
    # adaptive weights - drift over time based on recruiter hire/reject vs AI score
    __tablename__ = "scoring_weights"

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null = global weights
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # null = global, set = job-specific

    # weights should sum to ~1.0. defaults match the 40/40/20 split:
    # 40% skills / 40% experience / 20% education. semantic similarity is
    # folded into the hybrid scorer so its standalone default is 0.0.
    # keep in sync with scoring_service.DEFAULT_WEIGHTS and learning_service.DEFAULT_WEIGHTS.
    skill_weight = Column(Float, default=0.4, nullable=False)
    experience_weight = Column(Float, default=0.4, nullable=False)
    education_weight = Column(Float, default=0.2, nullable=False)
    semantic_similarity_weight = Column(Float, default=0.0, nullable=False)

    # metadata
    iteration_count = Column(Integer, default=0)  # number of learning iterations
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relationships
    recruiter = relationship("User", backref="scoring_weights")
    job = relationship("Job", backref="scoring_weights")


class AIAuditLog(Base):
    # one row per AI scoring run - keeps the traceability story honest
    __tablename__ = "ai_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    # scoring data
    overall_score = Column(Float, nullable=False)
    skill_score = Column(Float, nullable=True)
    experience_score = Column(Float, nullable=True)
    education_score = Column(Float, nullable=True)
    match_score = Column(Float, nullable=True)

    # explanation data
    explanation = Column(Text, nullable=True)  # XAI explanation text
    explanation_json = Column(JSON, nullable=True)  # structured explanation payload

    # fairness data
    bias_magnitude = Column(Float, nullable=True)
    fairness_status = Column(String(50), nullable=True)  # fair, warning, bias_detected

    # metadata
    scoring_method = Column(String(100), nullable=True)  # e.g. "hybrid", "semantic_only"
    llm_available = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # explicit foreign_keys=, otherwise SQLAlchemy can't disambiguate
    applicant = relationship("Applicant", foreign_keys=[applicant_id], backref="audit_logs")
    job = relationship("Job", foreign_keys=[job_id], backref="audit_logs")


class RefreshToken(Base):
    # opaque rotating refresh token. every login/refresh mints a new one and
    # revokes the old. revoked rows stay so we can spot reuse (theft signal).
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="refresh_tokens")


class PasswordResetToken(Base):
    # single-use, time-bound reset token. raw goes to the user (SMTP in
    # prod, debug echo in dev); only the SHA-256 hash hits the DB.
    # used_at blocks replay, expires_at caps lifetime, confirm also revokes
    # every refresh token for the user.
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", backref="password_reset_tokens")


class ApplicationNote(Base):
    # threaded, authored, timestamped notes per application - replaces the
    # single `notes` text column. each note carries author + timestamp.
    # only the author can delete their own note. old `notes` column stays
    # for back-compat but the UI reads from here.
    __tablename__ = "application_notes"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("Application", backref="threaded_notes")
    author = relationship("User", backref="application_notes")


class FairnessMetric(Base):
    # one row per audit snapshot - used by the trends chart
    __tablename__ = "fairness_metrics"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)

    # fairness metrics
    mean_score_difference = Column(Float, nullable=False)  # MSD
    disparate_impact_ratio = Column(Float, nullable=False)  # DIR
    bias_magnitude = Column(Float, nullable=False)
    bias_detected = Column(Boolean, default=False)

    # group analysis
    group_analysis = Column(JSON, nullable=True)  # group-level stats

    # demographic breakdown (when available)
    gender_breakdown = Column(JSON, nullable=True)
    experience_tier_breakdown = Column(JSON, nullable=True)
    education_level_breakdown = Column(JSON, nullable=True)

    # metadata
    candidate_count = Column(Integer, nullable=False)
    threshold_used = Column(Float, default=10.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # relationships
    job = relationship("Job", backref="fairness_metrics")
