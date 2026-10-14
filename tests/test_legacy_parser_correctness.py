"""Legacy suite: ported from EPG-Renderer 0.15.1 ``tests/test_schema_and_parser_correctness.py``.

Only the class ``ParserCorrectnessTests`` concerns the parser; the kit-schema classes of
that module stay in EPG-Renderer. Inputs and assertions are unchanged.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import strio
from strio import DuplicateColumnError, ParseError


def _write(directory: str, name: str, content: str) -> Path:
    path = Path(directory) / name
    path.write_text(content, encoding="utf-8", newline="")
    return path


class LegacyParserCorrectnessTests(unittest.TestCase):
    def test_quoted_multiline_field_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(
                directory,
                "multiline.csv",
                'Sample Name,Marker,Dye,Allele 1,Height 1\r\n"S1\r\ncontinued",D3S1358,B,15,100\r\n',
            )
            dataset = strio.read_genemapper(path, delimiter=",")
        self.assertEqual(tuple(dataset.samples), ("S1\r\ncontinued",))

    def test_semantically_duplicate_indexed_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(
                directory,
                "duplicates.tsv",
                "Sample Name\tMarker\tDye\tAllele 1\tAllele  1\tHeight 1\n"
                "S1\tD3S1358\tB\t15\t16\t100\n",
            )
            with self.assertRaisesRegex(
                DuplicateColumnError, "semantic indexed column.*Allele 1.*Allele  1"
            ):
                strio.read_genemapper(path, delimiter="\t")

    def test_valid_escaped_quote_blank_row_and_quoted_final_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(
                directory,
                "quoted.csv",
                'Sample Name,Marker,Dye,Allele 1,Height 1\r\n\r\n"S""1",D3S1358,B,15,"100"\r\n',
            )
            dataset = strio.read_genemapper(path, delimiter=",")
        self.assertEqual(tuple(dataset.samples), ('S"1',))

    def test_csv_reader_errors_are_wrapped_with_line_number(self):
        previous_limit = csv.field_size_limit()
        try:
            csv.field_size_limit(8)
            with tempfile.TemporaryDirectory() as directory:
                path = _write(
                    directory,
                    "oversized.csv",
                    "Sample Name,Marker,Dye,Allele 1,Height 1\nS1,D3S1358,B,15,100\n",
                )
                with self.assertRaisesRegex(ParseError, "Invalid CSV syntax.*line 1"):
                    strio.read_genemapper(path, delimiter=",")
        finally:
            csv.field_size_limit(previous_limit)

    def test_explicit_utf8_bom_only_header_is_rejected_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bom.csv"
            path.write_bytes(b"\xef\xbb\xbf")
            with self.assertRaisesRegex(ParseError, "Header row is empty"):
                strio.read_genemapper(path, delimiter=",", encoding="utf-8")

    def test_unknown_encoding_name_is_wrapped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "input.tsv", "content")
            with self.assertRaisesRegex(ParseError, "Unknown text encoding.*not-a-codec"):
                strio.read_genemapper(path, encoding="not-a-codec")

    def test_unclosed_quoted_field_is_reported_as_csv_syntax_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(
                directory,
                "broken.csv",
                'Sample Name,Marker,Dye,Allele 1,Height 1\n"S1,D3S1358,B,15,100\n',
            )
            with self.assertRaisesRegex(ParseError, "Invalid CSV syntax.*line 2"):
                strio.read_genemapper(path, delimiter=",")

    def test_quote_inside_unquoted_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(
                directory,
                "stray-quote.csv",
                'Sample Name,Marker,Dye,Allele 1,Height 1\nS"1,D3S1358,B,15,100\n',
            )
            with self.assertRaisesRegex(ParseError, "Invalid CSV syntax.*line 2"):
                strio.read_genemapper(path, delimiter=",")


if __name__ == "__main__":
    unittest.main()
