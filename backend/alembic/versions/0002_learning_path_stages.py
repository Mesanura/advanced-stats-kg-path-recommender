"""add learning path stages

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_path_items",
        sa.Column("stage", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute("UPDATE learning_paths SET state = 'STALE' WHERE state = 'CURRENT'")


def downgrade() -> None:
    op.drop_column("learning_path_items", "stage")
