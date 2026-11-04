"""Offline tests for read-only local Core RPC validation."""
import unittest
from decimal import Decimal
from floofywallet.core_reader import LocalCoreReader, CoreReadError, parse_gettxout, verify_p2pkh_outpoint

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

class ScriptVerificationTests(unittest.TestCase):
    def setUp(self):
        from floofywallet.addresses import encode_p2pkh
        self.hash160 = bytes.fromhex("37fa93723619acae2132a0dc14727ab0d6d6b5f2")
        self.address = encode_p2pkh(self.hash160)
        self.output = {
            "value": "10.00000000", "confirmations": 591, "coinbase": False,
            "scriptPubKey": {"hex": "76a914" + self.hash160.hex() + "88ac"},
        }

    def test_matching_script(self):
        result = verify_p2pkh_outpoint(self.output, self.address, Decimal("10"))
        self.assertEqual(result["confirmations"], 591)

    def test_wrong_address_rejected(self):
        from floofywallet.addresses import encode_p2pkh
        with self.assertRaises(CoreReadError):
            verify_p2pkh_outpoint(self.output, encode_p2pkh(bytes(20)), Decimal("10"))

    def test_mismatched_amount_rejected(self):
        with self.assertRaises(CoreReadError):
            verify_p2pkh_outpoint(self.output, self.address, Decimal("11"))

    def test_missing_utxo_rejected(self):
        with self.assertRaises(CoreReadError):
            verify_p2pkh_outpoint(None, self.address)

    def test_unconfirmed_rejected(self):
        data = dict(self.output, confirmations=0)
        with self.assertRaises(CoreReadError):
            verify_p2pkh_outpoint(data, self.address)

    def test_immature_coinbase_rejected(self):
        data = dict(self.output, coinbase=True, confirmations=99)
        with self.assertRaises(CoreReadError):
            verify_p2pkh_outpoint(data, self.address)

    def test_mature_coinbase_allowed(self):
        data = dict(self.output, coinbase=True, confirmations=100)
        self.assertEqual(verify_p2pkh_outpoint(data, self.address)["confirmations"], 100)

    def test_non_p2pkh_script_rejected(self):
        data = dict(self.output, scriptPubKey={"hex": "a914" + self.hash160.hex() + "87"})
        with self.assertRaises(CoreReadError):
            verify_p2pkh_outpoint(data, self.address)

    def test_reader_verifies_matching_address(self):
        from unittest.mock import patch
        reader = LocalCoreReader("http://127.0.0.1:6662", "user", "secret")
        with patch.object(reader, "_call", return_value=self.output) as rpc:
            result = reader.verify_address_outpoint("a" * 64, 0, self.address, Decimal("10"))
        self.assertEqual(result["confirmations"], 591)
        rpc.assert_called_once_with("gettxout", ["a" * 64, 0, True])

    def test_reader_rejects_wrong_script(self):
        from unittest.mock import patch
        from floofywallet.addresses import encode_p2pkh
        reader = LocalCoreReader("http://127.0.0.1:6662", "user", "secret")
        with patch.object(reader, "_call", return_value=self.output):
            with self.assertRaises(CoreReadError):
                reader.verify_address_outpoint("a" * 64, 0, encode_p2pkh(bytes(20)), Decimal("10"))

    def test_invalid_confirmation_threshold(self):
        with self.assertRaises(ValueError):
            verify_p2pkh_outpoint(self.output, self.address, min_confirmations=0)


if __name__ == "__main__":
    unittest.main()
