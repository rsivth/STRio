"""New in 0.1.0: model behaviour beyond the invariants taken over from EPG-Renderer."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

from strio import Allele, Dataset, Diagnostic, DiagnosticCode, Locus, Sample, SourceInfo


def _source() -> SourceInfo:
    return SourceInfo("test", ("Sample Name", "Marker"), "\t", "Sample Name")


class AlleleModelTests(unittest.TestCase):
    def test_measurements_default_to_none(self) -> None:
        allele = Allele(1, "15")
        self.assertEqual(
            (allele.height, allele.size_bp, allele.area, allele.mutation, allele.comment),
            (None, None, None, None, None),
        )

    def test_size_is_converted_to_decimal(self) -> None:
        self.assertEqual(Allele(1, "15", 1, size_bp="160.25").size_bp, Decimal("160.25"))  # type: ignore[arg-type]
        self.assertEqual(Allele(1, "15", 1, size_bp=160).size_bp, Decimal("160"))  # type: ignore[arg-type]

    def test_blank_optional_text_becomes_none(self) -> None:
        allele = Allele(1, "15", 1, mutation="  ", comment=" ok ")
        self.assertIsNone(allele.mutation)
        self.assertEqual(allele.comment, "ok")

    def test_booleans_are_not_numbers(self) -> None:
        for factory in (
            lambda: Allele(True, "15"),  # type: ignore[arg-type]
            lambda: Allele(1, "15", height=True),  # type: ignore[arg-type]
            lambda: Allele(1, "15", area=False),  # type: ignore[arg-type]
        ):
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()


class LocusModelTests(unittest.TestCase):
    def test_labels_and_key(self) -> None:
        locus = Locus(" vWA ", "", (Allele(1, "14", 1), Allele(3, "16", 1)))
        self.assertEqual(locus.marker, "vWA")
        self.assertEqual(locus.key, "VWA")
        self.assertIsNone(locus.dye)
        self.assertEqual(locus.labels, ("14", "16"))

    def test_extra_is_a_read_only_copy(self) -> None:
        extra = {"Panel": "NGM"}
        locus = Locus("vWA", None, (), extra=extra)
        extra["Panel"] = "changed"
        self.assertEqual(locus.extra["Panel"], "NGM")
        with self.assertRaises(TypeError):
            locus.extra["Panel"] = "x"  # type: ignore[index]

    def test_invalid_loci_are_rejected(self) -> None:
        for factory, error in (
            (lambda: Locus("vWA", None, ("14",)), TypeError),  # type: ignore[arg-type]
            (lambda: Locus("vWA", None, (Allele(2, "14"), Allele(1, "16"))), ValueError),
            (lambda: Locus("vWA", None, (), line=0), ValueError),
            (lambda: Locus("vWA", None, (), extra={"": "x"}), ValueError),
            (lambda: Locus("vWA", None, (), extra={"Panel": 1}), TypeError),  # type: ignore[dict-item]
        ):
            with self.subTest(factory=factory), self.assertRaises(error):
                factory()

    def test_key_is_not_a_constructor_argument(self) -> None:
        with self.assertRaises(TypeError):
            Locus("vWA", None, (), key="VWA")  # type: ignore[call-arg]


class SampleModelTests(unittest.TestCase):
    def test_display_name_defaults_to_id(self) -> None:
        self.assertEqual(Sample("S1").display_name, "S1")
        self.assertEqual(Sample("S1", display_name="Stain 1").display_name, "Stain 1")

    def test_identity_fields_are_normalised(self) -> None:
        sample = Sample("S1", sample_file=" A01.hid ", run_name="  ", source_sample_id=None)
        self.assertEqual(sample.sample_file, "A01.hid")
        self.assertIsNone(sample.run_name)

    def test_loci_must_be_locus_objects(self) -> None:
        with self.assertRaises(TypeError):
            Sample("S1", {"vWA": "14"})  # type: ignore[dict-item]

    def test_common_extra_requires_every_row(self) -> None:
        sample = Sample(
            "S1",
            {
                "vWA": Locus("vWA", None, (), extra={"Panel": "NGM"}),
                "TH01": Locus("TH01", None, ()),
            },
        )
        with self.assertRaises(ValueError):
            sample.common_extra("Panel")


class DatasetModelTests(unittest.TestCase):
    def test_sample_access_and_messages(self) -> None:
        diagnostic = Diagnostic(DiagnosticCode.TRAILING_EMPTY_COLUMNS, "note")
        dataset = Dataset({"S1": Sample("S1")}, _source(), (diagnostic,))
        self.assertEqual(dataset.sample_ids, ("S1",))
        self.assertEqual(dataset.sample("S1").id, "S1")
        self.assertEqual(dataset.messages, ("note",))
        with self.assertRaises(KeyError):
            dataset.sample("S2")

    def test_invalid_datasets_are_rejected(self) -> None:
        for factory in (
            lambda: Dataset({"S1": "sample"}, _source()),  # type: ignore[dict-item]
            lambda: Dataset({}, "source"),  # type: ignore[arg-type]
            lambda: Dataset({}, _source(), ("warning",)),  # type: ignore[arg-type]
        ):
            with self.subTest(factory=factory), self.assertRaises(TypeError):
                factory()

    def test_source_path_is_converted_and_frozen(self) -> None:
        source = SourceInfo("f", ("A",), ",", "A", path="x/y.txt")  # type: ignore[arg-type]
        self.assertEqual(source.path, Path("x/y.txt"))
        with self.assertRaises(FrozenInstanceError):
            source.format = "other"  # type: ignore[misc]
        with self.assertRaises(ValueError):
            SourceInfo(" ", ("A",), ",", "A")


if __name__ == "__main__":
    unittest.main()
