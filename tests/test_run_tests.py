"""The test runner counts by test, reports both suites and runs the quality tools.

Introduced in 0.1.0; changed in 0.1.1 (English report; a requested quality tool that is
not installed now fails the run; tools run as ``python -m``). See docs/TEST_PROVENANCE.md.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from unittest import mock

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
        report = runner.format_report(self.summary, "9.9.9", [("mypy --strict", "passed")])
        self.assertIn("STRio 9.9.9", report)
        self.assertRegex(report, r"Tests run\s+4")
        self.assertRegex(report, r"Failed\s+1")
        self.assertIn("Result: FAILED", report)
        self.assertIn("ERROR: test_error", report)
        self.assertIn("RuntimeError: boom", report)

    def test_skipped_tests_are_listed_with_their_reason(self) -> None:
        report = runner.format_report(self.summary, "9.9.9", [])
        self.assertIn("SKIPPED: test_skip", report)
        self.assertIn("not here", report)

    def test_legacy_tests_are_counted_by_module_prefix(self) -> None:
        tests = runner.discover(ROOT)
        summary = runner.summarize(tests, unittest.TestResult(), 0.0)
        legacy = [t for t in tests if t.id().startswith("test_legacy_")]
        self.assertEqual(summary.legacy, len(legacy))
        self.assertEqual(summary.legacy + summary.current, len(tests))
        self.assertGreaterEqual(summary.legacy, 49)

    def test_every_test_module_contributes_tests(self) -> None:
        discovered = {test.id().split(".", 1)[0] for test in runner.discover(ROOT)}
        modules = {path.stem for path in (ROOT / "tests").glob("test*.py")}
        self.assertEqual(discovered, modules)

    def test_quality_verdict_requires_every_tool_to_pass(self) -> None:
        clean = runner.Summary(total=1, passed=1)
        self.assertIn("Result: PASSED", runner.format_report(clean, "1.0.0", []))
        passing = [("ruff check", runner.PASSED), ("mypy --strict", runner.PASSED)]
        self.assertIn("Result: PASSED", runner.format_report(clean, "1.0.0", passing))
        failing = runner.format_report(clean, "1.0.0", [("ruff check", runner.FAILED)])
        self.assertIn("Result: FAILED", failing)

    def test_missing_quality_tool_fails_and_explains_installation(self) -> None:
        clean = runner.Summary(total=1, passed=1)
        report = runner.format_report(clean, "1.0.0", [("mypy --strict", runner.NOT_INSTALLED)])
        self.assertIn("Result: FAILED", report)
        self.assertIn('pip install -e ".[dev]"', report)


class QualityToolTests(unittest.TestCase):
    def test_tools_run_with_this_interpreter_as_modules(self) -> None:
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(runner.importlib.util, "find_spec", return_value=object()),
            mock.patch.object(runner.subprocess, "run", return_value=completed) as run,
        ):
            results = runner.run_quality_checks(ROOT)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][:3], [sys.executable, "-m", "ruff"])
        self.assertEqual(commands[2][:3], [sys.executable, "-m", "mypy"])
        self.assertEqual([status for _, status in results], [runner.PASSED] * 3)

    def test_tool_on_path_is_used_when_it_cannot_be_imported(self) -> None:
        with (
            mock.patch.object(runner.importlib.util, "find_spec", return_value=None),
            mock.patch.object(runner.shutil, "which", return_value="/opt/bin/mypy"),
        ):
            self.assertEqual(runner.tool_command("mypy"), ["/opt/bin/mypy"])

    def test_tool_that_is_neither_importable_nor_on_path_is_not_installed(self) -> None:
        with (
            mock.patch.object(runner.importlib.util, "find_spec", return_value=None),
            mock.patch.object(runner.shutil, "which", return_value=None),
            mock.patch.object(runner.subprocess, "run") as run,
        ):
            results = runner.run_quality_checks(ROOT)
        run.assert_not_called()
        self.assertEqual([status for _, status in results], [runner.NOT_INSTALLED] * 3)

    def test_failing_tool_is_reported_as_failed(self) -> None:
        completed = mock.Mock(returncode=1, stdout="E501", stderr="")
        with (
            mock.patch.object(runner.importlib.util, "find_spec", return_value=object()),
            mock.patch.object(runner.subprocess, "run", return_value=completed),
            mock.patch("sys.stderr", new_callable=io.StringIO),
        ):
            results = runner.run_quality_checks(ROOT)
        self.assertEqual([status for _, status in results], [runner.FAILED] * 3)

    def test_main_exit_code_is_one_when_a_requested_tool_is_missing(self) -> None:
        clean = runner.Summary(total=1, passed=1)
        missing = [("mypy --strict", runner.NOT_INSTALLED)]
        with (
            mock.patch.object(runner, "discover", return_value=[]),
            mock.patch.object(runner, "summarize", return_value=clean),
            mock.patch.object(runner, "run_quality_checks", return_value=missing),
            mock.patch("sys.stdout", new_callable=io.StringIO),
        ):
            self.assertEqual(runner.main(["--quality"]), 1)
            self.assertEqual(runner.main([]), 0)


if __name__ == "__main__":
    unittest.main()
