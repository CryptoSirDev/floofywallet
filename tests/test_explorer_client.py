import unittest
from decimal import Decimal
from unittest.mock import patch
from io import BytesIO

from floofywallet.explorer_client import (
    AddressSummary, ExplorerClient, ExplorerError, parse_address_summary,
)

ADDRESS = "FGWP1xKhDP5RmV525TmUoEwX9mTZwp3sJn"
SAMPLE = {
    "address": ADDRESS,
    "balance": "0.00000000",
    "received": "0.00000000",
    "sent": "0.00000000",
    "txcount": 0,
    "source": "MongoDB",
}


class ExplorerClientTests(unittest.TestCase):
    def test_parse_real_explorer_response(self):
        result = parse_address_summary(SAMPLE, ADDRESS)
        self.assertIsInstance(result, AddressSummary)
        self.assertEqual(result.balance, Decimal("0.00000000"))
        self.assertEqual(result.txcount, 0)

    def test_reject_wrong_address(self):
        with self.assertRaises(ExplorerError):
            parse_address_summary({**SAMPLE, "address": "wrong"}, ADDRESS)

    def test_reject_bad_amounts(self):
        for value in ("NaN", "Infinity", "-1", "0.000000001", "invalid", 2):
            with self.subTest(value=value):
                with self.assertRaises(ExplorerError):
                    parse_address_summary({**SAMPLE, "balance": value}, ADDRESS)

    def test_reject_bad_txcount(self):
        for value in (-1, True, "0"):
            with self.subTest(value=value):
                with self.assertRaises(ExplorerError):
                    parse_address_summary({**SAMPLE, "txcount": value}, ADDRESS)

    def test_history_and_utxo_paths(self):
        import json
        class Response:
            def __enter__(self):
                return BytesIO(json.dumps({"items": []}).encode())
            def __exit__(self, *args):
                return False
        client = ExplorerClient()
        with patch("floofywallet.explorer_client.urlopen", return_value=Response()) as mock:
            self.assertEqual(client.get_address_transactions(ADDRESS), {"items": []})
            self.assertTrue(mock.call_args.args[0].full_url.endswith("/txs"))
            self.assertEqual(client.get_address_utxos(ADDRESS), {"items": []})
            self.assertTrue(mock.call_args.args[0].full_url.endswith("/utxos"))

    def test_reject_http(self):
        with self.assertRaises(ValueError):
            ExplorerClient("http://explorer.floofychain.com")

    def test_get_address_mocked(self):
        import json
        class Response:
            def __enter__(self):
                return BytesIO(json.dumps(SAMPLE).encode())
            def __exit__(self, *args):
                return False
        with patch("floofywallet.explorer_client.urlopen", return_value=Response()) as mock:
            result = ExplorerClient().get_address(ADDRESS)
        self.assertEqual(result.source, "MongoDB")
        self.assertIn("/api/v1/address/" + ADDRESS, mock.call_args.args[0].full_url)


if __name__ == "__main__":
    unittest.main()
