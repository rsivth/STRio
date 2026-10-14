"""Legacy suite: ported parser contracts from three further EPG-Renderer 0.15.1 modules.

* ``tests/test_genemapper_exports.py`` -- the three tests about parsing the complete
  synthetic exports. The kit, positioning and rendering tests stay in EPG-Renderer.
* ``tests/test_rfu_limits.py`` -- the three GeneMapper-parser tests. The renderer's
  32,767-RFU ceiling is now the explicit option ``max_height=32_767``; the constant,
  manual-profile and renderer-model tests stay in EPG-Renderer.
* ``tests/test_batch_and_gui_regressions.py`` -- the case-only duplicate marker test.
"""

from __future__ import annotations

import hashlib
import unittest

from _support import EXPORTS, RFU_LIMIT, write_temp

import strio
from strio import DuplicateLocusError, NumericValueError

ESSPLEX = EXPORTS / "essplex_se_qs_mixed_export.txt"
NGM_SELECT = EXPORTS / "ngm_select_mixed_export.txt"


def _counts(dataset: strio.Dataset) -> tuple[int, int, int, int]:
    loci = [locus for sample in dataset.samples.values() for locus in sample.loci.values()]
    alleles = [len(locus.alleles) for locus in loci]
    return len(dataset.samples), len(loci), sum(alleles), max(alleles)


class LegacyGeneMapperExportTests(unittest.TestCase):
    def test_fixtures_are_pinned_synthetic_exports(self) -> None:
        expected = {
            ESSPLEX: "594415bd6e6015a6fd62fd24b729e9da89a12322178a4d5cfde6cfc121639b20",
            NGM_SELECT: "4711b7dd24c6db92946b3f6f825bc3174a95f10cf92ec23ea00f358f0bb1d3cd",
        }
        for path, digest in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_essplex_se_qs_export_parses_without_losing_calls(self) -> None:
        dataset = strio.read_genemapper(ESSPLEX)
        self.assertEqual(_counts(dataset), (7, 133, 530, 20))
        self.assertTrue(
            all(
                locus.dye is None
                for sample in dataset.samples.values()
                for locus in sample.loci.values()
            )
        )
        self.assertIn("empty unnamed trailing column", dataset.messages[0])
        self.assertIn("Allele 20", dataset.messages[1])

    def test_ngm_select_export_preserves_duplicate_display_names_as_injections(self) -> None:
        dataset = strio.read_genemapper(NGM_SELECT)
        samples, loci, alleles, _ = _counts(dataset)
        self.assertEqual((samples, loci, alleles), (31, 527, 1497))
        ladders = [s for s in dataset.samples.values() if s.display_name == "Allelleiter"]
        self.assertEqual(len(ladders), 2)
        self.assertEqual(
            {sample.sample_file for sample in ladders},
            {"A01_Ladder_01.hid", "H01_Ladder_08.hid"},
        )
        self.assertEqual(len({sample.id for sample in ladders}), 2)
        self.assertEqual(len({sample.source_sample_id for sample in ladders}), 2)


class LegacyHeightLimitTests(unittest.TestCase):
    def _export(self, height: int | str):
        return write_temp(
            self,
            f"Sample Name\tMarker\tAllele 1\tHeight 1\nS\tD3S1358\t15\t{height}\n",
            suffix=".tsv",
        )

    def test_parser_accepts_supported_maximum(self) -> None:
        dataset = strio.read_genemapper(self._export(32_767), max_height=RFU_LIMIT)
        self.assertEqual(dataset.sample("S").loci["D3S1358"].alleles[0].height, 32_767)

    def test_parser_rejects_height_above_supported_maximum(self) -> None:
        with self.assertRaisesRegex(NumericValueError, "32,767"):
            strio.read_genemapper(self._export(32_768), max_height=RFU_LIMIT)

    def test_parser_rejects_pathological_height_without_overflow(self) -> None:
        with self.assertRaisesRegex(NumericValueError, "32,767"):
            strio.read_genemapper(self._export("9" * 400), max_height=RFU_LIMIT)


class LegacyDuplicateMarkerTests(unittest.TestCase):
    def test_parser_rejects_case_only_duplicate_marker_rows(self) -> None:
        path = write_temp(
            self,
            "Sample Name\tMarker\tDye\tAllele 1\tHeight 1\n"
            "S\tD3S1358\tFAM\t15\t100\nS\td3s1358\tFAM\t16\t90\n",
            suffix=".tsv",
        )
        with self.assertRaises(DuplicateLocusError) as caught:
            strio.read_genemapper(path)
        self.assertIn("D3S1358", str(caught.exception))
        self.assertIn("d3s1358", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
