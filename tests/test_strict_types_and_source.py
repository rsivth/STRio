"""New in 0.2.0: text fields accept only str, and SourceInfo is format-neutral.

Findings #4 (silent str() conversion) and #1 (table properties in SourceInfo) of the
external code review of 0.1.1.
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from _support import FIXTURES

import strio
from strio import (
    Allele,
    Dataset,
    Diagnostic,
    DiagnosticCode,
    Locus,
    Sample,
    SourceInfo,
    TableLayout,
    marker_key,
    parse_allele_label,
)


class StrictTextTests(unittest.TestCase):
    def test_required_text_rejects_other_types_instead_of_converting(self) -> None:
        factories = (
            lambda: Allele(1, None),  # type: ignore[arg-type]
            lambda: Allele(1, 15),  # type: ignore[arg-type]
            lambda: Locus(None, None, ()),  # type: ignore[arg-type]
            lambda: Sample(123),  # type: ignore[arg-type]
            lambda: SourceInfo(None),  # type: ignore[arg-type]
            lambda: TableLayout(("A",), ",", 1),  # type: ignore[arg-type]
        )
        for factory in factories:
            with self.subTest(factory=factory), self.assertRaises(TypeError):
                factory()

    def test_optional_text_accepts_only_str_or_none(self) -> None:
        factories = (
            lambda: Allele(1, "15", mutation=1),  # type: ignore[arg-type]
            lambda: Allele(1, "15", comment=b"x"),  # type: ignore[arg-type]
            lambda: Locus("vWA", 3, ()),  # type: ignore[arg-type]
            lambda: Sample("S", display_name=1),  # type: ignore[arg-type]
            lambda: Sample("S", sample_file=Path("A01.hid")),  # type: ignore[arg-type]
            lambda: SourceInfo("f", encoding=8),  # type: ignore[arg-type]
        )
        for factory in factories:
            with self.subTest(factory=factory), self.assertRaises(TypeError):
                factory()
        self.assertIsNone(Allele(1, "15", mutation=None).mutation)

    def test_size_accepts_decimal_int_and_decimal_text_only(self) -> None:
        self.assertEqual(Allele(1, "15", size_bp=Decimal("160.5")).size_bp, Decimal("160.5"))
        self.assertEqual(Allele(1, "15", size_bp=160).size_bp, Decimal(160))  # type: ignore[arg-type]
        self.assertEqual(Allele(1, "15", size_bp="160.5").size_bp, Decimal("160.5"))  # type: ignore[arg-type]
        for value in (160.5, True, [160]):
            with self.subTest(value=value), self.assertRaises(TypeError):
                Allele(1, "15", size_bp=value)  # type: ignore[arg-type]

    def test_helpers_reject_non_strings(self) -> None:
        for call in (
            lambda: marker_key(None),  # type: ignore[arg-type]
            lambda: parse_allele_label(9.3),  # type: ignore[arg-type]
            lambda: Diagnostic(DiagnosticCode.TRAILING_EMPTY_COLUMNS, 3),  # type: ignore[arg-type]
            lambda: Locus("vWA", None, (), extra={1: "x"}),  # type: ignore[dict-item]
        ):
            with self.subTest(call=call), self.assertRaises(TypeError):
                call()

    def test_parse_genemapper_requires_decoded_text(self) -> None:
        text = "Sample Name\tMarker\tAllele 1\tHeight 1\nS\tvWA\t14\t1\n"
        with self.assertRaisesRegex(TypeError, "decode bytes first"):
            strio.parse_genemapper(text.encode())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            strio.parse_genemapper(text, source=Path("x"))  # type: ignore[arg-type]

    def test_sequences_of_text_must_hold_text(self) -> None:
        for factory in (
            lambda: TableLayout(("A", 2), ",", "A"),  # type: ignore[arg-type]
            lambda: TableLayout("AB", ",", "A"),
            lambda: TableLayout(("A",), ",", "A", extra_columns=(None,)),  # type: ignore[arg-type]
        ):
            with self.subTest(factory=factory), self.assertRaises(TypeError):
                factory()


class TableLayoutTests(unittest.TestCase):
    def test_reader_describes_its_table(self) -> None:
        dataset = strio.read_genemapper(FIXTURES / "globalfiler_minimal.tsv")
        table = dataset.source.require_table()
        self.assertIs(dataset.source.table, table)
        self.assertEqual((table.delimiter, table.sample_id_column), ("\t", "Sample Name"))
        self.assertEqual(table.header[:3], ("Sample Name", "Marker", "Dye"))
        self.assertEqual(table.extra_columns, ())

    def test_layout_invariants(self) -> None:
        for factory in (
            lambda: TableLayout((), ",", "A"),
            lambda: TableLayout(("A", " "), ",", "A"),
            lambda: TableLayout(("A",), ";;", "A"),
            lambda: TableLayout(("A",), ",", "B"),
            lambda: TableLayout(("A",), ",", "A", extra_columns=("C",)),
        ):
            with self.subTest(factory=factory), self.assertRaises(ValueError):
                factory()

    def test_layout_is_frozen_and_copies_its_sequences(self) -> None:
        header = ["A", "B"]
        table = TableLayout(header, ",", "A", extra_columns=["B"])  # type: ignore[arg-type]
        header.append("C")
        self.assertEqual(table.header, ("A", "B"))
        self.assertEqual(table.extra_columns, ("B",))


class FormatNeutralSourceTests(unittest.TestCase):
    def test_source_without_table_is_valid(self) -> None:
        source = SourceInfo("familias", path="case.fam", encoding="utf-8")  # type: ignore[arg-type]
        self.assertIsNone(source.table)
        self.assertEqual(source.path, Path("case.fam"))
        dataset = Dataset({"S": Sample("S")}, source)
        self.assertEqual(dataset.sample_ids, ("S",))

    def test_require_table_names_the_format_without_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "'familias' has no table layout"):
            SourceInfo("familias").require_table()

    def test_source_has_no_table_attributes_of_its_own(self) -> None:
        source = SourceInfo("genemapper-table")
        for name in ("header", "delimiter", "sample_id_column", "extra_columns"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(source, name))

    def test_source_rejects_invalid_parts(self) -> None:
        with self.assertRaises(TypeError):
            SourceInfo("f", table=("A",))  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            SourceInfo("f", path=3)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            SourceInfo("f", encoding=" ")

    def test_layout_is_exported(self) -> None:
        self.assertIn("TableLayout", strio.__all__)


if __name__ == "__main__":
    unittest.main()
