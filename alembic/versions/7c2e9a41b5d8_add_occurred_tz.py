"""Add occurred_tz to line_item and wallet_transfer, copied from each row's trip.

Revision ID: 7c2e9a41b5d8
Revises: d431f6f93289
Create Date: 2026-10-10 19:12:08.402113

"""

import sqlalchemy as sa

from alembic import op
from app.db_views import create_share_owed_view, drop_share_owed_view

# revision identifiers, used by Alembic.
revision = "7c2e9a41b5d8"
down_revision = "d431f6f93289"
branch_labels = None
depends_on = None

TABLES = ("line_item", "wallet_transfer")

# Stubs pin the schema at this revision, independent of `app.models`.
trip = sa.table("trip", sa.column("id", sa.Integer), sa.column("timezone", sa.String))


def upgrade() -> None:
    """Record on every row the zone its trip had: each row renders exactly as before."""
    for name in TABLES:
        op.add_column(name, sa.Column("occurred_tz", sa.String(length=64), nullable=True))
        rows = sa.table(name, sa.column("trip_id", sa.Integer), sa.column("occurred_tz", sa.String))
        op.execute(
            sa.update(rows).values(
                occurred_tz=sa.select(trip.c.timezone)
                .where(trip.c.id == rows.c.trip_id)
                .scalar_subquery()
            )
        )

    # Edited: SQLite cannot rebuild line_item while share_owed selects from it.
    op.execute(drop_share_owed_view)
    for name in TABLES:
        with op.batch_alter_table(name, schema=None) as batch_op:
            batch_op.alter_column("occurred_tz", existing_type=sa.String(length=64), nullable=False)
    op.execute(create_share_owed_view)


def downgrade() -> None:
    """Drop the per-row zones; the instants stay."""
    op.execute(drop_share_owed_view)
    for name in TABLES:
        with op.batch_alter_table(name, schema=None) as batch_op:
            batch_op.drop_column("occurred_tz")
    op.execute(create_share_owed_view)
