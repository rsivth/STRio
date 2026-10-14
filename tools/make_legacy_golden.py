"""Record EPG-Renderer's parser output for every fixture as JSON golden files.

Provenance tool, not part of the test suite. It needs EPG-Renderer 0.15.1 importable
(for example ``PYTHONPATH=/path/to/EPG-Renderer/src``). The resulting files in
``tests/golden/`` freeze the *old* behaviour; ``tests/test_legacy_golden.py`` checks that
strio still reproduces it. Regenerate only when the old behaviour itself is meant to be
re-recorded, and document why in CHANGELOG.md.

Usage::

    PYTHONPATH=../EPG-Renderer/src python tools/make_legacy_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

from epg_renderer.parser import read_genotypes_table
from epg_renderer.version import __version__ as renderer_version

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"


def snapshot(path: Path) -> dict[str, object]:
    """Return a JSON-serialisable record of the renderer's parse of ``path``."""

    project = read_genotypes_table(path)
    return {
        "recorded_with": f"EPG-Renderer {renderer_version}",
        "fixture": path.relative_to(FIXTURES).as_posix(),
        "header": list(project.header),
        "delimiter": project.delimiter,
        "sample_id_column": project.sample_id_column,
        "encoding": project.encoding,
        "warnings": list(project.warnings),
        "samples": [
            {
                "id": sample.sample_id,
                "display_name": sample.display_name,
                "sample_name": sample.sample_name,
                "sample_file": sample.sample_file,
                "source_sample_id": sample.source_sample_id,
                "run_name": sample.run_name,
                "loci": [
                    {
                        "marker": marker.marker,
                        "dye": marker.dye,
                        "alleles": [
                            [
                                call.allele_index,
                                call.allele,
                                call.height,
                                None if call.size_bp is None else str(call.size_bp),
                                call.area,
                                call.mutation,
                                call.comment,
                            ]
                            for call in marker.alleles
                        ],
                    }
                    for marker in sample.markers.values()
                ],
            }
            for sample in project.samples.values()
        ],
    }


def main() -> None:
    """Write one golden file per fixture."""

    GOLDEN.mkdir(exist_ok=True)
    for path in sorted(p for p in FIXTURES.rglob("*") if p.is_file()):
        target = GOLDEN / (path.relative_to(FIXTURES).as_posix().replace("/", "__") + ".json")
        target.write_text(
            json.dumps(snapshot(path), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
