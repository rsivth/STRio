"""Legacy suite: ported from EPG-Renderer 0.15.1 ``tests/test_parser.py``.

Every test keeps the input and the assertion of its original. Only the API is
translated: ``load_project`` -> ``strio.read_genemapper``, ``project.sample(...)
.markers[...]`` -> ``dataset.sample(...).loci[...]``, ``allele`` -> ``label``,
``allele_index`` -> ``index``, ``warnings`` -> ``messages`` and the renderer exception
names -> STRio exception names (see docs/TEST_PROVENANCE.md).
"""

from __future__ import annotations

import unittest

from _support import FIXTURES, write_temp

import strio
from strio import (
    DuplicateColumnError,
    DuplicateLocusError,
    MissingColumnError,
    NumericValueError,
    ParseError,
)


def load(path, **options):
    return strio.read_genemapper(path, **options)


class LegacyParserTests(unittest.TestCase):
    def _write(self, text: str, *, encoding: str = "utf-8"):
        return write_temp(self, text, encoding=encoding)

    def test_parses_globalfiler_tsv_and_preserves_order(self):
        dataset = load(FIXTURES / "globalfiler_minimal.tsv")
        self.assertEqual(dataset.sample_ids, ("S1",))
        sample = dataset.sample("S1")
        self.assertEqual(next(iter(sample.loci)), "D3S1358")
        self.assertEqual(tuple(sample.loci)[-1], "D2S1338")
        self.assertEqual(sample.loci["TH01"].alleles[1].label, "9.3")
        self.assertEqual(sample.loci["TH01"].alleles[1].height, 750)

    def test_detects_comma_delimiter(self):
        path = self._write("Sample Name,Marker,Dye,Allele 1,Height 1\nS,D3S1358,FAM,15,100\n")
        self.assertEqual(load(path).source.require_table().delimiter, ",")

    def test_detects_semicolon_delimiter(self):
        path = self._write("Sample Name;Marker;Dye;Allele 1;Height 1\nS;D3S1358;FAM;15;100\n")
        self.assertEqual(load(path).source.require_table().delimiter, ";")

    def test_reads_utf8_bom(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tD3S1358\tFAM\t15\t100\n",
            encoding="utf-8-sig",
        )
        self.assertEqual(load(path).sample_ids, ("S",))

    def test_reads_cp1252(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nPröbe\tD3S1358\tFAM\t15\t100\n",
            encoding="cp1252",
        )
        self.assertEqual(load(path).sample_ids, ("Pröbe",))

    def test_multiple_samples(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\n"
            "S1\tD3S1358\tFAM\t15\t100\nS2\tD3S1358\tFAM\t16\t200\n"
        )
        self.assertEqual(load(path).sample_ids, ("S1", "S2"))

    def test_supports_more_than_two_called_alleles(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\tAllele 2\tHeight 2\tAllele 3\t"
            "Height 3\nS\tD3S1358\tFAM\t15\t100\t16\t90\t17\t80\n"
        )
        locus = load(path).sample("S").loci["D3S1358"]
        self.assertEqual([allele.label for allele in locus.alleles], ["15", "16", "17"])

    def test_empty_allele_and_height_pair_is_ignored(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\tAllele 2\tHeight 2\n"
            "S\tTPOX\tFAM\t8\t100\t\t\n"
        )
        self.assertEqual(len(load(path).sample("S").loci["TPOX"].alleles), 1)

    def test_rejects_height_without_allele(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTPOX\tFAM\t\t100\n")
        with self.assertRaises(ParseError):
            load(path)

    def test_rejects_allele_without_height_by_default(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTPOX\tFAM\t8\t\n")
        with self.assertRaises(ParseError):
            load(path)

    def test_rejects_noninteger_height(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTPOX\tFAM\t8\t100.5\n")
        with self.assertRaises(NumericValueError):
            load(path)

    def test_rejects_negative_height(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTPOX\tFAM\t8\t-1\n")
        with self.assertRaises(NumericValueError):
            load(path)

    def test_accepts_missing_dye_column_as_absent_evidence(self):
        path = self._write("Sample Name\tMarker\tAllele 1\tHeight 1\nS\tTPOX\t8\t100\n")
        self.assertIsNone(load(path).sample("S").loci["TPOX"].dye)

    def test_rejects_missing_allele_columns(self):
        path = self._write("Sample Name\tMarker\tDye\tHeight 1\nS\tTPOX\tFAM\t100\n")
        with self.assertRaises(MissingColumnError):
            load(path)

    def test_rejects_duplicate_headers_case_insensitively(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tallele 1\tHeight 1\nS\tTPOX\tFAM\t8\t8\t100\n"
        )
        with self.assertRaises(DuplicateColumnError):
            load(path)

    def test_rejects_duplicate_marker_within_sample(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\n"
            "S\tTPOX\tFAM\t8\t100\nS\tTPOX\tFAM\t9\t90\n"
        )
        with self.assertRaises(DuplicateLocusError):
            load(path)

    def test_rejects_empty_sample_identifier(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\n\tTPOX\tFAM\t8\t100\n")
        with self.assertRaises(ParseError):
            load(path)

    def test_rejects_empty_marker(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\t\tFAM\t8\t100\n")
        with self.assertRaises(ParseError):
            load(path)

    def test_accepts_empty_dye_as_absent_evidence(self):
        path = self._write("Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTPOX\t\t8\t100\n")
        self.assertIsNone(load(path).sample("S").loci["TPOX"].dye)

    def test_ignores_only_empty_trailing_unnamed_columns(self):
        path = self._write("Sample Name\tMarker\tAllele 1\tHeight 1\t\nS\tTPOX\t8\t100\t\n")
        dataset = load(path)
        self.assertEqual(
            dataset.source.require_table().header, ("Sample Name", "Marker", "Allele 1", "Height 1")
        )
        self.assertIn("Ignored 1 empty unnamed trailing column", dataset.messages[0])

    def test_rejects_data_in_unnamed_trailing_column(self):
        path = self._write("Sample Name\tMarker\tAllele 1\tHeight 1\t\nS\tTPOX\t8\t100\textra\n")
        with self.assertRaisesRegex(ParseError, "Unnamed trailing column contains data"):
            load(path)

    def test_rejects_unnamed_interior_column(self):
        path = self._write("Sample Name\tMarker\t\tAllele 1\tHeight 1\nS\tTPOX\t\t8\t100\n")
        with self.assertRaisesRegex(ParseError, "Blank column names"):
            load(path)

    def test_preserves_sparse_indexes_and_optional_peak_families(self):
        path = self._write(
            "Sample Name\tMarker\tAllele 1\tAllele 3\tHeight 1\tHeight 3\t"
            "Size 1\tSize 3\tArea 1\tArea 3\tMutation 3\tComment 3\n"
            "S\tTPOX\t8\t10\t100\t80\t347.2\t355.2\t4000\t3200\tM\tcheck\n"
        )
        alleles = load(path).sample("S").loci["TPOX"].alleles
        self.assertEqual(tuple(allele.index for allele in alleles), (1, 3))
        self.assertEqual(str(alleles[0].size_bp), "347.2")
        self.assertEqual(alleles[1].area, 3200)
        self.assertEqual(alleles[1].mutation, "M")
        self.assertEqual(alleles[1].comment, "check")

    def test_allele_display_overflow_produces_explicit_warning(self):
        path = self._write(
            "Sample Name\tMarker\tAllele Display Overflow\tAllele 1\tHeight 1\nS\tTPOX\t1\t8\t100\n"
        )
        self.assertIn("allele-display overflow", load(path).messages[0])

    def test_rejects_nonempty_extra_field(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS\tTPOX\tFAM\t8\t100\textra\n"
        )
        with self.assertRaises(ParseError):
            load(path)

    def test_ignores_blank_rows(self):
        path = self._write(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\n\nS\tTPOX\tFAM\t8\t100\n\n"
        )
        self.assertEqual(load(path).sample_ids, ("S",))

    def test_rejects_empty_file(self):
        with self.assertRaises(ParseError):
            load(self._write(""))

    def test_custom_sample_id_column(self):
        path = self._write("Sample ID\tMarker\tDye\tAllele 1\tHeight 1\nID-1\tTPOX\tFAM\t8\t100\n")
        self.assertEqual(load(path, sample_id_column="Sample ID").sample_ids, ("ID-1",))


if __name__ == "__main__":
    unittest.main()
