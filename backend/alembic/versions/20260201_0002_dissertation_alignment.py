# dissertation alignment: demographics, embedding cache, async ai status
# revision: 20260201_0002, revises: 20260101_0001
# adds users.demographic_*, embeddings cache keys, applications.ai_status fields
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260201_0002"
down_revision: Union[str, None] = "20260101_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("demographic_gender", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("demographic_age_band", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("demographic_ethnicity", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("demographic_disability", sa.String(length=50), nullable=True))
        batch.add_column(
            sa.Column(
                "demographic_consent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("embeddings") as batch:
        batch.add_column(sa.Column("text_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("model_name", sa.String(length=100), nullable=True))
    op.create_index(
        "ix_embeddings_text_hash", "embeddings", ["text_hash"], unique=False
    )
    op.create_index(
        "ix_embeddings_model_name", "embeddings", ["model_name"], unique=False
    )

    with op.batch_alter_table("applications") as batch:
        batch.add_column(
            sa.Column(
                "ai_status",
                sa.String(length=20),
                nullable=False,
                server_default="skipped",
            )
        )
        batch.add_column(sa.Column("ai_processed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("ai_error", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("ai_error")
        batch.drop_column("ai_processed_at")
        batch.drop_column("ai_status")

    op.drop_index("ix_embeddings_model_name", table_name="embeddings")
    op.drop_index("ix_embeddings_text_hash", table_name="embeddings")
    with op.batch_alter_table("embeddings") as batch:
        batch.drop_column("model_name")
        batch.drop_column("text_hash")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("demographic_consent")
        batch.drop_column("demographic_disability")
        batch.drop_column("demographic_ethnicity")
        batch.drop_column("demographic_age_band")
        batch.drop_column("demographic_gender")
