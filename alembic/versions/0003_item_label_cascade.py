"""Cascade deletes from line_item and label onto item_label.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

FOREIGN_KEYS = (
    ("fk_item_label_item_id_line_item", "line_item", "item_id"),
    ("fk_item_label_label_id_label", "label", "label_id"),
)


def recreate_foreign_keys(ondelete: str | None) -> None:
    """Recreate both item_label foreign keys with the given ON DELETE action."""
    # Batch mode: SQLite cannot alter a constraint in place, so the table is rebuilt.
    with op.batch_alter_table("item_label") as batch:
        for name, referred, column in FOREIGN_KEYS:
            batch.drop_constraint(name, type_="foreignkey")
            batch.create_foreign_key(name, referred, [column], ["id"], ondelete=ondelete)


def upgrade() -> None:
    """Delete a link row together with its item or its label."""
    recreate_foreign_keys("CASCADE")


def downgrade() -> None:
    """Restore the plain foreign keys, which refuse to delete a linked item or label."""
    recreate_foreign_keys(None)
