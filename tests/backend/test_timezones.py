"""The trip time zone: wall times in and out, the days it cuts, and the order it keeps."""

import pytest

from tests.backend.test_stats import get_stats

PRAGUE = "Europe/Prague"
TOKYO = "Asia/Tokyo"


def set_zone(client, trip, zone):
    """PATCH the trip's time zone and assert it was accepted."""
    response = client.patch(f"/api/v1/trips/{trip['slug']}", json={"timezone": zone})
    assert response.status_code == 200, response.text


def post_item(client, trip, item_body, wall_time, **overrides):
    """POST an item at `wall_time` and return its wire form."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at=wall_time, **overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()["item"]


def feed(client, trip):
    """GET the trip's items envelope."""
    return client.get(f"/api/v1/trips/{trip['slug']}/items").json()


def test_trip_without_a_timezone_is_created_in_utc(trip):
    """An API create that omits `timezone` gets UTC, which reproduces the pre-zone feed."""
    assert trip["timezone"] == "UTC"


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "", "../etc/passwd", "Europe"])
def test_unknown_timezone_is_invalid_timezone_on_create_and_update(client, trip, timezone):
    """A name `zoneinfo` cannot load is `invalid_timezone` on create and on update."""
    expected = {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"timezone": {"code": "invalid_timezone", "params": {}}},
        }
    }
    body = {
        "name": "Bad zone",
        "timezone": timezone,
        "people": [{"name": "Ann"}],
        "currencies": [{"code": "ISK"}],
        "countries": [{"name": "Iceland"}],
    }

    created = client.post("/api/v1/trips", json=body)
    updated = client.patch(f"/api/v1/trips/{trip['slug']}", json={"timezone": timezone})

    assert (created.status_code, created.json()) == (422, expected)
    assert (updated.status_code, updated.json()) == (422, expected)


def test_wall_time_reads_back_in_the_trip_zone_and_keeps_its_zone_when_the_trip_moves(
    client, trip, item_body
):
    """17:00 typed into a Tokyo trip reads back as 17:00; moving the trip re-cuts only its days."""
    set_zone(client, trip, TOKYO)

    item = post_item(client, trip, item_body, "2026-09-14T17:00:00")

    assert item["occurred_at"] == "2026-09-14T17:00:00"
    assert item["occurred_tz"] == TOKYO
    assert item["trip_occurred_at"] == "2026-09-14T17:00:00"
    assert item["day"] == "2026-09-14"

    set_zone(client, trip, PRAGUE)
    moved = feed(client, trip)["items"][0]

    assert moved["occurred_at"] == "2026-09-14T17:00:00"
    assert moved["occurred_tz"] == TOKYO
    assert moved["trip_occurred_at"] == "2026-09-14T10:00:00"


@pytest.mark.parametrize("wall_time", ["2026-09-14T17:00:00Z", "2026-09-14T17:00:00+02:00"])
def test_wall_time_with_an_offset_is_invalid_datetime(client, trip, item_body, wall_time):
    """An `occurred_at` carrying an offset is refused rather than converted."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at=wall_time)
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {
        "occurred_at": {"code": "invalid_datetime", "params": {}}
    }


def test_spring_forward_gap_is_invalid_datetime_for_items_and_transfers(
    client, trip, item_body, transfer_body
):
    """02:30 on 29 Mar 2026 does not exist in Prague, on both write paths."""
    set_zone(client, trip, PRAGUE)
    expected = {"occurred_at": {"code": "invalid_datetime", "params": {}}}

    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at="2026-03-29T02:30:00")
    )
    transfer = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(occurred_at="2026-03-29T02:30:00"),
    )

    assert item.status_code == transfer.status_code == 422
    assert item.json()["error"]["fields"] == expected
    assert transfer.json()["error"]["fields"] == expected


def test_autumn_repeat_resolves_to_the_earlier_instant(client, trip, item_body):
    """02:30 on 25 Oct 2026 happens twice in Prague; the first one, 00:30 UTC, wins."""
    set_zone(client, trip, PRAGUE)
    post_item(client, trip, item_body, "2026-10-25T02:30:00")

    set_zone(client, trip, "UTC")

    assert feed(client, trip)["items"][0]["trip_occurred_at"] == "2026-10-25T00:30:00"


def test_patch_without_occurred_at_keeps_the_instant(client, trip, item_body):
    """Editing another field leaves the stored moment, so the wall time does not drift."""
    set_zone(client, trip, TOKYO)
    item = post_item(client, trip, item_body, "2026-09-14T17:00:00")

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{item['id']}", json={"name": "Renamed"}
    )

    assert response.json()["item"]["occurred_at"] == "2026-09-14T17:00:00"


def test_days_and_totals_are_cut_in_the_trip_zone(client, trip, item_body):
    """20:00 UTC on 11 Sep is 12 Sep in Tokyo: inside the trip, under its first day."""
    post_item(client, trip, item_body, "2026-09-11T20:00:00", amount="100.00")
    assert feed(client, trip)["before_trip_totals"] == [
        {"currency_code": "ISK", "currency_id": trip["currencies"][0]["id"], "amount": 100}
    ]

    set_zone(client, trip, TOKYO)
    body = feed(client, trip)

    assert body["items"][0]["day"] == "2026-09-12"
    assert body["before_trip_totals"] == []
    assert [day["date"] for day in body["day_totals"]] == ["2026-09-12"]
    groups = get_stats(client, trip["slug"], "day")
    assert [row["keys"]["date"] for row in groups[("currency", "day")]] == ["2026-09-12"]


def test_day_agrees_with_day_totals_across_a_clock_change(client, trip, item_body):
    """Prague's 25 Oct fall-back moves no row off its day: item `day`, totals and stats agree."""
    set_zone(client, trip, PRAGUE)
    wall_times = [
        "2026-10-24T23:30:00",
        "2026-10-25T00:30:00",
        "2026-10-25T03:30:00",
        "2026-10-25T23:30:00",
        "2026-10-26T00:30:00",
    ]
    for wall_time in wall_times:
        post_item(client, trip, item_body, wall_time, amount="10.00")

    body = feed(client, trip)
    days = [item["day"] for item in body["items"]]

    assert days == ["2026-10-26", "2026-10-25", "2026-10-25", "2026-10-25", "2026-10-24"]
    assert [day["date"] for day in body["day_totals"]] == ["2026-10-26", "2026-10-25", "2026-10-24"]
    assert [day["totals"][0]["amount"] for day in body["day_totals"]] == [10, 30, 10]
    groups = get_stats(client, trip["slug"], "day")
    assert [(row["keys"]["date"], row["amount"]) for row in groups[("currency", "day")]] == [
        ("2026-10-24", 10),
        ("2026-10-25", 30),
        ("2026-10-26", 10),
    ]


