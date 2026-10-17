"""Run the complete STRio test suite and print a short report.

Usage::

    python run_tests.py                     # all tests, short report
    python run_tests.py -v                  # additionally list every test
    python run_tests.py --quality           # additionally run ruff and mypy (required then)
    python run_tests.py --corpus DIR        # additionally read every export in DIR
    python run_tests.py --corpus DIR --shareable   # the same, without names and messages

The report separates the tests taken over from EPG-Renderer (``tests/test_legacy_*.py``)
from STRio's own tests. Quality tools are run with the same Python interpreter as this
script (``python -m ruff`` / ``python -m mypy``), so they are found in a virtual
environment even when it is not activated; only if the interpreter cannot import a tool,
an executable of that name on PATH is used.

The corpus run reads every ``.txt``, ``.tsv`` and ``.csv`` file below ``DIR`` with the
default options of :func:`strio.read_genemapper`. It is meant for real exports that must
not enter the repository: ``DIR`` has to lie outside it and nothing is written there.
The report shows counts, not data; but it names the files and quotes error messages,
which can contain a sample name or a value. ``--shareable`` replaces names by numbers
and messages by error types. See ``docs/DEVELOPMENT.md``, section "Real exports".

Exit code: 0 = everything passed, 1 = a test, quality check or corpus file failed or a
requested quality tool is not installed, 2 = the suite could not be discovered or the
corpus folder is unusable.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import unittest
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import strio

ROOT = Path(__file__).resolve().parent
LEGACY_PREFIX = "test_legacy_"
LINT_TARGETS = ("src", "tests", "run_tests.py", "tools")
PASSED = "passed"
FAILED = "FAILED"
NOT_INSTALLED = "NOT INSTALLED"
INSTALL_HINT = 'Install the development tools with: python -m pip install -e ".[dev]"'
CORPUS_SUFFIXES = (".txt", ".tsv", ".csv")
READ = "read"
REJECTED = "REJECTED"
CRASHED = "CRASHED"
DELIMITER_NAMES = {"\t": "tab", ";": "semicolon", ",": "comma"}
PRIVACY_HINT = (
    "This report names your files and quotes error messages, which can contain sample "
    "names or values. Add --shareable before passing it on."
)


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


def _last_line(text: str) -> str:
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
    for label, entries in (("FAILED", result.failures), ("ERROR", result.errors)):
        for test, trace in entries:
            summary.problems.append((label, str(test), _last_line(trace)))
    for test in result.unexpectedSuccesses:
        summary.problems.append(("UNEXPECTED SUCCESS", str(test), ""))
    for test, reason in result.skipped:
        summary.problems.append(("SKIPPED", str(test), reason))
    return summary


def quality_ok(quality: list[tuple[str, str]]) -> bool:
    """Return whether every requested quality check ran and passed."""

    return all(status == PASSED for _, status in quality)


@dataclass
class CorpusFile:
    """Outcome of reading one file of the corpus."""

    name: str
    status: str
    detail: str
    notes: list[str] = field(default_factory=list)


@dataclass
class CorpusResult:
    """Outcome of the corpus run."""

    folder: Path
    files: list[CorpusFile] = field(default_factory=list)
    other_files: int = 0
    duration: float = 0.0
    shareable: bool = False

    def count(self, status: str) -> int:
        """Return how many files ended with ``status``."""

        return sum(1 for item in self.files if item.status == status)

    @property
    def ok(self) -> bool:
        """Return whether there were files and every one of them was read."""

        return bool(self.files) and self.count(READ) == len(self.files)


class CorpusFolderError(Exception):
    """The corpus folder cannot be used."""


def corpus_files(folder: Path, root: Path = ROOT) -> tuple[list[Path], int]:
    """Return the export files below ``folder`` in name order and the number of others.

    Hidden files and folders are left out. A folder inside the repository is refused so
    that real exports cannot be committed by accident.
    """

    resolved = folder.expanduser().resolve()
    if not resolved.is_dir():
        raise CorpusFolderError(f"Corpus folder does not exist: {folder}")
    if resolved.is_relative_to(root.resolve()):
        raise CorpusFolderError(
            f"Corpus folder {folder} lies inside the repository; keep real exports outside it."
        )
    exports: list[Path] = []
    others = 0
    for path in sorted(resolved.rglob("*")):
        relative = path.relative_to(resolved)
        if any(part.startswith(".") for part in relative.parts) or not path.is_file():
            continue
        if path.suffix.casefold() in CORPUS_SUFFIXES:
            exports.append(path)
        else:
            others += 1
    return exports, others


def _code_location(exc: BaseException) -> str:
    """Return the innermost line of the traceback that lies in the STRio package."""

    import strio

    package = Path(strio.__file__).resolve().parent
    frames = traceback.extract_tb(exc.__traceback__)
    inside = [frame for frame in frames if Path(frame.filename).resolve().is_relative_to(package)]
    if not inside:
        return f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "unknown"
    frame = inside[-1]
    relative = Path(frame.filename).resolve().relative_to(package.parent).as_posix()
    return f"{relative}:{frame.lineno}"


def _error_type(exc: BaseException) -> str:
    """Return the exception type with the line it names, for shareable reports."""

    found = re.search(r"\bline (\d+)", str(exc))
    return type(exc).__name__ + (f" at line {found.group(1)}" if found else "")


def _read_notes(path: Path, dataset: strio.Dataset, shareable: bool) -> list[str]:
    """Return remarks about a file that was read: findings that need no action now."""

    import strio

    notes: list[str] = []
    codes = Counter(diagnostic.code.value for diagnostic in dataset.diagnostics)
    notes.extend(f"diagnostic {code} ({count}x)" for code, count in sorted(codes.items()))
    unknown = Counter(
        allele.label
        for sample in dataset.samples.values()
        for locus in sample.loci.values()
        for allele in locus.alleles
        if allele.value.kind is strio.AlleleKind.OTHER
    )
    if unknown:
        labels = "" if shareable else ": " + ", ".join(repr(label) for label in sorted(unknown))
        notes.append(
            _count(sum(unknown.values()), "allele label", "allele labels")
            + f" of unknown kind{labels}"
        )
    table = dataset.source.require_table()
    for delimiter in DELIMITER_NAMES:
        if delimiter == table.delimiter:
            continue
        try:
            other = strio.read_genemapper(
                path, delimiter=delimiter, encoding=dataset.source.encoding
            )
        except Exception:  # noqa: BLE001 - any failure means the delimiter does not fit
            continue
        if other.samples:
            notes.append(f"also readable with delimiter {DELIMITER_NAMES[delimiter]}")
    if not dataset.samples:
        notes.append("no samples")
    return notes


def _count(number: int, singular: str, plural: str) -> str:
    return f"{number} {singular if number == 1 else plural}"


def check_corpus_file(path: Path, name: str, shareable: bool = False) -> CorpusFile:
    """Read one export and describe the outcome without quoting any data values."""

    import strio

    try:
        dataset = strio.read_genemapper(path)
    except strio.StrioError as exc:
        detail = _error_type(exc) if shareable else f"{type(exc).__name__}: {exc}"
        return CorpusFile(name, REJECTED, detail)
    except Exception as exc:  # noqa: BLE001 - any other exception is a STRio bug
        return _crashed(name, exc, shareable)
    try:
        return CorpusFile(name, READ, _describe(dataset), _read_notes(path, dataset, shareable))
    except Exception as exc:  # noqa: BLE001 - the data model broke a promise
        return _crashed(name, exc, shareable)


def _crashed(name: str, exc: Exception, shareable: bool) -> CorpusFile:
    message = _error_type(exc) if shareable else f"{type(exc).__name__}: {exc}"
    return CorpusFile(name, CRASHED, f"{message} (at {_code_location(exc)})")


def _describe(dataset: strio.Dataset) -> str:
    """Return the format and the counts of a dataset that was read."""

    table = dataset.source.require_table()
    loci = [locus for sample in dataset.samples.values() for locus in sample.loci.values()]
    counts = (
        _count(len(dataset.samples), "sample", "samples"),
        _count(len(loci), "locus", "loci"),
        _count(sum(len(locus.alleles) for locus in loci), "allele", "alleles"),
        _count(len(table.extra_columns), "extra column", "extra columns"),
    )
    delimiter = DELIMITER_NAMES.get(table.delimiter, repr(table.delimiter))
    return f"{delimiter}, {dataset.source.encoding} · " + ", ".join(counts)


def run_corpus(folder: Path, shareable: bool = False, root: Path = ROOT) -> CorpusResult:
    """Read every export below ``folder``; raise :class:`CorpusFolderError` if unusable."""

    exports, others = corpus_files(folder, root)
    result = CorpusResult(folder, other_files=others, shareable=shareable)
    start = time.perf_counter()
    base = folder.expanduser().resolve()
    for number, path in enumerate(exports, start=1):
        name = f"file {number}" if shareable else path.relative_to(base).as_posix()
        result.files.append(check_corpus_file(path, name, shareable))
    result.duration = time.perf_counter() - start
    return result


def format_corpus(corpus: CorpusResult) -> list[str]:
    """Return the per-file lines of the corpus run."""

    folder = "<corpus folder>" if corpus.shareable else str(corpus.folder)
    lines = [f"Corpus: {folder}"]
    width = max((len(item.name) for item in corpus.files), default=0)
    for item in corpus.files:
        lines.append(f"  {item.status:<9}{item.name:<{width}}  {item.detail}")
        lines.extend(f"  {'':<9}{'':<{width}}  note: {note}" for note in item.notes)
    if not corpus.files:
        lines.append(f"  no {', '.join(CORPUS_SUFFIXES)} files found")
    return lines


def format_report(
    summary: Summary,
    version: str,
    quality: list[tuple[str, str]],
    corpus: CorpusResult | None = None,
) -> str:
    """Return the short human-readable report."""

    width = 50
    lines = format_corpus(corpus) if corpus is not None else []
    lines += [
        "=" * width,
        f"STRio {version} · Python {platform.python_version()}",
        "-" * width,
        f"Tests run              {summary.total:>6}",
        f"  taken over           {summary.legacy:>6}   (tests/test_legacy_*.py)",
        f"  STRio's own          {summary.current:>6}",
        "-" * width,
        f"Passed                 {summary.passed:>6}",
        f"Failed                 {summary.failed:>6}",
        f"Errors                 {summary.errors:>6}",
        f"Skipped                {summary.skipped:>6}",
    ]
    if summary.expected_failures or summary.unexpected_successes:
        lines.append(f"Expected failures      {summary.expected_failures:>6}")
        lines.append(f"Unexpected successes   {summary.unexpected_successes:>6}")
    lines.append(f"Duration               {summary.duration:>6.2f} s")
    for name, status in quality:
        lines.append(f"{name:<23}{status}")
    if corpus is not None:
        lines.extend(_corpus_counts(corpus))
    lines.append("-" * width)
    corpus_ok = corpus is None or corpus.ok
    verdict = "PASSED" if summary.ok and quality_ok(quality) and corpus_ok else "FAILED"
    lines.append(f"Result: {verdict}")
    lines.append("=" * width)
    for label, test, message in summary.problems:
        lines.append(f"{label}: {test}")
        if message:
            lines.append(f"    {message}")
    if any(status == NOT_INSTALLED for _, status in quality):
        lines.append(INSTALL_HINT)
    if corpus is not None and not corpus.shareable:
        lines.append(PRIVACY_HINT)
    return "\n".join(lines)


def _corpus_counts(corpus: CorpusResult) -> list[str]:
    """Return the corpus lines of the summary block."""

    return [
        "-" * 50,
        f"Corpus files           {len(corpus.files):>6}",
        f"  read                 {corpus.count(READ):>6}",
        f"  rejected             {corpus.count(REJECTED):>6}",
        f"  crashed              {corpus.count(CRASHED):>6}",
        f"Other files skipped    {corpus.other_files:>6}",
        f"Corpus duration        {corpus.duration:>6.2f} s",
    ]


def tool_command(module: str) -> list[str] | None:
    """Return the command that runs a quality tool, or ``None`` if it is not installed."""

    if importlib.util.find_spec(module) is not None:
        return [sys.executable, "-m", module]
    executable = shutil.which(module)
    return [executable] if executable else None


def run_quality_checks(root: Path = ROOT) -> list[tuple[str, str]]:
    """Run ruff and mypy; return (name, status) pairs."""

    checks = (
        ("ruff check", "ruff", ("check", *LINT_TARGETS)),
        ("ruff format --check", "ruff", ("format", "--check", *LINT_TARGETS)),
        ("mypy --strict", "mypy", ()),
    )
    results: list[tuple[str, str]] = []
    for name, module, arguments in checks:
        command = tool_command(module)
        if command is None:
            results.append((name, NOT_INSTALLED))
            continue
        completed = subprocess.run(
            [*command, *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        results.append((name, PASSED if completed.returncode == 0 else FAILED))
        if completed.returncode != 0:
            print(completed.stdout + completed.stderr, file=sys.stderr)
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the suite and print the report."""

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("-v", "--verbose", action="store_true", help="list every test")
    parser.add_argument("--quality", action="store_true", help="also run ruff and mypy")
    parser.add_argument(
        "--corpus", type=Path, metavar="DIR", help="also read every export below DIR"
    )
    parser.add_argument(
        "--shareable",
        action="store_true",
        help="number the corpus files and show only error types",
    )
    args = parser.parse_args(argv)
    if args.shareable and args.corpus is None:
        parser.error("--shareable requires --corpus")

    try:
        if args.corpus is not None:
            corpus_files(args.corpus)
        tests = discover()
    except (RuntimeError, CorpusFolderError) as exc:
        print(f"The test run could not start: {exc}", file=sys.stderr)
        return 2
    from strio.version import __version__

    stream = sys.stdout if args.verbose else io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2 if args.verbose else 0)
    start = time.perf_counter()
    result = runner.run(unittest.TestSuite(tests))
    summary = summarize(tests, result, time.perf_counter() - start)
    quality = run_quality_checks() if args.quality else []
    corpus = run_corpus(args.corpus, args.shareable) if args.corpus is not None else None
    if args.verbose:
        print()
    print(format_report(summary, __version__, quality, corpus))
    corpus_ok = corpus is None or corpus.ok
    return 0 if summary.ok and quality_ok(quality) and corpus_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
