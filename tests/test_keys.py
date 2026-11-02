"""Deterministic key=1 vectors; NOT real wallet funds or live Core tests.

Reference secp256k1 public key for scalar 1 is the standard generator point.
The FloofyChain address and WIF version bytes come from V4 chainparams.cpp.
Core RPC comparison is still required before shipping a wallet.
"""

import unittest

from floofywallet.keys import (
    SECP256K1_ORDER,
    address_from_private,
    address_from_public_key,
    decode_wif,
    encode_wif,
    public_key_from_private,
)

KEY_ONE = (1).to_bytes(32, "big")
COMPRESSED_PUBLIC = bytes.fromhex(
    "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
)
UNCOMPRESSED_PUBLIC = bytes.fromhex(
    "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
)


class TestLegacyKeyVectors(unittest.TestCase):
    def test_compressed_generator_point(self):
        self.assertEqual(public_key_from_private(KEY_ONE), COMPRESSED_PUBLIC)
        self.assertEqual(address_from_public_key(COMPRESSED_PUBLIC), "FGWP1xKhDP5RmV525TmUoEwX9mTZwp3sJn")
        self.assertEqual(address_from_private(KEY_ONE), "FGWP1xKhDP5RmV525TmUoEwX9mTZwp3sJn")

    def test_uncompressed_generator_point(self):
        self.assertEqual(public_key_from_private(KEY_ONE, compressed=False), UNCOMPRESSED_PUBLIC)
        self.assertEqual(address_from_private(KEY_ONE, compressed=False), "FK7V2tq9AJFaYY7zBjoGjcaakQYiroFn5R")

    def test_wif_vectors_and_round_trip(self):
        compressed = "R7WnCJjdY4LQqMAD9MLZmNRPZpkL5DCVY1YFD3US2zr1uTVbv7Sr"
        uncompressed = "6TrLkoACuMEuyiixmVAsUGjEGbP3xnMjGBYYmR882p6DSW1A9rQ"
        self.assertEqual(encode_wif(KEY_ONE), compressed)
        self.assertEqual(encode_wif(KEY_ONE, compressed=False), uncompressed)
        self.assertEqual(decode_wif(compressed), (KEY_ONE, True))
        self.assertEqual(decode_wif(uncompressed), (KEY_ONE, False))

    def test_reject_invalid_private_keys(self):
        for invalid in (b"", b"\\x00" * 32, SECP256K1_ORDER.to_bytes(32, "big")):
            with self.subTest(key_length=len(invalid)):
                with self.assertRaises(ValueError):
                    public_key_from_private(invalid)

    def test_reject_other_network_wif(self):
        from floofywallet.base58check import encode
        with self.assertRaises(ValueError):
            decode_wif(encode(bytes([128]) + KEY_ONE + b"\\x01"))

    def test_reject_bad_public_key(self):
        with self.assertRaises(ValueError):
            address_from_public_key(b"\\x02" + b"\\x00" * 32)


if __name__ == "__main__":
    unittest.main()