def test_feed_orders_by_instant_across_a_clock_change(client, trip, item_body):
    """Items posted out of order list newest first, and `trip_occurred_at` orders the same way."""
    set_zone(client, trip, PRAGUE)
    for wall_time in ("2026-10-25T03:30:00", "2026-10-25T02:30:00", "2026-10-25T01:30:00"):
        post_item(client, trip, item_body, wall_time)

    listed = [item["trip_occurred_at"] for item in feed(client, trip)["items"]]

    assert listed == ["2026-10-25T03:30:00", "2026-10-25T02:30:00", "2026-10-25T01:30:00"]


def test_items_and_transfers_answer_the_same_four_time_fields(
    client, trip, item_body, transfer_body
):
    """Both rows carry occurred_at, occurred_tz, trip_occurred_at and day from one rule."""
    set_zone(client, trip, TOKYO)
    item = post_item(client, trip, item_body, "2026-09-14T17:00:00")
    transfer = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(occurred_at="2026-09-14T17:00:00"),
    ).json()["transfer"]

    keys = ("occurred_at", "occurred_tz", "trip_occurred_at", "day")

    assert {key: item[key] for key in keys} == {key: transfer[key] for key in keys}
    assert {key: item[key] for key in keys} == {
        "occurred_at": "2026-09-14T17:00:00",
        "occurred_tz": TOKYO,
        "trip_occurred_at": "2026-09-14T17:00:00",
        "day": "2026-09-14",
    }


def test_trip_and_summary_carry_the_timezone(client, trip):
    """`timezone` is on the trip and on its list summary."""
    set_zone(client, trip, TOKYO)

    listed = client.get("/api/v1/trips").json()["trips"]

    assert [row["timezone"] for row in listed if row["slug"] == trip["slug"]] == [TOKYO]


# ---- Per-item zones --------------------------------------------------------------


def patch_item(client, trip, item, **body):
    """PATCH an item and return its wire form."""
    response = client.patch(f"/api/v1/trips/{trip['slug']}/items/{item['id']}", json=body)
    assert response.status_code == 200, response.text
    return response.json()["item"]


def test_item_in_another_zone_reads_in_its_own_zone_and_days_in_the_trips(client, trip, item_body):
    """17:00 Tokyo in a Prague trip reads 17:00 Tokyo; its trip time and day are Prague's."""
    set_zone(client, trip, PRAGUE)

    item = post_item(client, trip, item_body, "2026-09-14T01:00:00", occurred_tz=TOKYO)

    assert item["occurred_at"] == "2026-09-14T01:00:00"
    assert item["occurred_tz"] == TOKYO
    assert item["trip_occurred_at"] == "2026-09-13T18:00:00"
    assert item["day"] == "2026-09-13"


def test_create_without_occurred_tz_takes_the_trips_zone(client, trip, item_body):
    """A write that omits the zone records the trip's."""
    set_zone(client, trip, TOKYO)

    assert post_item(client, trip, item_body, "2026-09-14T17:00:00")["occurred_tz"] == TOKYO


