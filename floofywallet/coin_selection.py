"""Experimental, offline-only UTXO selection for legacy P2PKH previews.

Explorer outputs are untrusted. This does NOT establish spendability, validate
scripts, account for mempool conflicts, sign, or authorize a broadcast.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

ATOMIC = Decimal("0.00000001")
REFERENCE_RATE = Decimal("0.01000000")  # Core 4.0.4 UI reference; not a live estimate.
DUST_FLOOF = Decimal("0.01000000")  # Conservative change threshold; verify Core policy.


@dataclass(frozen=True)
class SelectionPreview:
    selected: tuple
    input_total: Decimal
    amount: Decimal
    estimated_fee: Decimal
    change: Decimal
    estimated_bytes: int
    output_count: int


def _check_amount(value, positive=True):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("Amount must be a finite Decimal")
    if (value <= 0 if positive else value < 0) or value != value.quantize(ATOMIC):
        raise ValueError("Invalid amount or precision")


def _fee(inputs, outputs, rate):
    # Deliberately conservative illustrative legacy P2PKH approximation.
    size = 10 + 149 * inputs + 34 * outputs
    fee = (Decimal(size) * rate / 1000 / ATOMIC).to_integral_value(
        rounding=ROUND_CEILING) * ATOMIC
    return size, fee


def preview_selection(utxos, amount, rate=REFERENCE_RATE):
    """Select reported UTXOs deterministically; returns illustration, never authorization.

    Refuses empty, duplicate, invalid, or excessive explorer UTXO collections.
    Does not fetch additional pages or check confirmations and scripts.
    """
    _check_amount(amount)
    _check_amount(rate)
    if not isinstance(utxos, (list, tuple)) or not 1 <= len(utxos) <= 1000:
        raise ValueError("UTXO list unavailable, empty, or too large")
    seen = set()
    for u in utxos:
        key = (u.txid, u.vout)
        if key in seen:
            raise ValueError("Duplicate UTXO")
        seen.add(key)
        _check_amount(u.amount)
    ordered = sorted(utxos, key=lambda u: (-u.amount, u.txid, u.vout))
    selected = []
    total = Decimal("0")
    for utxo in ordered:
        selected.append(utxo)
        total += utxo.amount
        size2, fee2 = _fee(len(selected), 2, rate)
        if total >= amount + fee2 + DUST_FLOOF:
            return SelectionPreview(tuple(selected), total, amount, fee2,
                                    total - amount - fee2, size2, 2)
        size1, fee1 = _fee(len(selected), 1, rate)
        if total >= amount + fee1:
            # No change output; leftover becomes additional miner fee.
            return SelectionPreview(tuple(selected), total, amount,
                                    total - amount, Decimal("0"), size1, 1)
    raise ValueError("Insufficient reported UTXOs for amount and fee")
