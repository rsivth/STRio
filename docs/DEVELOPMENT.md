# Development

## Working rules for every iteration

Each iteration (each new version) is documented and tested in three parts:

1. **Old behaviour**: what the previous version does, stated in CHANGELOG.md.
2. **New behaviour**: what changes, stated in CHANGELOG.md and in the reference pages.
3. **Test suites**:
   - the new version must pass the complete previous suite. An exception (a previous
     test changed or removed) needs a reason in CHANGELOG.md and in
     [TEST_PROVENANCE.md](TEST_PROVENANCE.md);
   - a new suite covers every change and every new behaviour.

Version numbers follow `X.Y.Z` ([Semantic Versioning](https://semver.org)). While the
major version is 0, the data model may still change: a change that breaks callers
raises `Y`; fixes and additions that break nothing raise `Z`.

## Setup

```text
git clone https://github.com/rsivth/strio
cd strio
python -m venv .venv
.venv/bin/pip install -e ".[dev]"          # Windows: .venv\Scripts\pip ...
```

STRio itself has no runtime dependencies. The `dev` extra installs ruff and mypy at the
versions EPG-Renderer pins.

## Checks

```text
python run_tests.py              # all tests, short report
python run_tests.py -v           # list every test
python run_tests.py --quality    # tests + ruff check + ruff format --check + mypy
```

`run_tests.py` works without installing the package; it puts `src/` on the path. The
report counts the tests taken over from EPG-Renderer (`tests/test_legacy_*.py`)
separately from STRio's own tests and lists every skipped test with its reason.

With `--quality`, ruff and mypy are required: they run as `python -m ruff` and
`python -m mypy` with the interpreter that runs the script, so a virtual environment
does not need to be activated (`.venv/bin/python run_tests.py --quality`; on Windows
`.venv\Scripts\python run_tests.py --quality`). If the interpreter cannot import a
tool, an executable on PATH is used; if neither exists, the tool is reported as
`NOT INSTALLED` and the run fails.

Exit code 0 means everything passed; 1 means a test or a requested check failed or a
requested tool is missing; 2 means the suite could not be loaded.

The suite is fast (well under two seconds) because it only parses small synthetic
files; `python run_tests.py -v` lists every test that ran.

## Conventions

- `src/` layout; the public API is what `strio/__init__.py` exports.
- Type hints everywhere; mypy in strict mode.
- ruff with the same rule set as EPG-Renderer; line length 100.
- Standard-library `unittest` only. Shared helpers live in `tests/_support.py`.
- Test data is synthetic. New fixtures get a provenance entry in TEST_PROVENANCE.md.
- Error messages name file, line and column wherever the input allows it.
- Every manual example is executed by `tests/test_documentation.py`; keep them true.

## Rules for writers

STRio does not write any format yet. When the first writer is added, it must not lose
genetically relevant information unnoticed:

- every writer returns or raises a report that names every field of the dataset that
  was not written (for example peak heights when writing genotypes, or extra columns a
  format has no place for);
- a writer that has to interpret data (for example peaks to genotypes) does so through
  an explicit, documented function, never implicitly while writing;
- tests read back what was written and compare it with the original, field by field.

## Release

1. Set the version in `src/strio/version.py` (the only place).
2. Add the CHANGELOG.md entry with the same version and the date.
3. `python run_tests.py --quality` must report `Result: PASSED`.
4. Commit, tag `vX.Y.Z`, push the tag.
