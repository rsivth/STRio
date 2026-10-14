"""New in 0.1.0: conservative interpretation of allele labels."""

from __future__ import annotations

import unittest
from decimal import Decimal

from strio import Allele, AlleleKind, AlleleValue, parse_allele_label


class ParseAlleleLabelTests(unittest.TestCase):
    def test_repeat_numbers_and_microvariants(self) -> None:
        cases = {
            "15": (Decimal("15"), 15, 0),
            "9.3": (Decimal("9.3"), 9, 3),
            "33.2": (Decimal("33.2"), 33, 2),
            " 8.1 ": (Decimal("8.1"), 8, 1),
            "0": (Decimal("0"), 0, 0),
        }
        for label, (number, full, partial) in cases.items():
            with self.subTest(label=label):
                value = parse_allele_label(label)
                self.assertIs(value.kind, AlleleKind.NUMERIC)
                self.assertTrue(value.is_numeric)
                self.assertEqual(value.number, number)
                self.assertEqual(value.full_repeats, full)
                self.assertEqual(value.partial_bases, partial)

    def test_numeric_designations_sort_in_nomenclature_order(self) -> None:
        labels = ["10", "9.3", "9", "11", "9.1"]
        ordered = sorted(labels, key=lambda label: parse_allele_label(label).number or 0)
        self.assertEqual(ordered, ["9", "9.1", "9.3", "10", "11"])

    def test_sex_alleles_in_any_case(self) -> None:
        for label, kind in (("X", AlleleKind.X), ("x", AlleleKind.X), ("Y", AlleleKind.Y)):
            with self.subTest(label=label):
                self.assertIs(parse_allele_label(label).kind, kind)

    def test_off_ladder_in_any_case(self) -> None:
        for label in ("OL", "ol", " Ol "):
            with self.subTest(label=label):
                self.assertIs(parse_allele_label(label).kind, AlleleKind.OFF_LADDER)

    def test_anything_else_is_other_and_never_guessed(self) -> None:
        for label in ("?", "Q", "9,3", "9.30", "-1", "1e3", "11/14", "INC", "", "15a"):
            with self.subTest(label=label):
                value = parse_allele_label(label)
                self.assertIs(value.kind, AlleleKind.OTHER)
                self.assertIsNone(value.number)
                self.assertIsNone(value.full_repeats)
                self.assertIsNone(value.partial_bases)

    def test_value_invariants(self) -> None:
        invalid = (
            lambda: AlleleValue(AlleleKind.NUMERIC),
            lambda: AlleleValue(AlleleKind.NUMERIC, Decimal("NaN")),
            lambda: AlleleValue(AlleleKind.NUMERIC, Decimal("-1")),
            lambda: AlleleValue(AlleleKind.X, Decimal("1")),
        )
        for factory in invalid:
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()
        with self.assertRaises(TypeError):
            AlleleValue("numeric", Decimal("1"))  # type: ignore[arg-type]


class AlleleValueOnModelTests(unittest.TestCase):
    def test_allele_derives_value_from_label(self) -> None:
        allele = Allele(1, " 9.3 ", 750)
        self.assertEqual(allele.label, "9.3")
        self.assertEqual(allele.value, AlleleValue(AlleleKind.NUMERIC, Decimal("9.3")))

    def test_label_text_stays_authoritative(self) -> None:
        allele = Allele(1, "OL", 300)
        self.assertEqual(allele.label, "OL")
        self.assertIs(allele.value.kind, AlleleKind.OFF_LADDER)

    def test_value_is_not_a_constructor_argument(self) -> None:
        with self.assertRaises(TypeError):
            Allele(1, "15", 100, value=None)  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
