"""New in 0.1.0: reader branches that the legacy suite does not reach."""

from __future__ import annotations

import unittest

import strio
from strio import DuplicateColumnError, MissingColumnError, ParseError


class SampleIdentityEdgeTests(unittest.TestCase):
    def test_conflicting_identity_within_one_selected_sample_is_rejected(self) -> None:
        with self.assertRaisesRegex(ParseError, "Inconsistent sample metadata at line 3"):
            strio.parse_genemapper(
                "Sample ID\tSample File\tMarker\tAllele 1\tHeight 1\n"
                "ID1\tA.hid\tvWA\t14\t1\nID1\tB.hid\tTH01\t9\t1\n",
                sample_id_column="Sample ID",
            )

    def test_duplicate_display_names_fall_back_to_sample_id(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tSample ID\tMarker\tAllele 1\tHeight 1\nS\tid-1\tvWA\t14\t1\nS\tid-2\tvWA\t15\t1\n"
        )
        self.assertEqual(dataset.sample_ids, ("S [id-1]", "S [id-2]"))

    def test_duplicate_display_names_fall_back_to_run_name(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tRun Name\tMarker\tAllele 1\tHeight 1\nS\tR1\tvWA\t14\t1\nS\tR2\tvWA\t15\t1\n"
        )
        self.assertEqual(dataset.sample_ids, ("S [R1]", "S [R2]"))

    def test_indistinguishable_duplicates_are_numbered(self) -> None:
        dataset = strio.parse_genemapper(
            "Lane\tSample Name\tMarker\tAllele 1\tHeight 1\n"
            "1\tS\tvWA\t14\t1\n2\tS\tvWA\t15\t1\n3\tS\tvWA\t16\t1\n",
            sample_id_column="Lane",
        )
        self.assertEqual(
            dataset.sample_ids, ("S [duplicate]", "S [duplicate] #2", "S [duplicate] #3")
        )
        self.assertEqual({s.display_name for s in dataset.samples.values()}, {"S"})

    def test_selected_sample_column_is_used_as_display_name_without_sample_name(self) -> None:
        dataset = strio.parse_genemapper(
            "Lane\tMarker\tAllele 1\tHeight 1\n7\tvWA\t14\t1\n", sample_id_column="lane"
        )
        sample = dataset.sample("7")
        self.assertEqual((sample.display_name, sample.sample_name), ("7", None))
        self.assertEqual(dataset.source.sample_id_column, "Lane")


class HeaderEdgeTests(unittest.TestCase):
    def test_missing_marker_column(self) -> None:
        with self.assertRaisesRegex(MissingColumnError, "Missing required column: 'Marker'"):
            strio.parse_genemapper("Sample Name\tLocus\tAllele 1\tHeight 1\nS\tvWA\t14\t1\n")

    def test_missing_height_columns_when_required(self) -> None:
        with self.assertRaisesRegex(MissingColumnError, "Height 1"):
            strio.parse_genemapper("Sample Name\tMarker\tAllele 1\nS\tvWA\t14\n")

    def test_area_and_peak_area_with_one_number_are_duplicates(self) -> None:
        with self.assertRaisesRegex(DuplicateColumnError, "'area' 1"):
            strio.parse_genemapper(
                "Sample Name\tMarker\tAllele 1\tHeight 1\tArea 1\tPeak Area 1\nS\tvWA\t14\t1\t2\t2\n"
            )

    def test_peak_area_is_read_as_area(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tHeight 1\tPeak Area 1\nS\tvWA\t14\t1\t250\n"
        )
        self.assertEqual(dataset.sample("S").loci["vWA"].alleles[0].area, 250)

    def test_first_line_that_no_delimiter_can_split(self) -> None:
        with self.assertRaisesRegex(ParseError, "Could not detect CSV delimiter"):
            strio.parse_genemapper('"Sample Name"x\tMarker\tAllele 1\nS\tvWA\t14\n')

    def test_character_after_closing_quote(self) -> None:
        with self.assertRaisesRegex(ParseError, "line 2: unexpected character after a closing"):
            strio.parse_genemapper(
                'Sample Name,Marker,Allele 1,Height 1\n"S"x,vWA,14,1\n', delimiter=","
            )

    def test_columns_are_found_ignoring_case_and_spacing(self) -> None:
        dataset = strio.parse_genemapper(
            "SAMPLE  NAME\tmarker\tDYE\tallele 1\theight 1\nS\tvWA\tB\t14\t1\n"
        )
        locus = dataset.sample("S").loci["vWA"]
        self.assertEqual((locus.dye, locus.labels), ("B", ("14",)))


if __name__ == "__main__":
    unittest.main()
