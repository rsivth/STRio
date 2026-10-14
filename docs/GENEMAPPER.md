# GeneMapper reader reference

`strio.read_genemapper()` and `strio.parse_genemapper()` read the **Genotypes table**
that GeneMapper exports as tab-, semicolon- or comma-separated text. This page states
every rule the reader applies. The behaviour was taken over from the parser of
EPG-Renderer 0.15.1 and is pinned by the legacy suite (`tests/test_legacy_*.py`); the
section [Changes against EPG-Renderer 0.15.1](#changes-against-epg-renderer-0151) lists
what is new.

Reference-profile exports (one row per marker with all alleles in one cell) are a
different format and not yet supported.

## Decoding

1. Without `encoding`: a UTF-16 byte-order mark selects UTF-16; otherwise UTF-8 with or
   without BOM, cp1252 and latin-1 are tried in this order. latin-1 decodes any bytes,
   so an unexpected encoding fails later with a precise header or value error.
2. With `encoding`: only that encoding is used; an unknown name or undecodable bytes
   raise `ParseError`.
3. Text containing a NUL character is rejected with a hint that it may be UTF-16 without
   byte-order mark.

## Table structure

1. The delimiter is detected from the first line by recognising `Marker`, `Allele n`
   and a sample column (`Sample Name`, `Sample ID`, `Sample File`); ties go to the
   delimiter yielding more columns. An explicit delimiter must be tab, `;` or `,`.
2. CSV quoting is validated strictly: a quote inside an unquoted field, characters after
   a closing quote and unterminated quotes raise `ParseError` with the line number.
   Quoted fields may contain line breaks; reported line numbers stay physical lines.
3. Empty, unnamed columns at the end of the header are ignored (diagnostic
   `trailing-empty-columns`); data in such a column is an error. Blank column names
   elsewhere are an error.
4. Column names are compared ignoring letter case and runs of whitespace. Two columns
   with the same name ignoring case are an error, and so are two numbered columns of the
   same family and number (`Allele 1` and `Allele  1`).
5. Blank rows are skipped. A row with more non-empty fields than the header is an error;
   shorter rows are padded with empty fields.

## Columns

| Column | Required | Meaning |
| --- | --- | --- |
| sample column (`sample_id_column`, default `Sample Name`) | yes | names the sample; empty values are an error |
| `Marker` (`marker_column`) | yes | marker name; empty values are an error |
| `Dye` (`dye_column`) | no | dye of the row; empty means unknown |
| `Sample Name`, `Sample File`, `Sample ID`, `Run Name` | no | sample identity (below) |
| `Allele n` | at least one | allele label of peak `n` |
| `Height n` | yes, unless `require_height=False` | peak height in RFU, whole number ≥ 0 |
| `Size n` | no | fragment size in bp, decimal ≥ 0; a decimal comma is accepted |
| `Area n` or `Peak Area n` | no | peak area, whole number ≥ 0 |
| `Mutation n`, `Comment n` | no | free text |
| `Allele Display Overflow` or `ADO` | no | overflow flag (below); also kept as extra |
| anything else | no | kept verbatim per row in `Locus.extra` |

Numbered columns are paired by their number `n`, never by position. Numbers need not be
contiguous (`Allele 1`, `Allele 3`).

For every number `n` of a row:

- no allele and no measurement → no peak;
- measurement but no allele → `ParseError` ("Indexed peak data without allele");
- allele but no height while `require_height=True` → `ParseError`;
- a height above `max_height` → `NumericValueError`.

## Sample identity

With the default sample column `Sample Name`, rows belong to the same sample injection
only if `Sample ID`, `Run Name`, `Sample File` and `Sample Name` all agree (as far as
those columns exist). Repeated display names therefore stay separate samples; their
identifiers get the sample file, sample ID or run name in brackets, and `#2`, `#3` if
still not unique. With any other sample column, rows are grouped by that column alone.
Rows of one injection with conflicting identity values raise `ParseError`.

Within one sample, two rows whose marker names are equal ignoring case and whitespace
raise `DuplicateLocusError`. Synonyms (`AM`/`Amelogenin`) are **not** treated as
duplicates by the reader; `Sample.locus()` reports them as ambiguous instead.

## Diagnostics

| Code | When |
| --- | --- |
| `trailing-empty-columns` | rule 3 of the table structure applied |
| `allele-display-overflow` | the overflow column holds anything except empty, `0`, `false`, `no`, `n`, `none` (any case) |
| `highest-allele-column-used` | no overflow was reported, the export has at least ten allele columns and the highest one is filled in some row |

## Changes against EPG-Renderer 0.15.1

Old behaviour is the parser `epg_renderer.parser.read_genotypes_table` of EPG-Renderer
0.15.1. strio takes over its reading rules unchanged: for input the old parser accepts,
it returns the same samples, loci, alleles, identities and warning texts, and for input
it rejects, the same error message. This is pinned by recorded output for every fixture
(`tests/test_legacy_golden.py`) and the ported legacy tests. During development it was
also cross-checked in 16,220 comparisons on 4,055 inputs (fixtures, the renderer's test
inputs and generated variants) with 0 differences. Such checks cannot prove equality for
every conceivable file; a difference found later is a bug.

| Area | EPG-Renderer 0.15.1 | strio 0.1.0 |
| --- | --- | --- |
| Uninterpreted columns | discarded | kept per row in `Locus.extra`; listed in `SourceInfo.extra_columns` |
| Height ceiling | always 32,767 RFU | none by default; `max_height=32_767` restores it |
| Warnings | plain strings | `Diagnostic` objects with code, message and lines; `Dataset.messages` gives the strings |
| UTF-16 with BOM | rejected ("Could not detect CSV delimiter") | read |
| UTF-16 without BOM (NUL characters) | "Could not detect CSV delimiter" | error naming UTF-16 and the `encoding` option |
| Marker lookup | exact name | additionally `Locus.key` and `Sample.locus()` by canonical key |
| Allele interpretation | text only | text plus derived `Allele.value` |
| Text input | file only | also `parse_genemapper(text)` |
| `export_mode` | part of the project | removed; it is renderer information |
| Exception names | `GeneMapperParserError`, `MissingRequiredColumnError`, `DuplicateHeaderError`, `DuplicateMarkerError`, `NumericConversionError` | `ParseError`, `MissingColumnError`, `DuplicateColumnError`, `DuplicateLocusError`, `NumericValueError`; messages unchanged |
