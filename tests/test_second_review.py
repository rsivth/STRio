"""New in 0.2.1: findings of the second external code review (of 0.2.0, 2026-10-15).

docs/TEST_PROVENANCE.md, section 0.2.1, maps each class to its finding.
"""

from __future__ import annotations

import re
import unittest
from unittest import mock

from _support import ROOT

import strio
from strio import DuplicateColumnError, NumericValueError
from strio.formats import _table
from strio.formats.genemapper import MAX_SIZE_DECIMALS

SIZE_HEADER = "Sample Name\tMarker\tAllele 1\tHeight 1\tSize 1\nS\tvWA\t14\t1\t"


def _size(value: str) -> object:
    dataset = strio.parse_genemapper(SIZE_HEADER + value + "\n")
    return dataset.sample("S").loci["vWA"].alleles[0].size_bp


class ExtraValueDocumentationTests(unittest.TestCase):
    def test_extras_are_documented_as_trimmed_everywhere(self) -> None:
        sources = (
            ROOT / "docs" / "GENEMAPPER.md",
            ROOT / "docs" / "MANUAL.md",
            ROOT / "src" / "strio" / "model.py",
            ROOT / "src" / "strio" / "formats" / "genemapper.py",
        )
        for path in sources:
            with self.subTest(path=path.name):
                text = " ".join(path.read_text(encoding="utf-8").split())
                self.assertNotIn("verbatim", text)
                self.assertRegex(text, r"surrounding whitespace removed")

    def test_extras_lose_only_surrounding_whitespace(self) -> None:
        dataset = strio.parse_genemapper(
            'Sample Name,Marker,Allele 1,Height 1,Note\nS,vWA,14,1,"  a  b  "\n'
        )
        self.assertEqual(dataset.sample("S").loci["vWA"].extra["Note"], "a  b")


class SizeDecimalPlacesTests(unittest.TestCase):
    def test_up_to_six_decimal_places_are_read(self) -> None:
        self.assertEqual(MAX_SIZE_DECIMALS, 6)
        self.assertEqual(str(_size("160.123456")), "160.123456")
        self.assertEqual(str(_size("160,25")), "160.25")

    def test_more_decimal_places_are_rejected_as_written(self) -> None:
        for value in ("160.1234567", "160.5000000", "." + "7" * 5000):
            with (
                self.subTest(value=value[:12]),
                self.assertRaisesRegex(NumericValueError, "more than 6 decimal places"),
            ):
                _size(value)

    def test_rejection_message_is_short_for_long_values(self) -> None:
        with self.assertRaises(NumericValueError) as caught:
            _size("123." + "7" * 100_000)
        self.assertLess(len(str(caught.exception)), 200)


class QuoteScanFastPathTests(unittest.TestCase):
    def test_text_without_quotes_skips_the_character_scan(self) -> None:
        with mock.patch.object(_table._CsvQuoteScanner, "validate") as validate:
            rows = _table.parse_rows("A\tB\n1\t2\n", "\t", "<text>")
        validate.assert_not_called()
        self.assertEqual(rows, [(1, ["A", "B"]), (2, ["1", "2"])])

    def test_text_with_a_quote_is_still_scanned(self) -> None:
        with self.assertRaisesRegex(strio.ParseError, "quote inside an unquoted field"):
            _table.parse_rows('A,B\nx"y,2\n', ",", "<text>")

    def test_skipping_is_safe_because_quote_free_text_always_passes_the_scan(self) -> None:
        for path in sorted((ROOT / "tests" / "fixtures").rglob("*.t*")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(fixture=path.name):
                self.assertNotIn('"', text)
                _table._CsvQuoteScanner("\t", path.name).validate(text)


class SingleDuplicateCheckTests(unittest.TestCase):
    def _error(self, header: str) -> str:
        text = f"{header}\nA\tB\tC\tD\tE\n"
        with self.assertRaises(DuplicateColumnError) as caught:
            strio.parse_genemapper(text)
        return str(caught.exception)

    def test_one_function_finds_all_name_duplicates(self) -> None:
        header = "Sample Name\tsample name\tMarker\tAllele 1\tHeight 1"
        with mock.patch.object(_table, "duplicate_names", wraps=_table.duplicate_names) as find:
            self._error(header)
        find.assert_called()
        self.assertEqual(
            _table.duplicate_names(("A", "a", "B", "B  x", "B x")), (["a"], ("B  x", "B x"))
        )

    def test_messages_are_unchanged(self) -> None:
        cases = {
            "Sample Name\tsample name\tMarker\tAllele 1\tHeight 1": (
                "Duplicate column names: ['sample name']"
            ),
            "Sample Name\tSample  Name\tMarker\tAllele 1\tHeight 1": (
                "Duplicate column names 'Sample Name' and 'Sample  Name' differ only in spacing."
            ),
            "Sample Name\tMarker\tAllele 1\tAllele  1\tHeight 1": (
                "Duplicate semantic indexed column 'allele' 1: 'Allele 1' and 'Allele  1'."
            ),
            "Sample Name\tMarker\tAllele 1\tallele 1\tHeight 1": (
                "Duplicate column names: ['allele 1']"
            ),
            "Sample Name\tMarker\tAllele 1\tAllele  1\tAllele  1": (
                "Duplicate column names: ['Allele  1']"
            ),
        }
        for header, message in cases.items():
            with self.subTest(header=header):
                self.assertEqual(self._error(header), message)


class ConversionRuleTests(unittest.TestCase):
    def test_development_guide_requires_loss_reports_from_writers(self) -> None:
        guide = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
        self.assertIn("## Rules for writers", guide)
        self.assertRegex(" ".join(guide.split()), r"report.*every field.*not written")

    def test_reader_reference_states_resource_use(self) -> None:
        reference = (ROOT / "docs" / "GENEMAPPER.md").read_text(encoding="utf-8")
        self.assertIn("## Resources", reference)
        self.assertTrue(re.search(r"about \d+ times the file size", reference))


if __name__ == "__main__":
    unittest.main()
