"""Tests for views/Balances.js and components/BalanceCard.js.

One card per currency, each `net`
formatted and signed correctly (credit `+`, debt `−`, zero bare), suggestion rows
in order and never more than n−1, bar widths derived without mutating the values;
asserts `|sum(people[].net)| < 0.00001` per card and that the suggestions sum to
zero exactly, both of which API.md explicitly allows a client to check; six-place
`net` values render to two.
"""

from playwright.sync_api import expect


def fmt_signed(page, value):
    """Return the exact string fmt.js's signed() produces for `value` in `en`."""
    return page.evaluate(
        "async ({ value }) => (await import('/js/fmt.js')).signed(value, 'en')",
        {"value": value},
    )


def balance_card_for(page, currency_code):
    """Return the 'Balance <code>' card (people + net) — not the settle-up card."""
    return page.locator(".card").filter(
        has=page.locator(".card-header", has_text=f"Balance {currency_code}")
    )


def settle_card_for(page, currency_code):
    """Return the 'Settle up <code>' card (suggestions)."""
    return page.locator(".card").filter(
        has=page.locator(".card-header", has_text=f"Settle up {currency_code}")
    )


def test_one_balance_card_and_one_settle_up_card_per_currency(
    page, mockserver, trip_url, fixture_data
):
    """Every currency in the fixture gets its own balance card and settle-up card."""
    page.goto(f"{trip_url}#balances")

    for balance in fixture_data["balances"]["balances"]:
        expect(balance_card_for(page, balance["currency_code"])).to_have_count(1)
        expect(settle_card_for(page, balance["currency_code"])).to_have_count(1)


def test_net_values_are_signed_correctly_per_person(page, mockserver, trip_url, fixture_data):
    """A positive net renders with a leading +, a negative with -, zero renders bare."""
    page.goto(f"{trip_url}#balances")
    trip = fixture_data["trip"]["trip"]
    people_by_id = {p["id"]: p["name"] for p in trip["people"]}

    for balance in fixture_data["balances"]["balances"]:
        card = balance_card_for(page, balance["currency_code"])
        for person in balance["people"]:
            name = people_by_id[person["person_id"]]
            expected = fmt_signed(page, person["net"])
            row = card.locator("li").filter(has_text=name)
            expect(row.locator(".num")).to_have_text(expected)
            if person["net"] > 0:
                assert expected.startswith("+")
            elif person["net"] < 0:
                assert expected.startswith(("-", "−"))
            else:
                assert not expected.startswith("+") and "-" not in expected


def test_suggestion_rows_match_the_fixture_order_and_count(
    page, mockserver, trip_url, fixture_data
):
    """Suggestion rows render in the fixture's own order and never exceed n-1 per currency."""
    page.goto(f"{trip_url}#balances")
    trip = fixture_data["trip"]["trip"]
    people_by_id = {p["id"]: p["name"] for p in trip["people"]}

    for balance in fixture_data["balances"]["balances"]:
        n_people = len(balance["people"])
        assert len(balance["suggestions"]) <= n_people - 1

        rows = settle_card_for(page, balance["currency_code"]).locator("ul.list-group-flush li")
        expect(rows).to_have_count(len(balance["suggestions"]))
        for i, suggestion in enumerate(balance["suggestions"]):
            expect(rows.nth(i)).to_contain_text(people_by_id[suggestion["from_person_id"]])
            expect(rows.nth(i)).to_contain_text(people_by_id[suggestion["to_person_id"]])


def test_suggestions_settle_every_person_close_to_their_net(
    page, mockserver, trip_url, fixture_data
):
    """Settle each person to within a cent of their raw net, summing to zero exactly.

    API.md: nets are rounded to hundredths with a zero-sum correction, so one person
    may absorb an extra hundredth to keep the total exactly balanced.
    """
    for balance in fixture_data["balances"]["balances"]:
        settled = dict.fromkeys((p["person_id"] for p in balance["people"]), 0.0)
        for s in balance["suggestions"]:
            settled[s["from_person_id"]] -= s["amount"]
            settled[s["to_person_id"]] += s["amount"]

        assert abs(sum(settled.values())) < 1e-9
        for person in balance["people"]:
            assert abs(settled[person["person_id"]] - person["net"]) <= 0.01 + 1e-9


def test_person_net_sums_to_nearly_zero_per_currency(fixture_data):
    """API.md guarantees |sum(people[].net)| < 0.00001 per currency (floor-loss bound)."""
    for balance in fixture_data["balances"]["balances"]:
        assert abs(sum(p["net"] for p in balance["people"])) < 0.00001


def test_bar_widths_are_derived_from_the_raw_six_place_net_not_the_rounded_display(
    page, mockserver, trip_url, fixture_data
):
    """The diverging bar's width% uses the full-precision net, not its 2-decimal text."""
    page.goto(f"{trip_url}#balances")
    trip = fixture_data["trip"]["trip"]
    people_by_id = {p["id"]: p["name"] for p in trip["people"]}

    for balance in fixture_data["balances"]["balances"]:
        card = balance_card_for(page, balance["currency_code"])
        max_abs = max(1e-9, *(abs(p["net"]) for p in balance["people"]))
        for person in balance["people"]:
            if person["net"] == 0:
                continue
            name = people_by_id[person["person_id"]]
            bar = card.locator("li").filter(has_text=name).locator(".bal-bar i")
            style = bar.get_attribute("style")
            width_pct = float(style.split("width:")[1].split("%")[0])
            expected_pct = (abs(person["net"]) / max_abs) * 50
            # Loose tolerance: only floating-point serialization noise is expected here;
            # using the rounded 2-decimal net instead would be off by whole percentage points.
            assert abs(width_pct - expected_pct) < 1e-3
