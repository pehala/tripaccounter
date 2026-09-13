"""Define the `share_owed` view as a SQLAlchemy `select()` compiled by whatever dialect is in use.

No hand-written SQL string, so it stays portable between SQLite (dev/test)
and Postgres (the schema's compatibility target).

`CreateView`/`DropView` are the standard SQLAlchemy recipe for view DDL: a
`DDLElement` subclass plus a `@compiles` hook that renders it by compiling the
wrapped `Select` with `literal_binds=True` (a view body can't carry bind
params).
"""

from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, Table, cast, func, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.ddl import DDLElement

from app.models import ItemShare, LineItem


class CreateView(DDLElement):
    """DDL element that creates a view from a compiled `Select`."""

    def __init__(self, name: str, selectable) -> None:
        """Store the view name and the selectable it is created from."""
        self.name = name
        self.selectable = selectable


class DropView(DDLElement):
    """DDL element that drops a view by name."""

    def __init__(self, name: str) -> None:
        """Store the view name to drop."""
        self.name = name


@compiles(CreateView)
def _compile_create_view(element: CreateView, compiler, **_kwargs) -> str:
    compiled_select = compiler.sql_compiler.process(element.selectable, literal_binds=True)
    return f"CREATE VIEW {element.name} AS {compiled_select}"


@compiles(DropView)
def _compile_drop_view(element: DropView, compiler, **_kwargs) -> str:
    return f"DROP VIEW IF EXISTS {element.name}"


# A plain Core Table (its own MetaData - never DDL'd via metadata.create_all)
# so services can SELECT from the view without an ORM mapping.
_view_metadata = MetaData()

share_owed_view = Table(
    "share_owed",
    _view_metadata,
    Column("item_id", Integer),
    Column("person_id", Integer),
    Column("trip_id", Integer),
    Column("currency_id", Integer),
    Column("occurred_at", DateTime),
    Column("owed_micro", BigInteger),
)


def _share_owed_select():
    """Compute `owed_micro = COALESCE(exact_owed, amount * weight / total_weight)`.

    At micro-unit scale, floored - the one definition of a computed share
    (ERD.md "Money"). Integer division on integer columns floors identically
    on SQLite and Postgres for the positive operands used here.
    """
    shares = ItemShare.__table__.alias("s")
    items = LineItem.__table__.alias("i")
    weight_totals = (
        select(
            ItemShare.__table__.c.item_id,
            func.sum(ItemShare.__table__.c.weight_scaled).label("total_scaled"),
        )
        .group_by(ItemShare.__table__.c.item_id)
        .subquery("w")
    )

    owed_micro = cast(
        func.coalesce(
            shares.c.owed_minor * 10000,
            items.c.amount_minor * 10000 * shares.c.weight_scaled / weight_totals.c.total_scaled,
        ),
        BigInteger,
    ).label("owed_micro")

    return select(
        shares.c.item_id,
        shares.c.person_id,
        items.c.trip_id,
        items.c.currency_id,
        items.c.occurred_at,
        owed_micro,
    ).select_from(
        shares.join(items, items.c.id == shares.c.item_id).join(
            weight_totals, weight_totals.c.item_id == shares.c.item_id
        )
    )


create_share_owed_view = CreateView("share_owed", _share_owed_select())
drop_share_owed_view = DropView("share_owed")
