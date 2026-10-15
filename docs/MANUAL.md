# STRio manual

This manual walks through reading a GeneMapper export with STRio and using the result.
Every example below is executed by the test suite (`tests/test_documentation.py`), run
from the repository root, so the shown output is the real output of this version.

- [Installation](#installation)
- [Reading a file](#reading-a-file)
- [Samples, loci and alleles](#samples-loci-and-alleles)
- [Finding a locus by any spelling](#finding-a-locus-by-any-spelling)
- [Allele labels and their interpretation](#allele-labels-and-their-interpretation)
- [Columns STRio does not interpret](#columns-strio-does-not-interpret)
- [Diagnostics: non-fatal findings](#diagnostics-non-fatal-findings)
- [Errors: unusable input](#errors-unusable-input)
- [Options](#options)
- [Reading text instead of a file](#reading-text-instead-of-a-file)
- [What STRio does not do](#what-strio-does-not-do)

## Installation

STRio has no dependencies outside the Python standard library (Python 3.10 or newer).

```text
pip install "strio-forensic @ git+https://github.com/rsivth/strio@v0.2.1"
```

The distribution is called `strio-forensic` because the name `strio` is taken on PyPI by
an unrelated project; the import name is `strio`. For development, see
[DEVELOPMENT.md](DEVELOPMENT.md).

## Reading a file

```pycon
>>> import strio
>>> dataset = strio.read_genemapper("tests/fixtures/globalfiler_minimal.tsv")
>>> dataset.sample_ids
('S1',)
>>> dataset.source.format, dataset.source.encoding
('genemapper-table', 'utf-8-sig')
>>> dataset.source.table.delimiter
'\t'

```

`dataset.source` describes the origin of any dataset; `dataset.source.table` holds what
only tables have (header, delimiter, sample column, extra columns). For a GeneMapper
export it is always present; `dataset.source.require_table()` returns it with a clear
error for sources without a table.

`read_genemapper` detects the delimiter (tab, `;` or `,`) and the text encoding, and
pairs `Allele n`, `Height n`, `Size n`, `Area n`/`Peak Area n`, `Mutation n` and
`Comment n` columns by their number, in whatever column order the export uses. The
[GeneMapper reader reference](GENEMAPPER.md) lists every rule.

## Samples, loci and alleles

A `Dataset` holds `Sample` objects in source order; each sample holds `Locus` objects
(one per exported marker row) in source order; each locus holds `Allele` objects.

```pycon
>>> sample = dataset.sample("S1")
>>> list(sample.loci)[:4]
['D3S1358', 'vWA', 'D16S539', 'CSF1PO']
>>> locus = sample.loci["TH01"]
>>> locus.marker, locus.dye, locus.labels
('TH01', 'NED', ('7', '9.3'))
>>> allele = locus.alleles[1]
>>> allele.index, allele.label, allele.height, allele.size_bp, allele.area
(2, '9.3', 750, None, None)

```

Measurements that the export does not contain are `None`, never `0`. All objects are
immutable; mappings are read-only views. Constructors accept text only as `str`:
`strio.Allele(1, None)` raises `TypeError` instead of creating the label `"None"`.

When one Sample Name appears in several injections (for example two allelic ladders),
STRio keeps them apart if `Sample File`, `Sample ID` or `Run Name` differ, and makes the
identifiers unique:

```pycon
>>> exports = "tests/fixtures/genemapper_exports/"
>>> ngm = strio.read_genemapper(exports + "ngm_select_mixed_export.txt")
>>> ngm.sample_ids[:2]
('Allelleiter [A01_Ladder_01.hid]', 'Allelleiter [H01_Ladder_08.hid]')
>>> ladder = ngm.sample(ngm.sample_ids[0])
>>> ladder.display_name, ladder.sample_file
('Allelleiter', 'A01_Ladder_01.hid')

```

## Finding a locus by any spelling

`sample.loci` is keyed by the marker name exactly as exported. To look a marker up
regardless of letter case, spacing or a documented synonym, use `sample.locus()`:

```pycon
>>> sample.locus("th01").marker
'TH01'
>>> strio.marker_key("Amelogenin"), strio.marker_key("AM"), strio.marker_key("Penta D")
('AMEL', 'AMEL', 'PENTAD')

```

The synonyms are deliberately few and listed in `strio.MARKER_SYNONYMS`. If one sample
contains two rows that share a key (for example both `AM` and `Amelogenin`), both rows
are kept and `sample.locus("AMEL")` raises `LookupError` instead of choosing one.

## Allele labels and their interpretation

`allele.label` is the exported text and always authoritative. `allele.value` is a
conservative interpretation for comparing and sorting:

```pycon
>>> allele.value.kind.value, allele.value.number
('numeric', Decimal('9.3'))
>>> allele.value.full_repeats, allele.value.partial_bases
(9, 3)
>>> [strio.parse_allele_label(text).kind.value for text in ("X", "OL", "9,3", "?")]
['x', 'off_ladder', 'other', 'other']

```

A decimal comma (`9,3`) is **not** read as a microvariant: the label is classified as
`other`, because STRio does not guess.

## Columns STRio does not interpret

Every column that is not one of the interpreted columns above is kept per row in
`locus.extra`, under its exported name and with surrounding whitespace removed.
`dataset.source.table.extra_columns` lists these columns in header order.

```pycon
>>> text = (
...     "Sample Name\tPanel\tMarker\tAllele 1\tHeight 1\tData Point 1\tAE\n"
...     "S\tNGM_v1\tvWA\t14\t1100\t3301\tPHR\n"
...     "S\tNGM_v1\tTH01\t9.3\t800\t2410\t\n"
... )
>>> extra_demo = strio.parse_genemapper(text)
>>> extra_demo.source.table.extra_columns
('Panel', 'Data Point 1', 'AE')
>>> vwa = extra_demo.sample("S").loci["vWA"]
>>> dict(vwa.extra)
{'Panel': 'NGM_v1', 'Data Point 1': '3301', 'AE': 'PHR'}
>>> vwa.indexed_extra("Data Point", vwa.alleles[0].index)
'3301'
>>> extra_demo.sample("S").common_extra("Panel")
'NGM_v1'

```

Extras are always stored at row level, because that is where they are in the file.
`common_extra()` returns a value only if every row of the sample has the same value and
raises `InconsistentExtraError` otherwise, so a per-marker value (for example a quality
flag such as `AE`) is never mistaken for a sample property.

## Diagnostics: non-fatal findings

Findings that do not make the file unusable are returned, not raised:

```pycon
>>> [item.code.value for item in ngm.diagnostics]
['trailing-empty-columns', 'highest-allele-column-used']
>>> ngm.diagnostics[1].lines[:3]
(8, 9, 13)
>>> print(ngm.messages[0])
Ignored 1 empty unnamed trailing column(s).

```

| Code | Meaning |
| --- | --- |
| `trailing-empty-columns` | Empty, unnamed columns at the end of the header were ignored. |
| `allele-display-overflow` | GeneMapper flagged more alleles than exported columns; peak lists may be incomplete. |
| `highest-allele-column-used` | The last of at least ten allele columns is filled; the export may be truncated. |

Show these to the person who uses the data. They are the reader's way of saying "this
is readable, but look twice".

## Errors: unusable input

Input that cannot be read correctly raises an exception that names the line and column.
All of them derive from `strio.ParseError`, which derives from `ValueError`:

| Exception | Raised when |
| --- | --- |
| `ParseError` | the file is missing, empty, undecodable, has invalid CSV quoting, blank column names, data without a column, an allele without height, ... |
| `MissingColumnError` | the sample column, `Marker` or every `Allele n` column is absent |
| `DuplicateColumnError` | two columns have the same name ignoring case/spacing |
| `DuplicateLocusError` | one sample has the same marker row twice |
| `NumericValueError` | a height, size or area is malformed, negative or above `max_height` |

```pycon
>>> strio.parse_genemapper("Sample Name\tMarker\tAllele 1\tHeight 1\nS\tTPOX\t8\t-1\n")
Traceback (most recent call last):
...
strio.errors.NumericValueError: Negative RFU value -1 at line 2, column 'Height 1'.

```

## Options

| Option | Default | Effect |
| --- | --- | --- |
| `sample_id_column` | `"Sample Name"` | Column that names samples. |
| `marker_column` | `"Marker"` | Column with marker names. |
| `dye_column` | `"Dye"` | Dye column; `None` ignores dyes (the column is then kept as an extra). |
| `delimiter` | detected | `"\t"`, `";"` or `","`. |
| `encoding` | detected | UTF-8 (with or without BOM), UTF-16 with BOM, cp1252, latin-1. |
| `require_height` | `True` | Reject an allele without height. `False` accepts it (height `None`). |
| `max_height` | `None` | Inclusive height ceiling, e.g. `32_767` RFU as EPG-Renderer uses. |

```pycon
>>> no_heights = strio.parse_genemapper(
...     "Sample Name\tMarker\tAllele 1\nS\tTH01\t9.3\n", require_height=False
... )
>>> no_heights.sample("S").loci["TH01"].alleles[0].height is None
True

```

## Reading text instead of a file

`parse_genemapper(text, source=...)` accepts already decoded text, for example from a
clipboard or a network request. It behaves exactly like `read_genemapper` except that it
does not detect an encoding; `source` names the text in error messages.

## What STRio does not do

- It does not decide which kit a sample was typed with, and it does not check alleles
  against allelic ladders. That belongs to the programs that use the data.
- It does not apply analytical or stochastic thresholds; the export does not contain
  them.
- It does not yet read GeneMapper reference-profile exports or write any format. Both
  are planned; see [CHANGELOG.md](../CHANGELOG.md).
