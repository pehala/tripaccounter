"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-12

"""

from sqlmodel import SQLModel

import app.models  # noqa: F401  registers all tables on SQLModel.metadata
from alembic import op
from app.db_views import create_share_owed_view, drop_share_owed_view

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create every table and the share-owed view."""
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)
    op.execute(create_share_owed_view)


def downgrade() -> None:
    """Drop the share-owed view and every table."""
    bind = op.get_bind()
    op.execute(drop_share_owed_view)
    SQLModel.metadata.drop_all(bind)
