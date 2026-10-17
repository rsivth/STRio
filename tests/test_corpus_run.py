"""New in 0.2.2: ``run_tests.py --corpus DIR`` reads every real export in a local folder.

docs/DEVELOPMENT.md, section "Real exports", describes the run; docs/TEST_PROVENANCE.md,
section 0.2.2, lists these tests.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import ROOT

import strio

_SPEC = importlib.util.spec_from_file_location("run_tests_corpus", ROOT / "run_tests.py")
assert _SPEC is not None and _SPEC.loader is not None
runner = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = runner
_SPEC.loader.exec_module(runner)

GOOD = "Sample Name\tMarker\tAllele 1\tHeight 1\nCASE-4711\tvWA\t14\t100\n"
BAD_HEIGHT = "Sample Name\tMarker\tAllele 1\tHeight 1\nCASE-4711\tvWA\t14\t9z9\n"


class _Folder:
    """A temporary corpus folder outside the repository."""

    def __init__(self, files: dict[str, str]) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="strio-corpus-")
        self.path = Path(self._directory.name)
        for name, text in files.items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def snapshot(self) -> list[tuple[str, int, int]]:
        return sorted(
            (path.relative_to(self.path).as_posix(), path.stat().st_mtime_ns, path.stat().st_size)
            for path in self.path.rglob("*")
        )

    def close(self) -> None:
        self._directory.cleanup()


def _main(*arguments: str) -> tuple[int, str]:
    with (
        mock.patch.object(runner, "discover", return_value=[]),
        mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
    ):
        code = runner.main(list(arguments))
    return code, stdout.getvalue()


class CorpusFolderTests(unittest.TestCase):
    def test_a_folder_inside_the_repository_is_refused(self) -> None:
        for folder in (ROOT, ROOT / "tests" / "fixtures"):
            with (
                self.subTest(folder=folder),
                self.assertRaisesRegex(runner.CorpusFolderError, "inside the repository"),
            ):
                runner.corpus_files(folder)
        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(runner.main(["--corpus", str(ROOT / "tests")]), 2)
        self.assertIn("keep real exports outside it", stderr.getvalue())

    def test_a_missing_folder_stops_the_run_before_the_tests(self) -> None:
        with (
            mock.patch.object(runner, "discover") as discover,
            mock.patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(runner.main(["--corpus", "/no/such/strio/corpus"]), 2)
        discover.assert_not_called()

    def test_export_files_are_found_recursively_and_others_are_counted(self) -> None:
        folder = _Folder(
            {
                "b.txt": GOOD,
                "a/run.TSV": GOOD,
                "a/c.csv": GOOD,
                "notes.docx": "x",
                ".hidden.txt": GOOD,
                ".git/x.txt": GOOD,
            }
        )
        self.addCleanup(folder.close)
        exports, others = runner.corpus_files(folder.path)
        names = [path.relative_to(folder.path).as_posix() for path in exports]
        self.assertEqual(names, ["a/c.csv", "a/run.TSV", "b.txt"])
        self.assertEqual(others, 1)

    def test_a_folder_reached_through_a_symbolic_link_keeps_its_given_path(self) -> None:
        # macOS: tempfile folders under /var are links to /private/var.
        folder = _Folder({"a/c.csv": GOOD, "b.txt": GOOD})
        self.addCleanup(folder.close)
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "corpus-link"
            link.symlink_to(folder.path, target_is_directory=True)
            exports, _ = runner.corpus_files(link)
            self.assertEqual(
                [path.relative_to(link).as_posix() for path in exports], ["a/c.csv", "b.txt"]
            )
            result = runner.run_corpus(link)
        self.assertEqual([item.name for item in result.files], ["a/c.csv", "b.txt"])
        self.assertTrue(result.ok)

    def test_a_link_from_outside_into_the_repository_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "looks-outside"
            link.symlink_to(ROOT / "tests" / "fixtures", target_is_directory=True)
            with self.assertRaisesRegex(runner.CorpusFolderError, "inside the repository"):
                runner.corpus_files(link)

    def test_shareable_needs_a_corpus(self) -> None:
        with (
            mock.patch("sys.stderr", new_callable=io.StringIO),
            self.assertRaises(SystemExit) as caught,
        ):
            runner.main(["--shareable"])
        self.assertEqual(caught.exception.code, 2)


class CorpusOutcomeTests(unittest.TestCase):
    def _folder(self, files: dict[str, str]) -> _Folder:
        folder = _Folder(files)
        self.addCleanup(folder.close)
        return folder

    def test_readable_files_pass_and_are_described_by_counts(self) -> None:
        folder = self._folder({"good.txt": GOOD})
        code, report = _main("--corpus", str(folder.path))
        self.assertEqual(code, 0)
        self.assertIn("read     good.txt  tab, utf-8-sig · 1 sample, 1 locus, 1 allele", report)
        self.assertRegex(report, r"Corpus files\s+1\n  read\s+1\n  rejected\s+0\n  crashed\s+0")
        self.assertIn("Result: PASSED", report)
        self.assertNotIn("CASE-4711", report)

    def test_a_rejected_file_fails_the_run_and_shows_the_message(self) -> None:
        folder = self._folder({"good.txt": GOOD, "bad.txt": BAD_HEIGHT})
        code, report = _main("--corpus", str(folder.path))
        self.assertEqual(code, 1)
        self.assertIn(
            "REJECTED bad.txt   NumericValueError: Invalid integer RFU value '9z9'", report
        )
        self.assertIn("Result: FAILED", report)
        self.assertIn(runner.PRIVACY_HINT, report)

    def test_an_unexpected_exception_is_a_crash_with_its_code_location(self) -> None:
        folder = self._folder({"good.txt": GOOD})
        with mock.patch.object(strio, "read_genemapper", side_effect=IndexError("boom")):
            result = runner.run_corpus(folder.path)
        self.assertEqual(result.count(runner.CRASHED), 1)
        self.assertRegex(result.files[0].detail, r"IndexError: boom \(at .+:\d+\)")
        self.assertFalse(result.ok)

    def test_a_folder_without_exports_fails(self) -> None:
        folder = self._folder({"notes.docx": "x"})
        code, report = _main("--corpus", str(folder.path))
        self.assertEqual(code, 1)
        self.assertIn("no .txt, .tsv, .csv files found", report)

    def test_the_corpus_folder_is_not_changed(self) -> None:
        folder = self._folder({"good.txt": GOOD, "bad.txt": BAD_HEIGHT, "x/y.csv": GOOD})
        before = folder.snapshot()
        _main("--corpus", str(folder.path))
        self.assertEqual(folder.snapshot(), before)

    def test_shareable_report_hides_names_paths_and_messages(self) -> None:
        folder = self._folder({"CASE-4711_batch.txt": GOOD, "CASE-4712.txt": BAD_HEIGHT})
        code, report = _main("--corpus", str(folder.path), "--shareable")
        self.assertEqual(code, 1)
        for secret in ("CASE-4711", "CASE-4712", "9z9", str(folder.path)):
            self.assertNotIn(secret, report)
        self.assertIn("REJECTED file 2  NumericValueError at line 2", report)
        self.assertIn("read     file 1  tab", report)
        self.assertNotIn(runner.PRIVACY_HINT, report)

    def test_notes_name_diagnostics_unknown_labels_and_ambiguous_delimiters(self) -> None:
        ambiguous = (
            "Sample Name;Marker;Allele 1;Height 1;X,Sample Name,Marker,Allele 1,Height 1\n"
            "S;vWA;14;100;x,S,vWA,15,200\n"
        )
        unknown = "Sample Name\tMarker\tAllele 1\tHeight 1\nS\tvWA\t?\t100\n"
        folder = self._folder({"ambiguous.csv": ambiguous, "unknown.txt": unknown})
        result = runner.run_corpus(folder.path)
        notes = {item.name: item.notes for item in result.files}
        self.assertEqual(notes["ambiguous.csv"], ["also readable with delimiter comma"])
        self.assertEqual(notes["unknown.txt"], ["1 allele label of unknown kind: '?'"])
        shared = runner.run_corpus(folder.path, shareable=True)
        self.assertEqual(shared.files[1].notes, ["1 allele label of unknown kind"])
        self.assertTrue(result.ok)

    def test_corpus_lines_come_before_the_block_that_ends_with_the_verdict(self) -> None:
        folder = self._folder({"good.txt": GOOD})
        _, report = _main("--corpus", str(folder.path))
        self.assertLess(report.index("Corpus: "), report.index("=" * 50))
        self.assertLess(report.index("Corpus files"), report.index("Result: PASSED"))


if __name__ == "__main__":
    unittest.main()
