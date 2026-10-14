"""New in 0.1.0: reader entry points, options, encodings and provenance."""

from __future__ import annotations

import codecs
import tempfile
import unittest
from pathlib import Path

from _support import FIXTURES, write_bytes, write_temp

import strio
from strio import NumericValueError, ParseError

SIMPLE = "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTH01\tFAM\t9.3\t100\n"


class EntryPointTests(unittest.TestCase):
    def test_parse_text_equals_read_file(self) -> None:
        path = FIXTURES / "globalfiler_minimal.tsv"
        from_file = strio.read_genemapper(path)
        from_text = strio.parse_genemapper(path.read_text(encoding="utf-8"))
        self.assertEqual(from_file.samples, from_text.samples)
        self.assertEqual(from_file.diagnostics, from_text.diagnostics)
        self.assertEqual(from_file.source.header, from_text.source.header)

    def test_source_information(self) -> None:
        path = write_temp(self, SIMPLE)
        dataset = strio.read_genemapper(path)
        self.assertEqual(dataset.source.format, "genemapper-table")
        self.assertEqual(dataset.source.path, path)
        self.assertEqual(dataset.source.encoding, "utf-8-sig")
        self.assertEqual(dataset.source.sample_id_column, "Sample Name")
        text_dataset = strio.parse_genemapper(SIMPLE)
        self.assertIsNone(text_dataset.source.path)
        self.assertIsNone(text_dataset.source.encoding)

    def test_text_source_name_appears_in_errors(self) -> None:
        with self.assertRaisesRegex(ParseError, "clipboard.*line 2"):
            strio.parse_genemapper(
                'Sample Name,Marker,Allele 1,Height 1\nS"1,TPOX,8,100\n', source="clipboard"
            )

    def test_accepts_str_paths(self) -> None:
        path = write_temp(self, SIMPLE)
        self.assertEqual(strio.read_genemapper(str(path)).sample_ids, ("S",))

    def test_missing_file_and_directory_are_parse_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ParseError, "does not exist"):
                strio.read_genemapper(Path(directory) / "missing.txt")
            with self.assertRaisesRegex(ParseError, "does not exist"):
                strio.read_genemapper(directory)

    def test_unsupported_explicit_delimiter_is_rejected(self) -> None:
        with self.assertRaisesRegex(ParseError, "Unsupported delimiter"):
            strio.parse_genemapper(SIMPLE.replace("\t", "|"), delimiter="|")

    def test_undetectable_delimiter_is_rejected(self) -> None:
        with self.assertRaisesRegex(ParseError, "Could not detect CSV delimiter"):
            strio.parse_genemapper("Sample Name|Marker|Allele 1\nS|TPOX|8\n")

    def test_all_errors_are_value_errors(self) -> None:
        with self.assertRaises(ValueError):
            strio.parse_genemapper("")

    def test_header_without_rows_is_rejected(self) -> None:
        with self.assertRaisesRegex(ParseError, "No sample rows"):
            strio.parse_genemapper("Sample Name\tMarker\tAllele 1\tHeight 1\n")


class HeightOptionTests(unittest.TestCase):
    def test_no_ceiling_by_default(self) -> None:
        dataset = strio.parse_genemapper(SIMPLE.replace("\t100\n", "\t65000\n"))
        self.assertEqual(dataset.sample("S").loci["TH01"].alleles[0].height, 65000)

    def test_custom_ceiling_is_inclusive(self) -> None:
        dataset = strio.parse_genemapper(SIMPLE, max_height=100)
        self.assertEqual(dataset.sample("S").loci["TH01"].alleles[0].height, 100)
        with self.assertRaisesRegex(NumericValueError, "maximum of 99 RFU"):
            strio.parse_genemapper(SIMPLE, max_height=99)

    def test_leading_zeros_do_not_trip_the_ceiling(self) -> None:
        dataset = strio.parse_genemapper(SIMPLE.replace("\t100\n", "\t000100\n"), max_height=100)
        self.assertEqual(dataset.sample("S").loci["TH01"].alleles[0].height, 100)

    def test_invalid_ceiling_is_a_programming_error(self) -> None:
        for value in (-1, True, 1.5, "100"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                strio.parse_genemapper(SIMPLE, max_height=value)  # type: ignore[arg-type]

    def test_heights_are_optional_on_request(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\nS\tTH01\t9.3\n", require_height=False
        )
        allele = dataset.sample("S").loci["TH01"].alleles[0]
        self.assertIsNone(allele.height)
        self.assertIsNone(allele.size_bp)
        self.assertIsNone(allele.area)

    def test_decimal_comma_in_size(self) -> None:
        dataset = strio.parse_genemapper(
            'Sample Name,Marker,Allele 1,Height 1,Size 1\nS,TH01,9.3,100,"160,5"\n'
        )
        self.assertEqual(str(dataset.sample("S").loci["TH01"].alleles[0].size_bp), "160.5")

    def test_invalid_sizes_and_areas(self) -> None:
        header = "Sample Name\tMarker\tAllele 1\tHeight 1\tSize 1\tArea 1\n"
        for row, pattern in (
            ("S\tTH01\t9\t1\tabc\t1\n", "Invalid decimal size"),
            ("S\tTH01\t9\t1\t-1\t1\n", "Invalid decimal size"),
            ("S\tTH01\t9\t1\tInfinity\t1\n", "Invalid decimal size"),
            ("S\tTH01\t9\t1\t100\t1.5\n", "Invalid integer area"),
        ):
            with self.subTest(row=row), self.assertRaisesRegex(NumericValueError, pattern):
                strio.parse_genemapper(header + row)


class EncodingTests(unittest.TestCase):
    def test_utf16_with_byte_order_mark_is_read(self) -> None:
        for bom, codec in ((codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be")):
            with self.subTest(codec=codec):
                path = write_bytes(
                    self,
                    bom
                    + "Sample Name\tMarker\tAllele 1\tHeight 1\nPröbe\tTH01\t9.3\t100\n".encode(
                        codec
                    ),
                )
                dataset = strio.read_genemapper(path)
                self.assertEqual(dataset.sample_ids, ("Pröbe",))
                self.assertEqual(dataset.source.encoding, "utf-16")

    def test_utf16_without_byte_order_mark_gets_a_clear_message(self) -> None:
        path = write_bytes(self, SIMPLE.encode("utf-16-le"))
        with self.assertRaisesRegex(ParseError, "NUL character.*UTF-16.*encoding='utf-16-le'"):
            strio.read_genemapper(path)
        dataset = strio.read_genemapper(path, encoding="utf-16-le")
        self.assertEqual(dataset.sample_ids, ("S",))

    def test_explicit_encoding_that_cannot_decode_is_reported(self) -> None:
        path = write_temp(self, SIMPLE.replace("S\t", "Pröbe\t"), encoding="cp1252")
        with self.assertRaisesRegex(ParseError, "Could not decode"):
            strio.read_genemapper(path, encoding="utf-8")

    def test_unreadable_path_is_a_parse_error(self) -> None:
        path = write_temp(self, SIMPLE)
        path.chmod(0)
        self.addCleanup(path.chmod, 0o600)
        try:
            path.read_bytes()
        except PermissionError:
            with self.assertRaisesRegex(ParseError, "Could not read"):
                strio.read_genemapper(path)
        else:
            self.skipTest("running with privileges that ignore file permissions")


if __name__ == "__main__":
    unittest.main()
