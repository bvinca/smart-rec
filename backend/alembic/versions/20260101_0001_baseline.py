# baseline migration: full schema
# revision: 20260101_0001, revises: (none)
# idempotent: existing dbs can alembic stamp 20260101_0001 without re-running
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260101_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("first_name", sa.String(length=100)),
        sa.Column("last_name", sa.String(length=100)),
        sa.Column("company_name", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text()),
        sa.Column("location", sa.String(length=255)),
        sa.Column("salary_range", sa.String(length=100)),
        sa.Column("status", sa.String(length=50), default="active"),
        sa.Column("recruiter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "applicants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, index=True),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("resume_text", sa.Text()),
        sa.Column("resume_file_path", sa.String(length=500)),
        sa.Column("resume_file_type", sa.String(length=50)),
        sa.Column("skills", sa.JSON()),
        sa.Column("experience_years", sa.Float()),
        sa.Column("education", sa.JSON()),
        sa.Column("work_experience", sa.JSON()),
        sa.Column("match_score", sa.Float(), default=0.0),
        sa.Column("skill_score", sa.Float(), default=0.0),
        sa.Column("experience_score", sa.Float(), default=0.0),
        sa.Column("education_score", sa.Float(), default=0.0),
        sa.Column("overall_score", sa.Float(), default=0.0),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_feedback", sa.Text()),
        sa.Column("interview_questions", sa.JSON()),
        sa.Column("status", sa.String(length=50), default="pending"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("applicant_id", sa.Integer(), sa.ForeignKey("applicants.id"), nullable=True),
        sa.Column("status", sa.String(length=50), default="pending"),
        sa.Column("notes", sa.Text()),
        sa.Column("hire_decision", sa.Boolean(), nullable=True),
        sa.Column("ai_score_at_decision", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("applicant_id", sa.Integer(), sa.ForeignKey("applicants.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("embedding_vector", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(length=500)),
        sa.Column("meeting_link", sa.String(length=500)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(length=50), default="scheduled"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("applicant_id", sa.Integer(), sa.ForeignKey("applicants.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("email_content", sa.Text(), nullable=False),
        sa.Column("sent", sa.Boolean(), default=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "scoring_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recruiter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("skill_weight", sa.Float(), nullable=False, default=0.4),
        sa.Column("experience_weight", sa.Float(), nullable=False, default=0.3),
        sa.Column("education_weight", sa.Float(), nullable=False, default=0.1),
        sa.Column("semantic_similarity_weight", sa.Float(), nullable=False, default=0.2),
        sa.Column("iteration_count", sa.Integer(), default=0),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ai_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("applicant_id", sa.Integer(), sa.ForeignKey("applicants.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("skill_score", sa.Float(), nullable=True),
        sa.Column("experience_score", sa.Float(), nullable=True),
        sa.Column("education_score", sa.Float(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("explanation_json", sa.JSON(), nullable=True),
        sa.Column("bias_magnitude", sa.Float(), nullable=True),
        sa.Column("fairness_status", sa.String(length=50), nullable=True),
        sa.Column("scoring_method", sa.String(length=100), nullable=True),
        sa.Column("llm_available", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "fairness_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("mean_score_difference", sa.Float(), nullable=False),
        sa.Column("disparate_impact_ratio", sa.Float(), nullable=False),
        sa.Column("bias_magnitude", sa.Float(), nullable=False),
        sa.Column("bias_detected", sa.Boolean(), default=False),
        sa.Column("group_analysis", sa.JSON(), nullable=True),
        sa.Column("gender_breakdown", sa.JSON(), nullable=True),
        sa.Column("experience_tier_breakdown", sa.JSON(), nullable=True),
        sa.Column("education_level_breakdown", sa.JSON(), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("threshold_used", sa.Float(), default=10.0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in (
        "fairness_metrics",
        "ai_audit_logs",
        "scoring_weights",
        "email_logs",
        "interviews",
        "embeddings",
        "applications",
        "applicants",
        "jobs",
        "users",
    ):
        op.drop_table(table)
