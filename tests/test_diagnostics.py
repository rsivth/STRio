"""New in 0.1.0: findings carry stable codes and source lines besides their text."""

from __future__ import annotations

import unittest

from _support import EXPORTS

import strio
from strio import Diagnostic, DiagnosticCode


class DiagnosticCodeTests(unittest.TestCase):
    def test_trailing_empty_columns(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tHeight 1\t\t\nS\tTPOX\t8\t100\t\t\n"
        )
        (item,) = dataset.diagnostics
        self.assertIs(item.code, DiagnosticCode.TRAILING_EMPTY_COLUMNS)
        self.assertEqual(item.message, "Ignored 2 empty unnamed trailing column(s).")
        self.assertEqual(item.lines, ())

    def test_allele_display_overflow_names_its_lines(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tADO\tAllele 1\tHeight 1\n"
            "S\tTPOX\t0\t8\t100\nS\tTH01\tTrue\t9\t100\nS\tFGA\tyes\t20\t100\n"
        )
        (item,) = dataset.diagnostics
        self.assertIs(item.code, DiagnosticCode.ALLELE_DISPLAY_OVERFLOW)
        self.assertEqual(item.lines, (3, 4))
        self.assertIn("line(s) 3, 4;", item.message)

    def test_overflow_preview_is_shortened_after_five_lines(self) -> None:
        rows = "".join(f"S\tM{i}\t1\t8\t100\n" for i in range(7))
        dataset = strio.parse_genemapper("Sample Name\tMarker\tADO\tAllele 1\tHeight 1\n" + rows)
        (item,) = dataset.diagnostics
        self.assertIn("line(s) 2, 3, 4, 5, 6...;", item.message)
        self.assertEqual(len(item.lines), 7)

    def test_highest_allele_column_used(self) -> None:
        dataset = strio.read_genemapper(EXPORTS / "essplex_se_qs_mixed_export.txt")
        codes = [item.code for item in dataset.diagnostics]
        self.assertEqual(
            codes,
            [DiagnosticCode.TRAILING_EMPTY_COLUMNS, DiagnosticCode.HIGHEST_ALLELE_COLUMN_USED],
        )
        self.assertTrue(dataset.diagnostics[1].lines)

    def test_highest_column_is_not_reported_below_ten_allele_columns(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tAllele 2\tHeight 1\tHeight 2\nS\tTPOX\t8\t9\t1\t1\n"
        )
        self.assertEqual(dataset.diagnostics, ())

    def test_overflow_takes_precedence_over_highest_column(self) -> None:
        header = "\t".join(["Sample Name", "Marker", "ADO"] + [f"Allele {i}" for i in range(1, 11)])
        row = "\t".join(["S", "TPOX", "1"] + [str(i) for i in range(1, 11)])
        dataset = strio.parse_genemapper(header + "\n" + row + "\n", require_height=False)
        self.assertEqual(
            [item.code for item in dataset.diagnostics], [DiagnosticCode.ALLELE_DISPLAY_OVERFLOW]
        )


class DiagnosticObjectTests(unittest.TestCase):
    def test_str_is_the_message(self) -> None:
        item = Diagnostic(DiagnosticCode.TRAILING_EMPTY_COLUMNS, " text ")
        self.assertEqual(str(item), "text")

    def test_codes_have_stable_string_values(self) -> None:
        self.assertEqual(
            {code.value for code in DiagnosticCode},
            {"trailing-empty-columns", "allele-display-overflow", "highest-allele-column-used"},
        )

    def test_invalid_diagnostics_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            Diagnostic("trailing-empty-columns", "x")  # type: ignore[arg-type]
        for factory in (
            lambda: Diagnostic(DiagnosticCode.TRAILING_EMPTY_COLUMNS, "  "),
            lambda: Diagnostic(DiagnosticCode.TRAILING_EMPTY_COLUMNS, "x", (0,)),
            lambda: Diagnostic(DiagnosticCode.TRAILING_EMPTY_COLUMNS, "x", (True,)),
        ):
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()

    def test_dataset_messages_follow_diagnostic_order(self) -> None:
        dataset = strio.read_genemapper(EXPORTS / "essplex_se_qs_mixed_export.txt")
        self.assertEqual(dataset.messages, tuple(str(item) for item in dataset.diagnostics))


if __name__ == "__main__":
    unittest.main()
