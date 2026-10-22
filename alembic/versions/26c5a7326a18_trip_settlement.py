"""Store a trip's settlement: its target currency, when it was settled, and one rate per currency.

Revision ID: 26c5a7326a18
Revises: 7c2e9a41b5d8
Create Date: 2026-10-22

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "26c5a7326a18"
down_revision = "7c2e9a41b5d8"
branch_labels = None
depends_on = None

FOREIGN_KEY = "fk_trip_settlement_currency"
CHECK = "ck_trip_settlement_complete"


def upgrade() -> None:
    """Add the settlement columns, then the target's key and the both-or-neither check."""
    op.add_column("trip", sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trip", sa.Column("settlement_currency_id", sa.Integer(), nullable=True))
    op.add_column(
        "trip_currency", sa.Column("settlement_rate_scaled", sa.BigInteger(), nullable=True)
    )
    # Batch mode: SQLite cannot add a foreign key or a check in place, so the table is rebuilt.
    with op.batch_alter_table("trip") as batch:
        batch.create_foreign_key(
            FOREIGN_KEY,
            "trip_currency",
            ["settlement_currency_id", "id"],
            ["id", "trip_id"],
        )
        batch.create_check_constraint(
            CHECK, "(settled_at IS NULL) = (settlement_currency_id IS NULL)"
        )


def downgrade() -> None:
    """Drop the key and the check, then the settlement columns."""
    with op.batch_alter_table("trip") as batch:
        batch.drop_constraint(CHECK, type_="check")
        batch.drop_constraint(FOREIGN_KEY, type_="foreignkey")
        batch.drop_column("settlement_currency_id")
        batch.drop_column("settled_at")
    op.drop_column("trip_currency", "settlement_rate_scaled")
