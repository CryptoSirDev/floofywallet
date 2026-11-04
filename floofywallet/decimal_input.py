"""Unambiguous FLOOF decimal entry for dot and comma locales."""
from decimal import Decimal, InvalidOperation
import re

def parse_decimal_input(value):
    if not isinstance(value, str):
        raise ValueError("Enter a decimal number")
    raw = value.strip()
    if not re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", raw):
        raise ValueError("Use a dot or comma decimal separator, without thousands separators")
    try:
        result = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal number") from exc
    if not result.is_finite() or result.as_tuple().exponent < -8:
        raise ValueError("Maximum 8 decimal places")
    return result
