# jobs.required_skills json column
# revision: 20260602_0005, revises: 20260601_0004
# explicit skill list for scorer; null keeps old text-mining fallback
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260602_0005"
down_revision: Union[str, None] = "20260601_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("required_skills", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "required_skills")
