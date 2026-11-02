import unittest
from decimal import Decimal
from unittest.mock import patch
from io import BytesIO

from floofywallet.explorer_client import (
    AddressSummary, ExplorerClient, ExplorerError, parse_address_summary,
    parse_address_transactions, parse_address_utxos,
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
                return BytesIO(json.dumps(self.payload).encode())
            def __exit__(self, *args):
                return False
        client = ExplorerClient()
        Response.payload = {"address": ADDRESS, "page": 0, "limit": 30, "transactions": []}
        with patch("floofywallet.explorer_client.urlopen", return_value=Response()) as mock:
            self.assertEqual(client.get_address_transactions(ADDRESS), [])
            self.assertTrue(mock.call_args.args[0].full_url.endswith("/txs"))
            Response.payload = {"address": ADDRESS, "page": 0, "has_more": False, "utxos": []}
            self.assertEqual(client.get_address_utxos(ADDRESS), [])
            self.assertTrue(mock.call_args.args[0].full_url.endswith("/utxos"))

    def test_real_faucet_history_and_utxo(self):
        address = "FAw6og7DCB6RZfWLSCwnSHwKmPt69zABCj"
        txid = "291862035229d57377827ae7843512f7d7e6d33a49ddb4dd6a5ee05fd634e762"
        history = {"address": address, "page": 0, "limit": 30, "transactions": [
            {"txid": txid, "blockindex": 245990, "time": 1793614253,
             "amount": "10.00000000", "received": "10.00000000", "sent": "0.00000000"}
        ]}
        utxos = {"address": address, "page": 0, "has_more": False, "utxos": [
            {"txid": txid, "vout": 0, "height": 245990, "amount": "10.00000000"}
        ]}
        tx = parse_address_transactions(history, address)[0]
        utxo = parse_address_utxos(utxos, address)[0]
        self.assertEqual(tx.amount, Decimal("10.00000000"))
        self.assertEqual(tx.block_height, utxo.height)
        self.assertEqual(tx.txid, utxo.txid)
        self.assertEqual(utxo.vout, 0)

    def test_reject_invalid_utxo(self):
        address = "FAw6og7DCB6RZfWLSCwnSHwKmPt69zABCj"
        with self.assertRaises(ExplorerError):
            parse_address_utxos({"address": address, "page": 0, "has_more": False,
                                 "utxos": [{"txid": "bad", "vout": 0, "height": 1,
                                            "amount": "10.00000000"}]}, address)

    def test_utxo_snapshot_pagination_status(self):
        import json
        class Response:
            def __enter__(self):
                return BytesIO(json.dumps(self.payload).encode())
            def __exit__(self, *args):
                return False
        Response.payload = {"address": ADDRESS, "page": 0, "has_more": False, "utxos": []}
        with patch("floofywallet.explorer_client.urlopen", return_value=Response()):
            items, has_more = ExplorerClient().get_address_utxo_snapshot(ADDRESS)
        self.assertEqual(items, [])
        self.assertFalse(has_more)

    def test_utxo_snapshot_rejects_wrong_page(self):
        import json
        class Response:
            def __enter__(self):
                return BytesIO(json.dumps(self.payload).encode())
            def __exit__(self, *args):
                return False
        Response.payload = {"address": ADDRESS, "page": 1, "has_more": False, "utxos": []}
        with patch("floofywallet.explorer_client.urlopen", return_value=Response()):
            with self.assertRaises(ExplorerError):
                ExplorerClient().get_address_utxo_snapshot(ADDRESS)

    def test_utxo_snapshot_rejects_empty_nonterminal_page(self):
        import json
        class Response:
            def __enter__(self):
                return BytesIO(json.dumps(self.payload).encode())
            def __exit__(self, *args):
                return False
        Response.payload = {"address": ADDRESS, "page": 0, "has_more": True, "utxos": []}
        with patch("floofywallet.explorer_client.urlopen", return_value=Response()):
            with self.assertRaises(ExplorerError):
                ExplorerClient().get_address_utxo_snapshot(ADDRESS)

    def test_all_utxos_two_pages(self):
        txid = "a" * 64
        pages = [
            {"address": ADDRESS, "page": 0, "has_more": True, "utxos": [
                {"txid": txid, "vout": 0, "height": 10, "amount": "1.00000000"}]},
            {"address": ADDRESS, "page": 1, "has_more": False, "utxos": [
                {"txid": txid, "vout": 1, "height": 10, "amount": "2.00000000"}]},
        ]
        client = ExplorerClient()
        with patch.object(client, "_get_address_endpoint", side_effect=pages) as mocked:
            result = client.get_all_address_utxos(ADDRESS)
        self.assertEqual(len(result), 2)
        self.assertEqual(mocked.call_args_list[1].args[1], "/utxos?page=1")

    def test_all_utxos_rejects_duplicate_across_pages(self):
        item = {"txid": "a" * 64, "vout": 0, "height": 10, "amount": "1.00000000"}
        pages = [
            {"address": ADDRESS, "page": 0, "has_more": True, "utxos": [item]},
            {"address": ADDRESS, "page": 1, "has_more": False, "utxos": [item]},
        ]
        client = ExplorerClient()
        with patch.object(client, "_get_address_endpoint", side_effect=pages):
            with self.assertRaises(ExplorerError):
                client.get_all_address_utxos(ADDRESS)

    def test_all_utxos_rejects_repeated_page(self):
        pages = [
            {"address": ADDRESS, "page": 0, "has_more": True, "utxos": [
                {"txid": "a" * 64, "vout": 0, "height": 10, "amount": "1.00000000"}]},
            {"address": ADDRESS, "page": 0, "has_more": False, "utxos": []},
        ]
        client = ExplorerClient()
        with patch.object(client, "_get_address_endpoint", side_effect=pages):
            with self.assertRaises(ExplorerError):
                client.get_all_address_utxos(ADDRESS)

    def test_all_utxos_rejects_page_limit(self):
        page = {"address": ADDRESS, "page": 0, "has_more": True, "utxos": [
            {"txid": "a" * 64, "vout": 0, "height": 10, "amount": "1.00000000"}]}
        client = ExplorerClient()
        with patch.object(client, "_get_address_endpoint", return_value=page):
            with self.assertRaises(ExplorerError):
                client.get_all_address_utxos(ADDRESS, max_pages=1)

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
