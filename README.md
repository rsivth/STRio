# STRio

Read forensic STR typing results into one format-neutral, immutable Python data model.

STRio currently reads **GeneMapper genotype-table exports** (tab, semicolon or comma
separated). It is the shared input layer of [EPG-Renderer](https://github.com/rsivth/EPG-Renderer)
and of planned statistics modules, so that every program reads an export in exactly the
same way.

```python
import strio

dataset = strio.read_genemapper("export.txt")
for sample in dataset.samples.values():
    for locus in sample.loci.values():
        print(sample.id, locus.marker, locus.labels)
for finding in dataset.diagnostics:
    print("Note:", finding)
```

## What it does

- Finds columns by name, in any order: `Allele 1, Allele 2, Height 1, Height 2` and
  `Allele 1, Height 1, Allele 2, Height 2` are read alike.
- Detects delimiter and encoding (UTF-8 with or without BOM, UTF-16 with BOM, cp1252).
- Keeps sample injections with the same Sample Name apart.
- Keeps every column it does not interpret, per row.
- Rejects malformed input with the line and column, instead of repairing it.
- Reports non-fatal findings (truncated allele lists, ignored columns) with stable codes.

## Documentation

- [Manual](docs/MANUAL.md) – a walk through every feature, with tested examples
- [GeneMapper reader reference](docs/GENEMAPPER.md) – every reading rule
- [Data model](docs/DATA_MODEL.md) – types, invariants and design decisions
- [Development](docs/DEVELOPMENT.md) – working rules, checks, release
- [Test provenance](docs/TEST_PROVENANCE.md) – where each test comes from
- [Changelog](CHANGELOG.md)

## Installation

Python 3.10 or newer, no further dependencies.

```text
pip install "strio-forensic @ git+https://github.com/rsivth/strio@v0.1.1"
```

The import name is `strio`; the distribution is `strio-forensic` because `strio` is
taken on PyPI by an unrelated project.

## Tests

```text
python run_tests.py
```

## Status

Alpha (0.x): the data model may still change between minor versions; every change is
recorded in the changelog together with the old behaviour.

## License

BSD 3-Clause, see [LICENSE](LICENSE).
