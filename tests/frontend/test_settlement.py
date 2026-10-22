"""Tests for a settled trip: the Total's stored rates, settle and unlock, and the lock.

components/TotalRatesPanel.js renders the Total's controls on Balances and Statistics
alike — editable with *Fix rates & settle* while the trip is open, read-only with the
badge and *Unlock* once `trip.settlement` is set. On a settled trip ItemModal.js
disables an item's money controls and every transfer control, and the feed and the
setup currencies offer no write the server would refuse.
"""

import copy

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import CURRENCY_ID, load_fixture, rate_input, set_rates

SETTLEMENT = {
    "target_currency_id": CURRENCY_ID["ISK"],
    "settled_at": "2026-09-22T18:00:00Z",
    "rates": [
        {"currency_id": CURRENCY_ID["EUR"], "rate": 150},
        {"currency_id": CURRENCY_ID["DKK"], "rate": 20.5},
    ],
}
BADGE = "Settled on 22 Sep 2026"
LOCKED_HINT = "This trip is settled"
TRIP_SETTLED = "This trip is settled — unlock it on Balances to change its money."
INVALID_RATE = "A rate must be a positive number with up to 9 decimal places."
NOT_SETTLED = "This trip isn't settled."
# The PUT body a Total with EUR 150 and DKK 20.5 typed against ISK sends.
SENT = {
    "target_currency_id": CURRENCY_ID["ISK"],
    "rates": [
        {"currency_id": CURRENCY_ID["EUR"], "rate": "150"},
        {"currency_id": CURRENCY_ID["DKK"], "rate": "20.5"},
    ],
}


@pytest.fixture(params=[pytest.param("balances", id="balances"), pytest.param("stats", id="stats")])
def total_tab(request):
    """Return the tab whose Total the test reads: Balances or Statistics."""
    return request.param


def show_total(page, tab):
    """Bring the Total on screen; Statistics picks it from the currency dropdown."""
    if tab == "stats":
        page.locator("#stats-currency").select_option(label="Total")
    page.locator("#cur-total").wait_for()
    return page.locator("#cur-total")


@pytest.fixture
def settled_data(fixture_data):
    """Return `fixture_data` with the trip settled in ISK at EUR 150 and DKK 20.5."""
    fixture_data["trip"]["trip"]["settlement"] = copy.deepcopy(SETTLEMENT)
    return fixture_data


@pytest.fixture
def settled_trip(settled_data, mockserver, open_trip):
    """Return `open_trip` against a mock serving the settled trip."""
    return open_trip


@pytest.fixture
def agreement(stub, fixture_data, slug):
    """Answer the settlement writes and the trip read as a server would, one agreement at a time.

    PUT stores the agreement it was sent and DELETE clears it; `GET /trips/{slug}`
    then answers with the trip carrying whichever is current. Returns the PUT bodies.
    """
    trip = fixture_data["trip"]["trip"]
    current = {"settlement": None}

    def write(request):
        if request.method == "PUT":
            sent = request.post_data_json
            current["settlement"] = {
                "target_currency_id": sent["target_currency_id"],
                "settled_at": SETTLEMENT["settled_at"],
                "rates": [
                    {"currency_id": r["currency_id"], "rate": float(r["rate"])}
                    for r in sent["rates"]
                ],
            }
        else:
            current["settlement"] = None
        return 200, {"trip": {**trip, **current}}

    stub(
        f"**/api/v1/trips/{slug}",
        lambda request: (200, {"trip": {**trip, **current}}),
        method="GET",
    )
    return stub(f"**/api/v1/trips/{slug}/settlement", write)


def expect_settled(total):
    """Assert the Total shows the stored agreement read-only, with the badge and Unlock."""
    expect(total.locator("#rates-target")).to_be_disabled()
    expect(total.locator("#rates-target")).to_have_value(str(CURRENCY_ID["ISK"]))
    for code in ("EUR", "DKK"):
        expect(rate_input(total.page, code)).to_have_attribute("readonly", "")
    expect(total.locator(".settled-badge")).to_have_text(BADGE)
    expect(total.get_by_role("button", name="Unlock")).to_be_visible()
    expect(total.get_by_role("button", name="Fix rates & settle")).to_have_count(0)


def expect_open(total):
    """Assert the Total's form is editable and offers to settle, with no badge."""
    expect(total.locator("#rates-target")).to_be_enabled()
    for code in ("EUR", "DKK"):
        expect(rate_input(total.page, code)).not_to_have_attribute("readonly", "")
    expect(total.locator(".settled-badge")).to_have_count(0)
    expect(total.get_by_role("button", name="Fix rates & settle")).to_be_visible()
    expect(total.get_by_role("button", name="Unlock")).to_have_count(0)


