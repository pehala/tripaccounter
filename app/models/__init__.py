"""SQLModel table definitions for the trip, roster, and line-item schema."""

from sqlmodel import SQLModel

# Constraints SQLAlchemy would otherwise leave unnamed - primary keys and
# single-column foreign keys - get a deterministic name from this convention,
# so the name is the same on SQLite and Postgres instead of whatever each
# engine autogenerates, and can be referenced (e.g. from a migration) without
# guessing it. Explicit `name=` on a constraint (every UniqueConstraint,
# CheckConstraint, and composite ForeignKeyConstraint in this package) always
# wins over the convention.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
