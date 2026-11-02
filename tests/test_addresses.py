"""Unit tests only; real Core cross-validation still required."""

import unittest

from floofywallet.addresses import encode_p2pkh, validate_address
from floofywallet.base58check import decode, encode


class TestAddresses(unittest.TestCase):
    def test_base58check_round_trip(self):
        payload = bytes([35]) + bytes(range(20))
        self.assertEqual(decode(encode(payload)), payload)

    def test_legacy_address(self):
        address = encode_p2pkh(bytes(range(20)))
        self.assertTrue(address.startswith("F"))
        self.assertTrue(validate_address(address))

    def test_bad_checksum(self):
        address = encode_p2pkh(bytes(range(20)))
        replacement = "1" if address[-1] != "1" else "2"
        self.assertFalse(validate_address(address[:-1] + replacement))

    def test_wrong_network(self):
        address = encode(bytes([0]) + bytes(range(20)))
        self.assertFalse(validate_address(address))

    def test_wrong_payload_size(self):
        self.assertFalse(validate_address(encode(bytes([35]) + b"short")))

    def test_invalid_pubkey_hash(self):
        with self.assertRaises(ValueError):
            encode_p2pkh(b"not-twenty")


if __name__ == "__main__":
    unittest.main()