# --- the Total ----------------------------------------------------------------------


def test_settled_total_shows_the_stored_agreement_read_only(settled_trip, total_tab):
    """Both Totals show the stored target and rates read-only, the badge, and Unlock."""
    total = show_total(settled_trip(total_tab), total_tab)

    expect_settled(total)
    expect(rate_input(total.page, "EUR")).to_have_value("150")
    expect(rate_input(total.page, "DKK")).to_have_value("20.5")


def test_settled_total_ignores_this_browsers_typed_rates(settled_data, mockserver, page, open_trip):
    """Rates typed into this browser earlier stay out of the settled Total's form."""
    page.add_init_script(
        "window.localStorage.setItem('rates:iceland-2026',"
        " JSON.stringify({target: 2, values: {1: '0.007', 3: '0.13'}}))"
    )

    page = open_trip("balances")

    expect(page.locator("#rates-target")).to_have_value(str(CURRENCY_ID["ISK"]))
    expect(rate_input(page, "EUR")).to_have_value("150")


def test_settled_balances_badge_every_currency_block(settled_trip):
    """Each currency's own balance block carries the same badge as the Total."""
    page = settled_trip("balances")

    for currency_id in CURRENCY_ID.values():
        expect(page.locator(f"#cur-{currency_id} .settled-badge")).to_have_text(BADGE)


def test_open_total_offers_settle_only_once_every_rate_is_typed(balances_page):
    """Fix rates & settle appears exactly when the server would accept the agreement."""
    total = show_total(balances_page, "balances")
    set_rates(balances_page, EUR="150")
    expect(total.get_by_role("button", name="Fix rates & settle")).to_have_count(0)

    set_rates(balances_page, DKK="20.5")

    expect(total.get_by_role("button", name="Fix rates & settle")).to_be_visible()


def test_settle_unlock_settle_switches_the_total_each_time(open_trip, total_tab, agreement):
    """Settle, unlock and settle again: the buttons and the form's lock follow every step."""
    page = open_trip(total_tab)
    page.on("dialog", lambda dialog: dialog.accept())
    total = show_total(page, total_tab)
    set_rates(page, EUR="150", DKK="20.5")
    expect_open(total)

    for step in range(3):
        if step % 2 == 0:
            total.get_by_role("button", name="Fix rates & settle").click()
            expect_settled(total)
        else:
            total.get_by_role("button", name="Unlock").click()
            expect_open(total)

    assert agreement == [SENT, None, SENT]


def test_settle_sends_a_locale_typed_rate_canonically(page, open_trip, agreement):
    """A rate typed with a Czech decimal comma is sent as the canonical decimal string."""
    page.add_init_script("window.localStorage.setItem('lang', 'cs')")
    page = open_trip("balances")
    page.on("dialog", lambda dialog: dialog.accept())
    total = show_total(page, "balances")
    set_rates(page, EUR="150", DKK="20,5")

    total.get_by_role("button", name="Zafixovat kurzy a vyrovnat").click()

    expect(total.locator(".settled-badge")).to_be_visible()
    assert agreement == [SENT]


def test_rejected_settle_shows_the_error_under_the_button(balances_page, stub):
    """A rate the server refuses keeps the trip open and says why beside the settle button."""
    body = load_fixture("errors/422_invalid_rate.json")
    stub("**/api/v1/trips/*/settlement", lambda request: (422, body), method="PUT")
    balances_page.on("dialog", lambda dialog: dialog.accept())
    total = show_total(balances_page, "balances")
    set_rates(balances_page, EUR="150", DKK="20.5")

    total.get_by_role("button", name="Fix rates & settle").click()

    expect(total.locator(".invalid-feedback")).to_have_text(INVALID_RATE)
    expect_open(total)


def test_failed_unlock_flashes_and_keeps_the_trip_settled(settled_trip, stub, page):
    """An unlock the server refuses - another tab unlocked first - reaches the flash."""
    body = load_fixture("errors/409_trip_not_settled.json")
    stub("**/api/v1/trips/*/settlement", lambda request: (409, body), method="DELETE")
    total = show_total(settled_trip("balances"), "balances")
    page.on("dialog", lambda dialog: dialog.accept())

    total.get_by_role("button", name="Unlock").click()

    expect(page.locator(".alert-danger")).to_have_text(NOT_SETTLED)
    expect(total.locator(".invalid-feedback")).to_have_count(0)
    expect_settled(total)


