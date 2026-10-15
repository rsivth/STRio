# Changelog

All notable changes to STRio. Versions follow `X.Y.Z` (see docs/DEVELOPMENT.md).

## 0.1.2 - 2026-10-15

Fixes the findings of an external code review of 0.1.1. The data model and the API are
unchanged.

### Old behaviour

- A height, area or size with more than 4,300 digits raised a plain `ValueError`
  (Python 3.11 and later) instead of `NumericValueError`. EPG-Renderer 0.15.1 had
  rejected such values correctly; the regression came with the move to STRio.
- Column names that differ only in spacing (`Sample Name`, `Sample  Name`) were
  accepted, although the reader treats them as the same column; the second was
  silently ignored.
- Digits of other scripts were read as numbers (`١٢٣` → 123, allele `٩.٣` → 9.3), and
  sizes in exponent notation were read (`1e2` → 100).
- Numeric error messages named a canonical column (`'Area 1'` for `Peak Area 1`) and
  quoted the complete value, however long.
- `utf-8` was tried after `utf-8-sig`, which already reads UTF-8 without BOM.
- docs/DEVELOPMENT.md asked for the verdict `BESTANDEN`, which the runner no longer
  prints.

### New behaviour

- Heights, areas and the whole-number part of sizes have at most 18 digits; longer
  values raise `NumericValueError` on every Python version. Column numbers have at most
  six digits.
- Column names equal ignoring case and spacing raise `DuplicateColumnError`.
- Only ASCII digits are numbers; sizes are plain decimals (`160`, `160.5`, `160,5`).
- Error messages name the column as spelled in the export and shorten long values.
- The encoding list is `utf-8-sig`, `cp1252`, `latin-1` (same results as before).
- The release step names `Result: PASSED`.
- ruff checks cyclomatic complexity (C90, at most 12).

### Tests

- Previous suite (0.1.1): 173 tests, all pass unchanged against 0.1.2 (1 skipped as
  before).
- New: `tests/test_hardening.py`, one class per review finding.

## 0.1.1 - 2026-10-14

A maintenance release: the test runner is English and checks the development tools
reliably; the documentation writes the project name as STRio. The library itself is
unchanged.

### Old behaviour

- `run_tests.py` printed its report in German.
- `run_tests.py --quality` looked for `ruff` and `mypy` only as programs on PATH. In a
  virtual environment that was not activated, installed tools were reported as "nicht
  installiert", and the run still ended with "BESTANDEN".
- Skipped tests were counted but not named.
- The documentation wrote the project name in lower case.

### New behaviour

- The report is in English (`Tests run`, `Passed`, `Failed`, ..., `Result: PASSED`).
- Quality tools run as `python -m ruff` / `python -m mypy` with the interpreter that runs
  the script; an executable on PATH is the fallback.
- A requested quality tool that is not installed fails the run (`NOT INSTALLED`,
  `Result: FAILED`, exit code 1) and the report says how to install it.
- Every skipped test is listed with its reason.
- Prose in README, documentation and code docstrings writes **STRio**; the import name
  `strio` and the distribution name `strio-forensic` are unchanged.
- `.gitattributes` keeps `LICENSE` with LF line endings and `py.typed` byte-exact, so a
  Windows checkout can be compared byte for byte with the copy bundled in EPG-Renderer.

### Tests

- Previous suite (0.1.0): 164 tests. Run unchanged against 0.1.1, 161 pass, 1 is
  skipped as before, and 2 tests of `tests/test_run_tests.py` fail because they assert
  the German report and the old rule that a missing tool still passes. Both were
  changed deliberately (docs/TEST_PROVENANCE.md, section 0.1.1).
- New tests cover the English report, the listing of skipped tests, the interpreter-
  based tool invocation, the PATH fallback, the failing verdict and exit code for a
  missing tool, that every test module contributes tests, and the STRio spelling.

## 0.1.0 - 2026-10-14

First version. STRio takes over the GeneMapper parser of EPG-Renderer 0.15.1 as a
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
