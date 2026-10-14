"""New in 0.1.0: the test runner counts by test and reports both suites."""

from __future__ import annotations

import importlib.util
import io
import sys
import unittest

from _support import ROOT

_SPEC = importlib.util.spec_from_file_location("run_tests_module", ROOT / "run_tests.py")
assert _SPEC is not None and _SPEC.loader is not None
runner = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = runner
_SPEC.loader.exec_module(runner)


def _sample_case() -> type[unittest.TestCase]:
    """Build the demo case inside a function so that discovery does not collect it."""

    class _Sample(unittest.TestCase):
        def test_pass(self) -> None:
            pass

        def test_fail_twice_in_subtests(self) -> None:
            for value in (1, 2):
                with self.subTest(value=value):
                    self.assertEqual(value, 0)

        def test_error(self) -> None:
            raise RuntimeError("boom")

        @unittest.skip("not here")
        def test_skip(self) -> None:
            pass

    return _Sample


def _run(tests: list[unittest.TestCase]) -> unittest.TestResult:
    stream = io.StringIO()
    return unittest.TextTestRunner(stream=stream, verbosity=0).run(unittest.TestSuite(tests))


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        loader = unittest.defaultTestLoader
        self.tests = list(runner.iter_tests(loader.loadTestsFromTestCase(_sample_case())))
        self.summary = runner.summarize(self.tests, _run(self.tests), 0.5)

    def test_counts_are_per_test_not_per_subtest(self) -> None:
        summary = self.summary
        self.assertEqual(
            (summary.total, summary.passed, summary.failed, summary.errors, summary.skipped),
            (4, 1, 1, 1, 1),
        )
        self.assertFalse(summary.ok)

    def test_report_states_counts_problems_and_verdict(self) -> None:
        report = runner.format_report(self.summary, "9.9.9", [("mypy", "bestanden")])
        self.assertIn("strio 9.9.9", report)
        self.assertRegex(report, r"Tests gesamt\s+4")
        self.assertRegex(report, r"Fehlgeschlagen\s+1")
        self.assertIn("Ergebnis: NICHT BESTANDEN", report)
        self.assertIn("FEHLER: test_error", report)
        self.assertIn("RuntimeError: boom", report)

    def test_legacy_tests_are_counted_by_module_prefix(self) -> None:
        tests = runner.discover(ROOT)
        summary = runner.summarize(tests, unittest.TestResult(), 0.0)
        legacy = [t for t in tests if t.id().startswith("test_legacy_")]
        self.assertEqual(summary.legacy, len(legacy))
        self.assertEqual(summary.legacy + summary.current, len(tests))
        self.assertGreaterEqual(summary.legacy, 49)

    def test_failed_quality_check_fails_the_verdict(self) -> None:
        clean = runner.Summary(total=1, passed=1)
        self.assertIn("Ergebnis: BESTANDEN", runner.format_report(clean, "1.0.0", []))
        failing = runner.format_report(clean, "1.0.0", [("ruff check", "FEHLGESCHLAGEN")])
        self.assertIn("Ergebnis: NICHT BESTANDEN", failing)
        missing = runner.format_report(clean, "1.0.0", [("mypy", "nicht installiert")])
        self.assertIn("Ergebnis: BESTANDEN", missing)


if __name__ == "__main__":
    unittest.main()
