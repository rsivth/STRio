"""Legacy suite: strio must reproduce EPG-Renderer 0.15.1's parse of every fixture.

The JSON files in ``tests/golden/`` were recorded from EPG-Renderer 0.15.1 with
``tools/make_legacy_golden.py``. They freeze the old behaviour field by field: header,
delimiter, encoding, warnings, sample identities, markers, dyes and every allele with
height, size, area, mutation and comment. strio is read with ``max_height=32_767``,
the renderer's ceiling.
"""

from __future__ import annotations

import json
import unittest

from _support import FIXTURES, RFU_LIMIT, ROOT

import strio

GOLDEN = ROOT / "tests" / "golden"


def _snapshot(dataset: strio.Dataset) -> dict[str, object]:
    return {
        "header": list(dataset.source.header),
        "delimiter": dataset.source.delimiter,
        "sample_id_column": dataset.source.sample_id_column,
        "encoding": dataset.source.encoding,
        "warnings": list(dataset.messages),
        "samples": [
            {
                "id": sample.id,
                "display_name": sample.display_name,
                "sample_name": sample.sample_name,
                "sample_file": sample.sample_file,
                "source_sample_id": sample.source_sample_id,
                "run_name": sample.run_name,
                "loci": [
                    {
                        "marker": locus.marker,
                        "dye": locus.dye,
                        "alleles": [
                            [
                                allele.index,
                                allele.label,
                                allele.height,
                                None if allele.size_bp is None else str(allele.size_bp),
                                allele.area,
                                allele.mutation,
                                allele.comment,
                            ]
                            for allele in locus.alleles
                        ],
                    }
                    for locus in sample.loci.values()
                ],
            }
            for sample in dataset.samples.values()
        ],
    }


class LegacyGoldenTests(unittest.TestCase):
    def test_every_fixture_has_a_golden_record(self) -> None:
        fixtures = {
            path.relative_to(FIXTURES).as_posix() for path in FIXTURES.rglob("*") if path.is_file()
        }
        recorded = {
            json.loads(path.read_text(encoding="utf-8"))["fixture"]
            for path in GOLDEN.glob("*.json")
        }
        self.assertEqual(recorded, fixtures)

    def test_strio_reproduces_renderer_parse_of_every_fixture(self) -> None:
        for golden_path in sorted(GOLDEN.glob("*.json")):
            expected = json.loads(golden_path.read_text(encoding="utf-8"))
            with self.subTest(fixture=expected["fixture"]):
                self.assertEqual(expected["recorded_with"], "EPG-Renderer 0.15.1")
                dataset = strio.read_genemapper(
                    FIXTURES / expected["fixture"], max_height=RFU_LIMIT
                )
                actual = _snapshot(dataset)
                for key, value in actual.items():
                    self.assertEqual(value, expected[key], key)


if __name__ == "__main__":
    unittest.main()
