"""Round money to minor units (hundredths) with a zero-sum correction.

The one place money is rounded, then a greedy minimum-transfer plan.
"""

from fractions import Fraction

from app.services.money import MICRO_PER_MINOR


def round_nets_to_minor(net_micro: dict[int, int], roster_order: dict[int, int]) -> dict[int, int]:
    """Round each person's net (in micro-units) to the nearest minor unit (cent).

    Then nudge by one minor unit, largest rounding error first, until the
    total is exactly zero. Deterministic; ties broken by `roster_order`.
    """
    exact = {pid: Fraction(value, MICRO_PER_MINOR) for pid, value in net_micro.items()}
    minor = {pid: round(value) for pid, value in exact.items()}
    error = {pid: minor[pid] - exact[pid] for pid in minor}

    total = sum(minor.values())
    while total != 0:
        if total > 0:
            pid = max(minor, key=lambda p: (error[p], -roster_order[p]))
            minor[pid] -= 1
            error[pid] -= 1
            total -= 1
        else:
            pid = min(minor, key=lambda p: (error[p], roster_order[p]))
            minor[pid] += 1
            error[pid] += 1
            total += 1

    return minor


def suggest_transfers(
    net_minor: dict[int, int], roster_order: dict[int, int]
) -> list[dict[str, int]]:
    """Greedy min-cash-flow: repeatedly match the largest creditor with the largest debtor.

    At most n-1 transfers, amounts in minor units summing to zero.
    """
    creditors = sorted(
        ([pid, amount] for pid, amount in net_minor.items() if amount > 0),
        key=lambda pair: (-pair[1], roster_order[pair[0]]),
    )
    debtors = sorted(
        ([pid, amount] for pid, amount in net_minor.items() if amount < 0),
        key=lambda pair: (pair[1], roster_order[pair[0]]),
    )

    transfers: list[dict[str, int]] = []
    ci = di = 0
    while ci < len(creditors) and di < len(debtors):
        creditor_id, credit = creditors[ci]
        debtor_id, debt = debtors[di]
        amount = min(credit, -debt)

        transfers.append(
            {"from_person_id": debtor_id, "to_person_id": creditor_id, "amount": amount}
        )

        creditors[ci][1] -= amount
        debtors[di][1] += amount
        if creditors[ci][1] == 0:
            ci += 1
        if debtors[di][1] == 0:
            di += 1

    return transfers
