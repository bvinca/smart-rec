# jobs.required_education_level column
# revision: 20260601_0004, revises: 20260429_0003
# explicit none/associate/bachelor/master/phd instead of text-mining the jd
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260601_0004"
down_revision: Union[str, None] = "20260429_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("required_education_level", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "required_education_level")