def test_patch_with_occurred_at_alone_resolves_in_the_rows_zone(client, trip, item_body):
    """A wall time sent alone is read in the row's zone, not the trip's."""
    set_zone(client, trip, PRAGUE)
    item = post_item(client, trip, item_body, "2026-09-14T17:00:00", occurred_tz=TOKYO)

    moved = patch_item(client, trip, item, occurred_at="2026-09-14T18:00:00")

    assert moved["occurred_at"] == "2026-09-14T18:00:00"
    assert moved["occurred_tz"] == TOKYO
    assert moved["trip_occurred_at"] == "2026-09-14T11:00:00"


def test_patch_with_occurred_tz_alone_keeps_the_instant(client, trip, item_body):
    """Changing only the zone shows the same moment as local time elsewhere."""
    set_zone(client, trip, PRAGUE)
    item = post_item(client, trip, item_body, "2026-09-14T17:00:00")

    moved = patch_item(client, trip, item, occurred_tz=TOKYO)

    assert moved["occurred_at"] == "2026-09-15T00:00:00"
    assert moved["occurred_tz"] == TOKYO
    assert moved["trip_occurred_at"] == "2026-09-14T17:00:00"


def test_patch_with_both_moves_the_instant_to_the_typed_time_in_the_new_zone(
    client, trip, item_body
):
    """Time and zone together mean the typed time was right and the zone was wrong."""
    set_zone(client, trip, PRAGUE)
    item = post_item(client, trip, item_body, "2026-09-14T17:00:00")

    moved = patch_item(client, trip, item, occurred_at="2026-09-14T17:00:00", occurred_tz=TOKYO)

    assert moved["occurred_at"] == "2026-09-14T17:00:00"
    assert moved["trip_occurred_at"] == "2026-09-14T10:00:00"


def test_patch_across_a_clock_change_resolves_at_the_new_offset(client, trip, item_body):
    """Moving a Prague row from September to November keeps its zone and takes the winter offset."""
    set_zone(client, trip, PRAGUE)
    item = post_item(client, trip, item_body, "2026-09-14T12:00:00")

    moved = patch_item(client, trip, item, occurred_at="2026-11-14T12:00:00")

    assert moved["occurred_tz"] == PRAGUE
    assert moved["trip_occurred_at"] == "2026-11-14T12:00:00"
    assert feed(client, trip)["items"][0]["occurred_at"] == "2026-11-14T12:00:00"


def test_unknown_occurred_tz_is_invalid_timezone_for_items_and_transfers(
    client, trip, item_body, transfer_body
):
    """A zone `zoneinfo` cannot load is a field error on both write paths."""
    expected = {"occurred_tz": {"code": "invalid_timezone", "params": {}}}

    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(occurred_at="2026-09-14T17:00:00", occurred_tz="Mars/Olympus"),
    )
    transfer = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(occurred_tz="Mars/Olympus"),
    )

    assert item.status_code == transfer.status_code == 422
    assert item.json()["error"]["fields"] == expected
    assert transfer.json()["error"]["fields"] == expected


def test_gap_is_checked_in_the_items_own_zone(client, trip, item_body):
    """02:30 on 29 Mar 2026 exists in Tokyo, so a Prague trip accepts it there."""
    set_zone(client, trip, PRAGUE)

    item = post_item(client, trip, item_body, "2026-03-29T02:30:00", occurred_tz=TOKYO)

    assert item["occurred_at"] == "2026-03-29T02:30:00"


def test_transfer_follows_the_same_zone_rules(client, trip, transfer_body):
    """A transfer's zone defaults to the trip's, and a zone sent alone keeps its instant."""
    set_zone(client, trip, PRAGUE)
    url = f"/api/v1/trips/{trip['slug']}/transfers"
    created = client.post(url, json=transfer_body(occurred_at="2026-09-14T17:00:00")).json()[
        "transfer"
    ]

    moved = client.patch(f"{url}/{created['id']}", json={"occurred_tz": TOKYO}).json()["transfer"]

    assert created["occurred_tz"] == PRAGUE
    assert moved["occurred_at"] == "2026-09-15T00:00:00"
    assert moved["occurred_tz"] == TOKYO
    assert moved["trip_occurred_at"] == "2026-09-14T17:00:00"


def test_feed_orders_by_instant_across_two_zones(client, trip, item_body):
    """A later local time in Tokyo can be the earlier instant; the feed follows the instant."""
    set_zone(client, trip, PRAGUE)
    tokyo = post_item(client, trip, item_body, "2026-09-14T20:00:00", occurred_tz=TOKYO)
    prague = post_item(client, trip, item_body, "2026-09-14T14:00:00")

    assert [row["id"] for row in feed(client, trip)["items"]] == [prague["id"], tokyo["id"]]
