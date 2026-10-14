"""New in 0.1.0: cases where the Go package *forge* misreads exports.

A differential comparison against forge's ``ReadGenemapper`` found these inputs on
2026-10-14 (see docs/TEST_PROVENANCE.md). strio must keep handling each one correctly.
"""

from __future__ import annotations

import unittest

import strio
from strio import DuplicateLocusError


class ForgeRegressionTests(unittest.TestCase):
    def test_allele_display_overflow_column_is_not_an_allele_column(self) -> None:
        # forge counts every header starting with "Allele " and indexes past the row.
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tAllele 2\tAllele Display Overflow\tHeight 1\tHeight 2\n"
            "S1\tvWA\t14\t16\tfalse\t1100\t970\n"
        )
        locus = dataset.sample("S1").loci["vWA"]
        self.assertEqual([(a.label, a.height) for a in locus.alleles], [("14", 1100), ("16", 970)])

    def test_missing_height_column_is_paired_by_name_not_position(self) -> None:
        # forge computes column positions from the first offset and reads past the row.
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tAllele 2\tAllele 3\tHeight 1\tHeight 3\n"
            "S1\tvWA\t14\t16\t17\t1100\t500\n",
            require_height=False,
        )
        alleles = dataset.sample("S1").loci["vWA"].alleles
        self.assertEqual(
            [(a.label, a.height) for a in alleles], [("14", 1100), ("16", None), ("17", 500)]
        )

    def test_dye_belongs_to_each_marker_row(self) -> None:
        # forge stores Dye once per sample, taken from the sample's first row.
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\nS1\tvWA\tB\t14\t1100\nS1\tTH01\tG\t9.3\t800\n"
        )
        sample = dataset.sample("S1")
        self.assertEqual((sample.loci["vWA"].dye, sample.loci["TH01"].dye), ("B", "G"))

    def test_two_injections_with_one_sample_name_stay_separate(self) -> None:
        # forge merges them by name and silently drops the second injection's loci.
        dataset = strio.parse_genemapper(
            "Sample Name\tSample File\tMarker\tAllele 1\tHeight 1\n"
            "S1\tA01.hid\tvWA\t14\t1100\nS1\tB01.hid\tvWA\t17\t500\n"
        )
        self.assertEqual(dataset.sample_ids, ("S1 [A01.hid]", "S1 [B01.hid]"))
        self.assertEqual(dataset.sample("S1 [B01.hid]").loci["vWA"].labels, ("17",))

    def test_empty_marker_row_followed_by_same_marker_is_a_duplicate(self) -> None:
        # forge appends the locus twice when the first row has no alleles.
        with self.assertRaises(DuplicateLocusError):
            strio.parse_genemapper(
                "Sample Name\tMarker\tAllele 1\tHeight 1\nS1\tvWA\t\t\nS1\tvWA\t14\t1100\n"
            )

    def test_off_ladder_label_text_is_kept(self) -> None:
        # forge turns "OL" into NaN and loses the exported text.
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tAllele 2\tHeight 1\tHeight 2\nS1\tvWA\tOL\t14\t300\t1100\n"
        )
        self.assertEqual(dataset.sample("S1").loci["vWA"].labels, ("OL", "14"))

    def test_samples_keep_source_order(self) -> None:
        # forge returns samples in Go map order, which is unspecified.
        rows = "".join(f"{name}\tvWA\t14\t1\n" for name in "DCBAEFGHIJ")
        dataset = strio.parse_genemapper("Sample Name\tMarker\tAllele 1\tHeight 1\n" + rows)
        self.assertEqual(dataset.sample_ids, tuple("DCBAEFGHIJ"))

    def test_missing_heights_stay_none_instead_of_zero(self) -> None:
        # forge stores absent measurements as 0, indistinguishable from a measured 0.
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tHeight 1\tSize 1\nS1\tvWA\t14\t0\t\n"
        )
        allele = dataset.sample("S1").loci["vWA"].alleles[0]
        self.assertEqual(allele.height, 0)
        self.assertIsNone(allele.size_bp)


if __name__ == "__main__":
    unittest.main()
