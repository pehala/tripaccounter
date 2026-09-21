"""Add city to line_item.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the nullable city column to line_item."""
    op.add_column("line_item", sa.Column("city", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop the city column from line_item."""
    op.drop_column("line_item", "city")