def test_settle_dismissed_sends_nothing(balances_page, count_requests):
    """Dismissing the confirmation leaves the trip open and sends no request."""
    balances_page.once("dialog", lambda dialog: dialog.dismiss())
    total = show_total(balances_page, "balances")
    set_rates(balances_page, EUR="150", DKK="20.5")
    sent = count_requests("*/settlement")

    total.get_by_role("button", name="Fix rates & settle").click()

    expect_open(total)
    assert sent == []


# --- the lock -----------------------------------------------------------------------


@pytest.fixture
def settled_items_page(settled_trip):
    """Return the settled trip on the Items tab."""
    return settled_trip()


def open_edit(page, row_selector):
    """Click a feed row's Edit button and return the open modal."""
    page.locator(row_selector).first.get_by_role("button", name="Edit").click()
    modal = page.locator(".modal.show")
    modal.wait_for()
    return modal


def test_settled_feed_disables_adding(settled_items_page):
    """Neither add button - the toolbar's and the floating one - is enabled on a settled trip."""
    buttons = settled_items_page.locator("button", has=settled_items_page.locator(".bi-plus-lg"))
    expect(buttons).to_have_count(2)
    for button in buttons.all():
        expect(button).to_be_disabled()


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param('input[name="amount"]', id="amount"),
        pytest.param('select[name="currency_id"]', id="currency"),
        pytest.param("#pay-1", id="payer"),
        pytest.param("#split-1", id="split-person"),
        pytest.param('#split-body button:text-is("Shares")', id="split-mode"),
    ],
)
def test_settled_item_money_controls_are_disabled(settled_items_page, selector):
    """An item's amount, currency, payer and split controls are frozen while settled."""
    modal = open_edit(settled_items_page, ".item-row:has-text('Dinner at Messinn')")

    expect(modal.locator(selector)).to_be_disabled()


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param('input[name="name"]', id="name"),
        pytest.param('select[name="country_id"]', id="country"),
        pytest.param('select[name="wallet_id"]', id="wallet"),
        pytest.param('input[name="city"]', id="city"),
        pytest.param('input[type="datetime-local"]', id="when"),
    ],
)
def test_settled_item_free_fields_stay_enabled(settled_items_page, selector):
    """Every item field outside the balances stays editable on a settled trip."""
    modal = open_edit(settled_items_page, ".item-row:has-text('Dinner at Messinn')")

    expect(modal.locator(selector)).to_be_enabled()


def test_settled_item_shows_the_hint_and_hides_delete(settled_items_page):
    """The modal says why the money is frozen, and offers no Delete."""
    modal = open_edit(settled_items_page, ".item-row:has-text('Dinner at Messinn')")

    expect(modal.locator(".settled-hint")).to_contain_text(LOCKED_HINT)
    expect(modal.get_by_role("button", name="Delete")).to_have_count(0)
    expect(modal.get_by_role("button", name="Save", exact=True)).to_be_enabled()


def test_settled_transfer_disables_every_control(settled_items_page):
    """A transfer is frozen whole: every input and select, Save and Delete included."""
    modal = open_edit(settled_items_page, ".transfer-row:has-text('20,000 ISK')")

    expect(modal.locator(".settled-hint")).to_contain_text(LOCKED_HINT)
    controls = modal.locator(".modal-body input, .modal-body select")
    expect(controls).not_to_have_count(0)
    for control in controls.all():
        expect(control).to_be_disabled()
    expect(modal.get_by_role("button", name="Save", exact=True)).to_be_disabled()
    expect(modal.get_by_role("button", name="Delete")).to_have_count(0)


def test_stale_tab_save_flashes_trip_settled(open_edit_modal, stub, page):
    """A save the server refuses because another tab settled the trip reaches the flash."""
    stub(
        "**/api/v1/trips/*/items/42",
        lambda request: (409, load_fixture("errors/409_trip_settled.json")),
        method="PATCH",
    )
    modal = open_edit_modal("Dinner at Messinn")

    modal.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator(".alert-danger")).to_have_text(TRIP_SETTLED)


def test_settled_setup_freezes_currencies_and_offers_archive(settled_trip, card):
    """Setup offers no currency add or delete, and shows the badge beside Archive."""
    page = settled_trip("setup")
    currencies = card("Currencies")

    expect(currencies.get_by_role("button", name="+ Add")).to_be_disabled()
    deletes = currencies.get_by_role("button", name="Delete")
    expect(deletes).to_have_count(len(CURRENCY_ID))
    for button in deletes.all():
        expect(button).to_be_disabled()
    trip_row = card("Trip").locator("li").filter(has=page.locator(".settled-badge"))
    expect(trip_row.locator(".settled-badge")).to_have_text(BADGE)
    expect(trip_row.get_by_role("link", name="Archive trip")).to_be_visible()
