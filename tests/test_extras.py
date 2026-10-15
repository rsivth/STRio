"""New in 0.1.0: columns the reader does not interpret are kept per row."""

from __future__ import annotations

import unittest

from _support import EXPORTS

import strio
from strio import InconsistentExtraError

HEADER = (
    "Sample File\tSample Name\tPanel\tMarker\tDye\tAllele 1\tAllele 2\tHeight 1\tHeight 2\t"
    "Peak Area 1\tPeak Area 2\tData Point 1\tData Point 2\tAllele Display Overflow\tAE\n"
)


def _parse(rows: str, **options: object) -> strio.Dataset:
    return strio.parse_genemapper(HEADER + rows, **options)  # type: ignore[arg-type]


class ExtraColumnTests(unittest.TestCase):
    def test_uninterpreted_columns_are_kept_in_header_order(self) -> None:
        dataset = _parse(
            "A1.hid\tS\tNGM_v1\tvWA\tB\t14\t16\t1100\t970\t9000\t8000\t3301\t3410\t0\t\n"
        )
        self.assertEqual(
            dataset.source.require_table().extra_columns,
            ("Panel", "Data Point 1", "Data Point 2", "Allele Display Overflow", "AE"),
        )
        locus = dataset.sample("S").loci["vWA"]
        self.assertEqual(
            dict(locus.extra),
            {
                "Panel": "NGM_v1",
                "Data Point 1": "3301",
                "Data Point 2": "3410",
                "Allele Display Overflow": "0",
                "AE": "",
            },
        )
        self.assertEqual(tuple(locus.extra), dataset.source.require_table().extra_columns)

    def test_interpreted_columns_are_not_duplicated_into_extras(self) -> None:
        dataset = _parse("A1.hid\tS\tNGM_v1\tvWA\tB\t14\t16\t1100\t970\t9000\t8000\t1\t2\t0\t\n")
        interpreted = {"Sample File", "Sample Name", "Marker", "Dye", "Allele 1", "Height 1"}
        interpreted |= {"Peak Area 1", "Allele 2", "Height 2", "Peak Area 2"}
        self.assertFalse(interpreted & set(dataset.source.require_table().extra_columns))
        self.assertEqual(dataset.sample("S").loci["vWA"].alleles[1].area, 8000)

    def test_extra_values_are_stripped_and_empty_values_kept(self) -> None:
        dataset = _parse("A1.hid\tS\t  NGM_v1 \tvWA\tB\t14\t\t1100\t\t\t\t\t\t\t\n")
        extra = dataset.sample("S").loci["vWA"].extra
        self.assertEqual(extra["Panel"], "NGM_v1")
        self.assertEqual(extra["Data Point 1"], "")

    def test_each_row_keeps_its_own_values(self) -> None:
        dataset = _parse(
            "A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t\t\tPHR\n"
            "A1.hid\tS\tNGM_v1\tTH01\tG\t9.3\t\t800\t\t\t\t\t\t\t\n"
        )
        sample = dataset.sample("S")
        self.assertEqual(sample.loci["vWA"].extra["AE"], "PHR")
        self.assertEqual(sample.loci["TH01"].extra["AE"], "")

    def test_ignoring_dyes_keeps_the_dye_column_as_extra(self) -> None:
        dataset = _parse("A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t\t\t\n", dye_column=None)
        locus = dataset.sample("S").loci["vWA"]
        self.assertIsNone(locus.dye)
        self.assertEqual(locus.extra["Dye"], "B")

    def test_files_without_extra_columns_have_empty_extras(self) -> None:
        dataset = strio.read_genemapper(EXPORTS / "ngm_select_mixed_export.txt")
        self.assertEqual(dataset.source.require_table().extra_columns, ())
        self.assertTrue(
            all(
                not locus.extra
                for sample in dataset.samples.values()
                for locus in sample.loci.values()
            )
        )


class CommonExtraTests(unittest.TestCase):
    def test_value_shared_by_every_row_is_returned(self) -> None:
        dataset = _parse(
            "A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t\t\t\n"
            "A1.hid\tS\tNGM_v1\tTH01\tG\t9.3\t\t800\t\t\t\t\t\t\t\n"
        )
        self.assertEqual(dataset.sample("S").common_extra("Panel"), "NGM_v1")

    def test_disagreeing_rows_raise(self) -> None:
        dataset = _parse(
            "A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t\t\tPHR\n"
            "A1.hid\tS\tNGM_v1\tTH01\tG\t9.3\t\t800\t\t\t\t\t\t\t\n"
        )
        with self.assertRaisesRegex(InconsistentExtraError, "AE.*differs"):
            dataset.sample("S").common_extra("AE")

    def test_unknown_column_raises_key_error(self) -> None:
        dataset = _parse("A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t\t\t\n")
        with self.assertRaises(KeyError):
            dataset.sample("S").common_extra("Sample Type")


class IndexedExtraTests(unittest.TestCase):
    def test_numbered_extra_is_paired_with_its_allele(self) -> None:
        dataset = _parse("A1.hid\tS\tNGM_v1\tvWA\tB\t14\t16\t1100\t970\t\t\t3301\t3410\t0\t\n")
        locus = dataset.sample("S").loci["vWA"]
        pairs = [(a.label, locus.indexed_extra("data point", a.index)) for a in locus.alleles]
        self.assertEqual(pairs, [("14", "3301"), ("16", "3410")])

    def test_missing_numbered_extra_raises_key_error(self) -> None:
        dataset = _parse("A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t\t\t\n")
        with self.assertRaises(KeyError):
            dataset.sample("S").loci["vWA"].indexed_extra("Data Point", 3)

    def test_numbered_extra_without_allele_is_kept_not_rejected(self) -> None:
        dataset = _parse("A1.hid\tS\tNGM_v1\tvWA\tB\t14\t\t1100\t\t\t\t\t999\t\t\n")
        locus = dataset.sample("S").loci["vWA"]
        self.assertEqual(locus.labels, ("14",))
        self.assertEqual(locus.indexed_extra("Data Point", 2), "999")


if __name__ == "__main__":
    unittest.main()
