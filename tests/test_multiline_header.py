"""New in 0.2.2: delimiter detection reads the first record, not the first physical line.

Finding of the third external review (of 0.2.1, 2026-10-15). EPG-Renderer 0.15.1 failed
in the same way; docs/TEST_PROVENANCE.md, section 0.2.2, records the changed behaviour.
"""

from __future__ import annotations

import unittest

from _support import FIXTURES

import strio
from strio.formats import _table

HEADER = ("Sample Name", "Marker", "Allele 1", "Height 1", '"Long\nNote"')


def _export(delimiter: str, line_end: str = "\n") -> str:
    header = delimiter.join(HEADER).replace("\n", line_end)
    row = delimiter.join(("S", "vWA", "14", "100", "ok"))
    return f"{header}{line_end}{row}{line_end}"


class MultiLineHeaderTests(unittest.TestCase):
    def test_detection_reads_a_header_with_a_line_break_in_a_quoted_name(self) -> None:
        for delimiter in strio.formats.genemapper.SUPPORTED_DELIMITERS:
            for line_end in ("\n", "\r\n"):
                text = _export(delimiter, line_end)
                with self.subTest(delimiter=delimiter, line_end=line_end):
                    detected = strio.parse_genemapper(text)
                    explicit = strio.parse_genemapper(text, delimiter=delimiter)
                    self.assertEqual(detected, explicit)
                    table = detected.source.require_table()
                    self.assertEqual(table.delimiter, delimiter)
                    self.assertEqual(table.extra_columns, (f"Long{line_end}Note",))
                    locus = detected.sample("S").loci["vWA"]
                    self.assertEqual(locus.extra, {f"Long{line_end}Note": "ok"})

    def test_rows_after_a_two_line_header_keep_their_physical_line_numbers(self) -> None:
        text = _export(",").replace(",100,", ",1x,")
        with self.assertRaisesRegex(strio.NumericValueError, "at line 3"):
            strio.parse_genemapper(text)
        dataset = strio.parse_genemapper(_export(","))
        self.assertEqual(dataset.sample("S").loci["vWA"].line, 3)

    def test_a_header_quote_that_never_closes_is_still_rejected(self) -> None:
        text = 'Sample Name,Marker,Allele 1,Height 1,"Note\nS,vWA,14,100,ok\n'
        with self.assertRaises(strio.ParseError):
            strio.parse_genemapper(text)
        with self.assertRaisesRegex(strio.ParseError, "CSV syntax"):
            strio.parse_genemapper(text, delimiter=",")

    def test_first_record_fields_follows_the_csv_rules(self) -> None:
        self.assertEqual(_table.first_record_fields('A,"B\nC",D\nx,y,z\n', ","), ["A", "B\nC", "D"])
        self.assertEqual(_table.first_record_fields("A;B\r\nC;D", ";"), ["A", "B"])
        self.assertEqual(_table.first_record_fields("", ","), [])
        self.assertIsNone(_table.first_record_fields('A,"B\nC\n', ","))

    def test_detection_agrees_with_the_explicit_delimiter_on_every_fixture(self) -> None:
        for path in sorted(FIXTURES.rglob("*.t*")):
            with self.subTest(fixture=path.name):
                detected = strio.read_genemapper(path)
                table = detected.source.require_table()
                self.assertEqual(detected, strio.read_genemapper(path, delimiter=table.delimiter))


if __name__ == "__main__":
    unittest.main()
