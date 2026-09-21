"""SQLModel table definitions for the trip, roster, and line-item schema."""

from sqlmodel import SQLModel

# Constraints SQLAlchemy would otherwise leave unnamed - primary keys and
# single-column foreign keys - get a deterministic name from this convention,
# so the name is the same on SQLite and Postgres instead of whatever each
# engine autogenerates, and can be referenced (e.g. from a migration) without
# guessing it. Explicit `name=` on a constraint (every UniqueConstraint and
# composite ForeignKeyConstraint in this package) always wins over the
# convention. No "ck" key: unlike the others, CheckConstraint feeds its own
# given name into %(constraint_name)s even when already named, so adding one
# would silently rename every existing CheckConstraint (e.g. `ck_transfer_not_same`
# -> `ck_wallet_transfer_ck_transfer_not_same`) - and every CheckConstraint here
# already carries a full, explicit name.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
