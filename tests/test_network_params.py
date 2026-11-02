"""FloofyChain V4 constants from src/chainparams.cpp, mainnet."""

import unittest

from floofywallet.network_params import MAINNET


class TestMainnetParams(unittest.TestCase):
    def test_legacy_prefixes(self):
        self.assertEqual(MAINNET.p2pkh_prefix, 35)
        self.assertEqual(MAINNET.p2sh_prefix, 22)
        self.assertEqual(MAINNET.wif_prefix, 163)

    def test_extended_key_versions(self):
        self.assertEqual(MAINNET.xpub_version.hex(), "02facafd")
        self.assertEqual(MAINNET.xprv_version.hex(), "02fac398")

    def test_chain_identifiers(self):
        self.assertEqual(MAINNET.coinbase_maturity, 10)
        self.assertEqual(MAINNET.p2p_port, 6661)
        self.assertEqual(len(MAINNET.genesis_hash), 64)


if __name__ == "__main__":
    unittest.main()
