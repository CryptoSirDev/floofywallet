"""Offline tests for read-only local Core RPC validation."""
import unittest
from decimal import Decimal
from floofywallet.core_reader import LocalCoreReader, CoreReadError, parse_gettxout

class CoreReaderTests(unittest.TestCase):
    def test_missing_outpoint(self):
        self.assertIsNone(parse_gettxout(None))

    def test_valid_outpoint(self):
        result = parse_gettxout({"value": 10, "confirmations": 12,
                                 "coinbase": False, "scriptPubKey": {"hex": "76a9"}},
                                Decimal("10"))
        self.assertEqual(result["amount"], Decimal("10"))
        self.assertEqual(result["confirmations"], 12)

    def test_amount_mismatch(self):
        with self.assertRaises(CoreReadError):
            parse_gettxout({"value": 9, "confirmations": 1,
                            "scriptPubKey": {"hex": "00"}}, Decimal("10"))

    def test_reject_remote_rpc(self):
        with self.assertRaises(ValueError):
            LocalCoreReader("http://example.com:6662", "user", "secret")

    def test_reject_credentials_in_url(self):
        with self.assertRaises(ValueError):
            LocalCoreReader("http://user:pass@localhost:6662", "user", "secret")

    def test_reject_invalid_outpoint(self):
        reader = LocalCoreReader("http://127.0.0.1:6662", "user", "secret")
        with self.assertRaises(ValueError):
            reader.check_outpoint("bad", 0)

    def test_reject_non_atomic_amount(self):
        with self.assertRaises(CoreReadError):
            parse_gettxout({"value": "1.000000001", "confirmations": 1,
                            "scriptPubKey": {"hex": "00"}})

if __name__ == "__main__":
    unittest.main()
