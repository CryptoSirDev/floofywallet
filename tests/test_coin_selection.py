"""Offline tests for experimental UTXO preview."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from floofywallet.coin_selection import preview_selection


def coin(n, amount):
    return SimpleNamespace(txid=f"{n:064x}", vout=0, amount=Decimal(amount))


class CoinSelectionTests(unittest.TestCase):
    def test_change_output(self):
        p = preview_selection([coin(1, "20")], Decimal("10"))
        self.assertEqual(p.output_count, 2)
        self.assertEqual(p.estimated_bytes, 227)
        self.assertEqual(p.estimated_fee, Decimal("0.00227000"))
        self.assertEqual(p.change, Decimal("9.99773000"))

    def test_multiple_inputs(self):
        p = preview_selection([coin(1, "6"), coin(2, "6")], Decimal("10"))
        self.assertEqual(len(p.selected), 2)
        self.assertEqual(p.estimated_bytes, 376)

    def test_insufficient(self):
        with self.assertRaises(ValueError):
            preview_selection([coin(1, "1")], Decimal("10"))

    def test_no_change(self):
        p = preview_selection([coin(1, "10.00200000")], Decimal("10"))
        self.assertEqual(p.output_count, 1)
        self.assertEqual(p.change, Decimal("0"))

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            preview_selection([coin(1, "6"), coin(1, "6")], Decimal("10"))

    def test_invalid_rate(self):
        with self.assertRaises(ValueError):
            preview_selection([coin(1, "20")], Decimal("10"), Decimal("-1"))


if __name__ == "__main__":
    unittest.main()
