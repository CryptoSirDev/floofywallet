"""Encrypted wallet vault regression tests. Uses only public test key 1."""
import tempfile
from pathlib import Path
import unittest

from floofywallet.keys import encode_wif
from floofywallet.vault import (
    VaultError, address_from_wif, decrypt_wif, encrypt_wif,
    generate_wallet, load_vault, save_vault,
)


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.wif = encode_wif((1).to_bytes(32, "big"))
        self.password = "test-password-not-for-real-funds"

    def test_roundtrip_and_address(self):
        vault = encrypt_wif(self.wif, self.password)
        self.assertEqual(vault["address"], "FGWP1xKhDP5RmV525TmUoEwX9mTZwp3sJn")
        self.assertNotIn(self.wif, str(vault))
        self.assertEqual(decrypt_wif(vault, self.password), self.wif)

    def test_wrong_password_and_tamper(self):
        vault = encrypt_wif(self.wif, self.password)
        with self.assertRaises(VaultError):
            decrypt_wif(vault, "incorrect-password-123")
        vault["ciphertext"] = ("00" if vault["ciphertext"][:2] != "00" else "01") + vault["ciphertext"][2:]
        with self.assertRaises(VaultError):
            decrypt_wif(vault, self.password)

    def test_short_password_rejected(self):
        with self.assertRaises(VaultError):
            encrypt_wif(self.wif, "short")

    def test_file_create_without_overwrite(self):
        vault = encrypt_wif(self.wif, self.password)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.wallet"
            save_vault(path, vault)
            self.assertEqual(load_vault(path), vault)
            with self.assertRaises(FileExistsError):
                save_vault(path, vault)

    def test_generated_wallet_has_valid_address(self):
        wif, address = generate_wallet()
        self.assertEqual(address_from_wif(wif), address)


if __name__ == "__main__":
    unittest.main()
