import unittest
from decimal import Decimal
from floofywallet.decimal_input import parse_decimal_input

class DecimalInputTests(unittest.TestCase):
    def test_comma(self):
        self.assertEqual(parse_decimal_input("10,50"), Decimal("10.50"))
    def test_dot(self):
        self.assertEqual(parse_decimal_input("10.50"), Decimal("10.50"))
    def test_eight_places(self):
        self.assertEqual(parse_decimal_input("0,12345678"), Decimal("0.12345678"))
    def test_nine_places_rejected(self):
        with self.assertRaises(ValueError):
            parse_decimal_input("0,123456789")
    def test_mixed_separators_rejected(self):
        for value in ("1,000.50", "1.000,50", "1,2,3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_decimal_input(value)
    def test_exponent_and_sign_rejected(self):
        for value in ("1e3", "-1", "+1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_decimal_input(value)
    def test_spaces_rejected(self):
        with self.assertRaises(ValueError):
            parse_decimal_input("1 000,50")
