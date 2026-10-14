# Changelog

All notable changes to strio. Versions follow `X.Y.Z` (see docs/DEVELOPMENT.md).

## 0.1.0 - 2026-10-14

First version. strio takes over the GeneMapper parser of EPG-Renderer 0.15.1 as a
separate package with a format-neutral data model, so that EPG-Renderer and future
statistics modules read exports in one way.

### Old behaviour

The parser `epg_renderer.parser.read_genotypes_table` of EPG-Renderer 0.15.1. It reads
GeneMapper genotype tables (tab, `;`, `,`; UTF-8, cp1252, latin-1), pairs numbered
columns by name, keeps repeated sample names apart as separate injections, rejects
malformed input with line numbers, enforces 32,767 RFU and discards every column it does
not interpret.

### New behaviour

- **Same reading:** `strio.read_genemapper` applies the old reading rules unchanged and
  returns the same samples, loci, alleles, identities, warning texts and error messages
  (pinned by recorded output for every fixture; see docs/GENEMAPPER.md).
- **Extra columns are kept:** every column the reader does not interpret is stored per
  row in `Locus.extra`; `SourceInfo.extra_columns` lists them;
  `Sample.common_extra()` returns a value shared by all rows of a sample;
  `Locus.indexed_extra()` pairs a numbered column such as `Data Point n` with an allele.
- **Neutral model:** `Dataset`, `Sample`, `Locus`, `Allele`, `SourceInfo`. The renderer
  fields `export_mode`, `origin`, `height_mode` and `position_allele` are not part of it.
- **Height ceiling is optional:** no ceiling by default; `max_height=32_767` gives the
  renderer's behaviour.
- **Marker keys:** `Locus.key`, `strio.marker_key()` and `Sample.locus()` find a marker
  regardless of case, spacing and a short list of documented synonyms.
- **Allele interpretation:** `Allele.value` classifies each label as numeric (with
  `full_repeats` / `partial_bases`), X, Y, off-ladder or other, without guessing.
- **Diagnostics:** warnings are `Diagnostic` objects with a stable code and the source
  lines; `Dataset.messages` returns the texts.
- **UTF-16:** files with a UTF-16 byte-order mark are read; text with NUL characters is
  rejected with a message that names UTF-16 and the `encoding` option.
- **Text input:** `strio.parse_genemapper(text)`.
- **Exceptions renamed** (messages unchanged): `ParseError`, `MissingColumnError`,
  `DuplicateColumnError`, `DuplicateLocusError`, `NumericValueError`; new
  `InconsistentExtraError`. All derive from `ValueError`.

### Tests

- Legacy suite: 49 tests taken over from EPG-Renderer 0.15.1 or recording its output
  (docs/TEST_PROVENANCE.md lists origin and the tests not taken over, with reasons).
- Current suite: tests for every new behaviour above.
- `run_tests.py` runs everything and prints a short report.

### Known limitations

- GeneMapper reference-profile exports are not read yet (no example export available).
- No writer yet.
- Python 3.10 is declared but was not available in the development environment;
  the suite ran on Python 3.11, 3.12 and 3.13.
