# Test provenance

The suite has two parts:

- **Legacy suite** (`tests/test_legacy_*.py`): behaviour STRio took over. Every later
  iteration must keep it passing; an exception needs a reason recorded here and in
  CHANGELOG.md.
- **Current suite** (all other `tests/test_*.py`): the behaviour introduced or changed by
  an iteration. With the next iteration it becomes part of what must keep passing.

`python run_tests.py` reports both counts.

## Legacy suite of 0.1.0: taken over from EPG-Renderer 0.15.1

Source: EPG-Renderer 0.15.1 (`b6708f1`), `tests/`. Inputs and assertions are unchanged;
only names are translated:

| EPG-Renderer | STRio |
| --- | --- |
| `load_project(path, ...)`, `read_genotypes_table(path, ...)` | `strio.read_genemapper(path, ...)` |
| `GeneMapperProject` | `Dataset` + `SourceInfo` |
| `SampleCall`, `.sample_id`, `.markers` | `Sample`, `.id`, `.loci` |
| `MarkerCall` | `Locus` |
| `AlleleCall`, `.allele_index`, `.allele` | `Allele`, `.index`, `.label` |
| `project.warnings`, `.header`, `.delimiter` | `dataset.messages`, `.source.header`, `.source.delimiter` |
| `GeneMapperParserError`, `MissingRequiredColumnError`, `DuplicateHeaderError`, `DuplicateMarkerError`, `NumericConversionError` | `ParseError`, `MissingColumnError`, `DuplicateColumnError`, `DuplicateLocusError`, `NumericValueError` |

| STRio module | Tests | Origin |
| --- | ---: | --- |
| `test_legacy_parser.py` | 28 | `test_parser.py`, all 28 tests |
| `test_legacy_parser_correctness.py` | 8 | `test_schema_and_parser_correctness.py`, class `ParserCorrectnessTests`, all 8 tests |
| `test_legacy_exports_and_limits.py` | 7 | `test_genemapper_exports.py` (3 of 6), `test_rfu_limits.py` (3 of 6), `test_batch_and_gui_regressions.py` (1 of 14) |
| `test_legacy_models.py` | 4 | `test_public_api_and_models.py`, class `ImmutableCallModelTests` (4 of 5) |
| `test_legacy_golden.py` | 2 | new: compares STRio with EPG-Renderer 0.15.1's recorded parse of all 8 fixtures (`tests/golden/`, recorded by `tools/make_legacy_golden.py`) |
| **Total** | **49** | |

### Not taken over, with reasons

| EPG-Renderer test | Reason |
| --- | --- |
| `test_genemapper_exports.py`: kit identification, rendering, kit profiles (3) | Kit and rendering behaviour stays in EPG-Renderer. |
| `test_rfu_limits.py`: `MAX_RFU` constant, manual parser, `AlleleCall` ceiling (3) | STRio deliberately has no instrument ceiling; the reader option `max_height` replaces it and is tested by the 3 ported parser tests. The renderer keeps these three tests. |
| `test_public_api_and_models.py`: `test_marker_call_no_longer_contains_unused_source_order` | Refers to a field the renderer removed; STRio never had it. |
| `test_public_api_and_models.py`: invalid `export_mode`, `origin`, `height_mode` states | These fields are renderer information and are not part of the STRio model. |
| All other parser calls in the renderer suite (kit detection, positioning, rendering) | They use the parser only to obtain input; EPG-Renderer keeps testing them after it switches to STRio. |

Changed assertions: none. Changed inputs: none.

## Current suite of 0.1.0

| Module | Covers |
| --- | --- |
| `test_extras.py` | uninterpreted columns per row, `common_extra`, `indexed_extra` |
| `test_marker_keys.py` | `marker_key`, synonyms, `Sample.locus` lookup and ambiguity |
| `test_allele_values.py` | `parse_allele_label`, `AlleleValue`, `Allele.value` |
| `test_diagnostics.py` | diagnostic codes, lines, precedence, `Diagnostic` invariants |
| `test_reader_api.py` | `parse_genemapper`, `SourceInfo`, `max_height`, UTF-16, NUL, error paths |
| `test_reader_edge_cases.py` | reader branches the legacy suite does not reach (identity fall-backs, header errors, quoting) |
| `test_model.py` | model behaviour beyond the legacy invariants |
| `test_forge_regressions.py` | inputs the Go package *forge* misreads (found by a differential comparison on 2026-10-14) |
| `test_public_api.py` | public names, version consistency, packaging metadata |
| `test_documentation.py` | executes every example in the manual; checks required documents |
| `test_run_tests.py` | the test runner's counting and report |

## Iteration 0.1.1

Previous suite: the 164 tests of 0.1.0. Run unchanged against 0.1.1: 161 passed,
1 skipped (as in 0.1.0: the unreadable-file test is skipped when the suite runs with
administrator rights), 2 failed. The two failures are intended and the tests were
changed:

| Test (`test_run_tests.py`) | Change | Reason |
| --- | --- | --- |
| `test_report_states_counts_problems_and_verdict` | expects `STRio`, `Tests run`, `Failed`, `Result: FAILED`, `ERROR:` instead of the German labels | the report is English |
| `test_failed_quality_check_fails_the_verdict` | renamed `test_quality_verdict_requires_every_tool_to_pass`; the "missing tool passes" assertion moved to the new `test_missing_quality_tool_fails_and_explains_installation`, which asserts the opposite | a requested check that did not run must not be reported as passed |

New tests in 0.1.1:

| Module | Test |
| --- | --- |
| `test_run_tests.py` | `test_skipped_tests_are_listed_with_their_reason` |
| `test_run_tests.py` | `test_every_test_module_contributes_tests` |
| `test_run_tests.py` | `test_missing_quality_tool_fails_and_explains_installation` |
| `test_run_tests.py` | `test_tools_run_with_this_interpreter_as_modules` |
| `test_run_tests.py` | `test_tool_on_path_is_used_when_it_cannot_be_imported` |
| `test_run_tests.py` | `test_tool_that_is_neither_importable_nor_on_path_is_not_installed` |
| `test_run_tests.py` | `test_failing_tool_is_reported_as_failed` |
| `test_run_tests.py` | `test_main_exit_code_is_one_when_a_requested_tool_is_missing` |
| `test_documentation.py` | `test_prose_writes_the_project_name_as_strio_brand` |

## Fixtures

`tests/fixtures/` is copied unchanged from EPG-Renderer 0.15.1 (`tests/fixtures/`).
Every fixture is synthetic; see EPG-Renderer `docs/SOURCES.md`, section "Test data
provenance". `tests/test_legacy_exports_and_limits.py` pins the SHA-256 of the two
complete exports.
