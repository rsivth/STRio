"""New in 0.1.2: findings of the external code review of 0.1.1 (2026-10-15).

Each class covers one finding; docs/TEST_PROVENANCE.md, section 0.1.2, lists them.
"""

from __future__ import annotations

import re
import unittest

from _support import ROOT

import strio
from strio import AlleleKind, DuplicateColumnError, MissingColumnError, NumericValueError
from strio.formats import _table
from strio.formats.genemapper import MAX_INTEGER_DIGITS

HEADER = "Sample Name\tMarker\tAllele 1\tHeight 1"


def _parse(header_suffix: str, values: str, **options: object) -> strio.Dataset:
    text = f"{HEADER}{header_suffix}\nS\tvWA\t14\t{values}\n"
    return strio.parse_genemapper(text, **options)  # type: ignore[arg-type]


class SpacingDuplicateHeaderTests(unittest.TestCase):
    def test_names_differing_only_in_spacing_are_rejected(self) -> None:
        for second in ("Sample  Name", "sample  name", " Sample Name"):
            text = f"Sample Name\t{second}\tMarker\tAllele 1\tHeight 1\nA\tB\tvWA\t14\t1\n"
            with (
                self.subTest(second=second),
                self.assertRaisesRegex(DuplicateColumnError, "differ only in spacing"),
            ):
                strio.parse_genemapper(text)

    def test_spacing_duplicates_among_extra_columns_are_rejected(self) -> None:
        with self.assertRaisesRegex(DuplicateColumnError, "'Run  Date'"):
            _parse("\tRun Date\tRun  Date", "1\tx\ty")

    def test_indexed_duplicates_keep_their_specific_message(self) -> None:
        with self.assertRaisesRegex(DuplicateColumnError, "semantic indexed column"):
            _parse("\tHeight  1", "1\t1")


class LongIntegerTests(unittest.TestCase):
    def test_pathologically_long_values_raise_numeric_errors(self) -> None:
        huge = "9" * 5000
        for suffix, values in (("\tArea 1", f"1\t{huge}"), ("", huge)):
            with self.subTest(suffix=suffix), self.assertRaises(NumericValueError) as caught:
                _parse(suffix, values)
            message = str(caught.exception)
            self.assertIn(f"more than {MAX_INTEGER_DIGITS} digits", message)
            self.assertIn("(5000 characters)", message)
            self.assertLess(len(message), 200)

    def test_digit_limit_is_eighteen_ignoring_sign_and_leading_zeros(self) -> None:
        accepted = _parse("\tArea 1", "1\t" + "1" * 18).sample("S").loci["vWA"].alleles[0]
        self.assertEqual(accepted.area, int("1" * 18))
        padded = _parse("\tArea 1", "1\t+" + "0" * 30 + "7").sample("S").loci["vWA"].alleles[0]
        self.assertEqual(padded.area, 7)
        with self.assertRaisesRegex(NumericValueError, "more than 18 digits"):
            _parse("\tArea 1", "1\t" + "1" * 19)

    def test_long_whole_part_of_a_size_is_rejected(self) -> None:
        with self.assertRaisesRegex(NumericValueError, "Size value .* more than 18 digits"):
            _parse("\tSize 1", "1\t" + "1" * 19 + ".5")

    def test_height_ceiling_message_still_wins_for_long_heights(self) -> None:
        with self.assertRaisesRegex(NumericValueError, "maximum of 32,767 RFU"):
            _parse("", "9" * 5000, max_height=32_767)

    def test_long_column_numbers_are_rejected(self) -> None:
        with self.assertRaisesRegex(strio.ParseError, "Allele 1234567.*more than 6 digits"):
            _parse("\tAllele 1234567", "1\t")


class SourceColumnNameTests(unittest.TestCase):
    def test_messages_name_the_exported_column(self) -> None:
        cases = (
            ("Sample Name\tMarker\tAllele 1\tHeight 1\tPeak Area 1", "1\tx", "'Peak Area 1'"),
            ("Sample Name\tMarker\tallele 1\theight 1", "x", "'height 1'"),
            ("Sample Name\tMarker\tAllele 1\tHeight 1\tSIZE 1", "1\tx", "'SIZE 1'"),
        )
        for header, values, column in cases:
            with (
                self.subTest(column=column),
                self.assertRaisesRegex(NumericValueError, re.escape(column)),
            ):
                strio.parse_genemapper(f"{header}\nS\tvWA\t14\t{values}\n")


class AsciiDigitTests(unittest.TestCase):
    def test_digits_of_other_scripts_are_not_numbers(self) -> None:
        cases = (
            ("", "١٢٣"),  # Arabic-Indic height
            ("\tArea 1", "1\t१२"),  # Devanagari area
            ("\tSize 1", "1\t１６０"),  # full-width size
        )
        for suffix, values in cases:
            with self.subTest(values=values), self.assertRaises(NumericValueError):
                _parse(suffix, values)

    def test_allele_labels_with_other_digits_are_other(self) -> None:
        for label in ("٩.٣", "１５"):
            with self.subTest(label=label):
                self.assertIs(strio.parse_allele_label(label).kind, AlleleKind.OTHER)

    def test_column_numbers_must_be_ascii(self) -> None:
        with self.assertRaises(MissingColumnError):
            strio.parse_genemapper("Sample Name\tMarker\tAllele ١\tHeight 1\nS\tvWA\t14\t1\n")

    def test_sizes_are_plain_decimals(self) -> None:
        accepted = {"160": "160", "+160.5": "160.5", "160,5": "160.5", ".5": "0.5", "160.": "160"}
        for raw, expected in accepted.items():
            with self.subTest(raw=raw):
                text = f'Sample Name,Marker,Allele 1,Height 1,Size 1\nS,vWA,14,1,"{raw}"\n'
                size = strio.parse_genemapper(text).sample("S").loci["vWA"].alleles[0].size_bp
                self.assertEqual(str(size), expected)
        for raw in ("1e2", "Infinity", "NaN", "1_000", "-1", "1.2.3"):
            with self.subTest(raw=raw), self.assertRaises(NumericValueError):
                _parse("\tSize 1", f"1\t{raw}")


class EncodingListTests(unittest.TestCase):
    def test_utf8_is_tried_once_through_utf8_sig(self) -> None:
        self.assertEqual(_table.DEFAULT_ENCODINGS, ("utf-8-sig", "cp1252", "latin-1"))


class DocumentationAndLintTests(unittest.TestCase):
    def test_release_instructions_name_the_runner_verdict(self) -> None:
        development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
        self.assertIn("`Result: PASSED`", development)
        self.assertNotIn("BESTANDEN", development)

    def test_ruff_limits_cyclomatic_complexity(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('    "C90",\n', pyproject)
        self.assertIn("[tool.ruff.lint.mccabe]\nmax-complexity = 12\n", pyproject)


if __name__ == "__main__":
    unittest.main()
