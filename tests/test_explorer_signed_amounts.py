"""Regression tests for signed explorer transaction amounts."""
from decimal import Decimal
import unittest

from floofywallet.explorer_client import (
    ExplorerError, parse_address_transactions, parse_address_utxos,
)

ADDRESS = "FQfc9JBsGrBgq5WgRLRPdCVHje7CxnJ2rF"
TXID = "83c4c2b4dad93948e08271b7bfda9270dee62c82f2556066fd35eddd7fc9cc03"


class SignedAmountsTests(unittest.TestCase):
    def test_negative_net_transaction_amount_is_valid(self):
        data = {"address": ADDRESS, "page": 0, "limit": 30, "transactions": [{
            "txid": TXID, "blockindex": 236126, "time": 1792777768,
            "amount": "-2500.00264000", "received": "21.75936441",
            "sent": "2521.76200441",
        }]}
        transactions = parse_address_transactions(data, ADDRESS)
        self.assertEqual(transactions[0].amount, Decimal("-2500.00264000"))
        self.assertEqual(transactions[0].received, Decimal("21.75936441"))

    def test_negative_utxo_amount_is_rejected(self):
        data = {"address": ADDRESS, "page": 0, "has_more": False, "utxos": [{
            "txid": TXID, "vout": 0, "height": 236126,
            "amount": "-1.00000000",
        }]}
        with self.assertRaises(ExplorerError):
            parse_address_utxos(data, ADDRESS)


if __name__ == "__main__":
    unittest.main()
