"""Legacy suite: model invariants ported from EPG-Renderer 0.15.1.

Source: ``tests/test_public_api_and_models.py``, class ``ImmutableCallModelTests``
(four of its five tests). Renderer names map to STRio names as follows:
``AlleleCall`` -> ``Allele``, ``MarkerCall`` -> ``Locus``, ``SampleCall`` -> ``Sample``,
``GeneMapperProject`` -> ``Dataset`` + ``SourceInfo``. The renderer-only fields
``origin``, ``height_mode`` and ``export_mode`` do not exist in STRio; the invalid
states that concern them are not ported (see docs/TEST_PROVENANCE.md).
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from _support import FIXTURES

import strio
from strio import Allele, Dataset, Locus, Sample, SourceInfo


def _source(header=("Sample Name", "Marker"), delimiter="\t", column="Sample Name"):
    return SourceInfo("test", header, delimiter, column)


class LegacyImmutableModelTests(unittest.TestCase):
    def test_locus_defensively_copies_alleles(self) -> None:
        alleles = [Allele(1, "15", 100)]
        locus = Locus("D3S1358", "FAM", alleles)
        alleles.append(Allele(2, "16", 90))
        self.assertEqual(locus.alleles, (Allele(1, "15", 100),))
        with self.assertRaises(FrozenInstanceError):
            locus.dye = "VIC"  # type: ignore[misc]

    def test_sample_and_dataset_defensively_copy_nested_mappings(self) -> None:
        locus = Locus("D3S1358", "FAM", (Allele(1, "15", 100),))
        loci = {"D3S1358": locus}
        sample = Sample("S1", loci)
        loci.clear()
        self.assertEqual(tuple(sample.loci), ("D3S1358",))
        with self.assertRaises(TypeError):
            sample.loci["vWA"] = locus  # type: ignore[index]

        samples = {"S1": sample}
        dataset = Dataset(samples, _source())
        samples.clear()
        self.assertEqual(dataset.sample_ids, ("S1",))
        with self.assertRaises(TypeError):
            dataset.samples["S2"] = sample  # type: ignore[index]

    def test_constructors_reject_invalid_states(self) -> None:
        valid_allele = Allele(1, "15", 100)
        valid_locus = Locus("D3S1358", "FAM", (valid_allele,))
        invalid_factories = (
            lambda: Allele(0, "15", 100),
            lambda: Allele(1, "   ", 100),
            lambda: Allele(1, "15", -1),
            lambda: Allele(1, "15", 100, size_bp="not-a-number"),
            lambda: Allele(1, "15", 100, size_bp="NaN"),
            lambda: Allele(1, "15", 100, area=-1),
            lambda: Locus("", "FAM", (valid_allele,)),
            lambda: Locus("D3S1358", "FAM", (Allele(1, "15", 100), Allele(1, "16", 90))),
            lambda: Sample("", {}),
            lambda: Sample("S", {"vWA": valid_locus}),
            lambda: Dataset({"S2": Sample("S", {})}, _source(header=("Sample Name",))),
            lambda: _source(header=()),
            lambda: _source(header=("Sample Name",), delimiter="::"),
            lambda: _source(header=("Sample Name",), column=""),
        )
        for factory in invalid_factories:
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()

    def test_loaded_dataset_is_immutable_at_every_layer(self) -> None:
        dataset = strio.read_genemapper(FIXTURES / "globalfiler_minimal.tsv")
        sample = dataset.sample("S1")
        locus = sample.loci["D3S1358"]
        with self.assertRaises(FrozenInstanceError):
            locus.marker = "vWA"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            sample.id = "S2"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            dataset.source.delimiter = ","  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
