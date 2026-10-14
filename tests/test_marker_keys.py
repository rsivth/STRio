"""New in 0.1.0: canonical marker keys and locus lookup by key."""

from __future__ import annotations

import unittest

import strio
from strio import MARKER_SYNONYMS, Allele, Locus, Sample, marker_key


class MarkerKeyTests(unittest.TestCase):
    def test_case_and_whitespace_are_ignored(self) -> None:
        cases = {
            "vWA": "VWA",
            "VWA": "VWA",
            " vwa ": "VWA",
            "Penta D": "PENTAD",
            "PentaD": "PENTAD",
            "D21 S11": "D21S11",
            "DYS389 II": "DYS389II",
        }
        for name, key in cases.items():
            with self.subTest(name=name):
                self.assertEqual(marker_key(name), key)

    def test_documented_synonyms_map_to_one_key(self) -> None:
        for name in ("AM", "Amelogenin", "AMEL", "amel"):
            with self.subTest(name=name):
                self.assertEqual(marker_key(name), "AMEL")
        self.assertEqual(marker_key("ACTBP2"), "SE33")
        self.assertEqual(marker_key("SE33"), "SE33")

    def test_synonym_table_is_read_only(self) -> None:
        with self.assertRaises(TypeError):
            MARKER_SYNONYMS["X"] = "Y"  # type: ignore[index]

    def test_unicode_is_normalised(self) -> None:
        composed = "DÄ"
        decomposed = "DÄ"
        self.assertEqual(marker_key(composed), marker_key(decomposed))

    def test_blank_names_are_rejected(self) -> None:
        for name in ("", "   ", "\t"):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                marker_key(name)

    def test_unrelated_names_are_never_merged(self) -> None:
        self.assertNotEqual(marker_key("D2S1338"), marker_key("D2S441"))
        self.assertNotEqual(marker_key("DYS385a"), marker_key("DYS385b"))


class LocusLookupTests(unittest.TestCase):
    def _sample(self, *markers: str) -> Sample:
        loci = {name: Locus(name, None, (Allele(1, "15", 100),)) for name in markers}
        return Sample("S", loci)

    def test_locus_carries_its_key(self) -> None:
        self.assertEqual(Locus("Amelogenin", None, ()).key, "AMEL")

    def test_lookup_by_any_spelling(self) -> None:
        sample = self._sample("vWA", "Amelogenin")
        self.assertEqual(sample.locus("VWA").marker, "vWA")
        self.assertEqual(sample.locus("AM").marker, "Amelogenin")
        self.assertTrue(sample.has_locus("amel"))

    def test_missing_locus_raises_key_error(self) -> None:
        sample = self._sample("vWA")
        with self.assertRaises(KeyError):
            sample.locus("TH01")
        self.assertFalse(sample.has_locus("TH01"))

    def test_synonym_rows_in_one_sample_are_kept_but_ambiguous(self) -> None:
        dataset = strio.parse_genemapper(
            "Sample Name\tMarker\tAllele 1\tHeight 1\nS\tAM\tX\t100\nS\tAmelogenin\tY\t90\n"
        )
        sample = dataset.sample("S")
        self.assertEqual(tuple(sample.loci), ("AM", "Amelogenin"))
        with self.assertRaisesRegex(LookupError, "ambiguous"):
            sample.locus("AMEL")
        self.assertFalse(sample.has_locus("AMEL"))

    def test_sample_rejects_case_only_duplicate_loci(self) -> None:
        with self.assertRaises(ValueError):
            self._sample("vWA", "VWA")


if __name__ == "__main__":
    unittest.main()
