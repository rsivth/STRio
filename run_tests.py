"""Run the complete strio test suite and print a short report.

Usage::

    python run_tests.py              # all tests, short report
    python run_tests.py -v           # additionally list every test
    python run_tests.py --quality    # additionally run ruff and mypy if installed

The report separates the legacy suite (``tests/test_legacy_*.py``: behaviour taken over
from earlier versions or from EPG-Renderer) from the tests of the current iteration.
Exit code: 0 = everything passed, 1 = a test or quality check failed, 2 = the suite
could not be discovered.
"""

from __future__ import annotations

import argparse
import io
import platform
import shutil
import subprocess
import sys
import time
import unittest
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEGACY_PREFIX = "test_legacy_"


@dataclass
class Summary:
    """Counts of one test run, by test (not by sub-test)."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    expected_failures: int = 0
    unexpected_successes: int = 0
    legacy: int = 0
    current: int = 0
    duration: float = 0.0
    problems: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether no test failed, errored or passed unexpectedly."""

        return not (self.failed or self.errors or self.unexpected_successes)


def iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    """Yield every test case of a possibly nested suite."""

    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def discover(root: Path = ROOT) -> list[unittest.TestCase]:
    """Discover every ``tests/test*.py`` test exactly once."""

    for entry in (root / "tests", root / "src"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    suite = unittest.defaultTestLoader.discover(
        str(root / "tests"), pattern="test*.py", top_level_dir=str(root / "tests")
    )
    tests = list(iter_tests(suite))
    failed_imports = [test for test in tests if type(test).__name__ == "_FailedTest"]
    if failed_imports:
        names = ", ".join(test.id() for test in failed_imports)
        raise RuntimeError(f"Test modules could not be imported: {names}")
    ids = [test.id() for test in tests]
    if len(ids) != len(set(ids)):
        duplicates = sorted({test_id for test_id in ids if ids.count(test_id) > 1})
        raise RuntimeError(f"Duplicate test IDs: {duplicates}")
    return tests


def _base_id(test: object) -> str:
    owner = getattr(test, "test_case", test)
    return str(owner.id()) if hasattr(owner, "id") else str(owner)


def _first_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""


def summarize(
    tests: list[unittest.TestCase], result: unittest.TestResult, duration: float
) -> Summary:
    """Build the report counts from a finished run."""

    summary = Summary(total=len(tests), duration=duration)
    summary.legacy = sum(1 for test in tests if test.id().startswith(LEGACY_PREFIX))
    summary.current = summary.total - summary.legacy
    failed = {_base_id(test) for test, _ in result.failures}
    errored = {_base_id(test) for test, _ in result.errors} - failed
    skipped = {_base_id(test) for test, _ in result.skipped} - failed - errored
    expected = {_base_id(test) for test, _ in result.expectedFailures}
    unexpected = {_base_id(test) for test in result.unexpectedSuccesses}
    summary.failed = len(failed)
    summary.errors = len(errored)
    summary.skipped = len(skipped)
    summary.expected_failures = len(expected)
    summary.unexpected_successes = len(unexpected)
    summary.passed = summary.total - len(failed | errored | skipped | expected | unexpected)
    for label, entries in (("FEHLGESCHLAGEN", result.failures), ("FEHLER", result.errors)):
        for test, trace in entries:
            summary.problems.append((label, str(test), _first_line(trace)))
    for test in result.unexpectedSuccesses:
        summary.problems.append(("UNERWARTET BESTANDEN", str(test), ""))
    return summary


def format_report(summary: Summary, version: str, quality: list[tuple[str, str]]) -> str:
    """Return the short human-readable report."""

    width = 46
    lines = [
        "=" * width,
        f"strio {version} · Python {platform.python_version()}",
        "-" * width,
        f"Tests gesamt        {summary.total:>6}",
        f"  Altbestand        {summary.legacy:>6}   (tests/test_legacy_*.py)",
        f"  aktuelle Iteration{summary.current:>6}",
        "-" * width,
        f"Bestanden           {summary.passed:>6}",
        f"Fehlgeschlagen      {summary.failed:>6}",
        f"Fehler              {summary.errors:>6}",
        f"Übersprungen        {summary.skipped:>6}",
    ]
    if summary.expected_failures or summary.unexpected_successes:
        lines.append(f"Erwartet fehlgeschl.{summary.expected_failures:>6}")
        lines.append(f"Unerwartet bestanden{summary.unexpected_successes:>5}")
    lines.append(f"Dauer               {summary.duration:>6.2f} s")
    for name, status in quality:
        lines.append(f"{name:<20}{status}")
    lines.append("-" * width)
    quality_ok = all(status in {"bestanden", "nicht installiert"} for _, status in quality)
    verdict = "BESTANDEN" if summary.ok and quality_ok else "NICHT BESTANDEN"
    lines.append(f"Ergebnis: {verdict}")
    lines.append("=" * width)
    for label, test, message in summary.problems:
        lines.append(f"{label}: {test}")
        if message:
            lines.append(f"    {message}")
    return "\n".join(lines)


def run_quality_checks(root: Path = ROOT) -> list[tuple[str, str]]:
    """Run ruff and mypy when installed; return (name, status) pairs."""

    checks = (
        ("ruff check", ["ruff", "check", "src", "tests", "run_tests.py", "tools"]),
        ("ruff format", ["ruff", "format", "--check", "src", "tests", "run_tests.py", "tools"]),
        ("mypy", ["mypy"]),
    )
    results: list[tuple[str, str]] = []
    for name, command in checks:
        if shutil.which(command[0]) is None:
            results.append((name, "nicht installiert"))
            continue
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        status = "bestanden" if completed.returncode == 0 else "FEHLGESCHLAGEN"
        results.append((name, status))
        if completed.returncode != 0:
            print(completed.stdout + completed.stderr, file=sys.stderr)
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the suite and print the report."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="list every test")
    parser.add_argument("--quality", action="store_true", help="also run ruff and mypy")
    args = parser.parse_args(argv)

    try:
        tests = discover()
    except RuntimeError as exc:
        print(f"Testsuite konnte nicht geladen werden: {exc}", file=sys.stderr)
        return 2
    from strio.version import __version__

    stream = sys.stdout if args.verbose else io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2 if args.verbose else 0)
    start = time.perf_counter()
    result = runner.run(unittest.TestSuite(tests))
    summary = summarize(tests, result, time.perf_counter() - start)
    quality = run_quality_checks() if args.quality else []
    if args.verbose:
        print()
    print(format_report(summary, __version__, quality))
    quality_ok = all(status in {"bestanden", "nicht installiert"} for _, status in quality)
    return 0 if summary.ok and quality_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
