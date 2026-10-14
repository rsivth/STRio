"""New in 0.1.0: public names, version consistency and packaging metadata."""

from __future__ import annotations

import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None  # type: ignore[assignment]

from _support import ROOT

import strio


class PublicApiTests(unittest.TestCase):
    def test_every_exported_name_exists(self) -> None:
        for name in strio.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(strio, name))

    def test_core_entry_points_are_exported(self) -> None:
        expected = {
            "read_genemapper",
            "parse_genemapper",
            "Dataset",
            "Sample",
            "Locus",
            "Allele",
            "SourceInfo",
            "ParseError",
            "marker_key",
            "parse_allele_label",
            "__version__",
        }
        self.assertLessEqual(expected, set(strio.__all__))

    def test_internal_helpers_are_not_exported(self) -> None:
        for name in ("row_key", "_table", "FORMAT_NAME"):
            with self.subTest(name=name):
                self.assertNotIn(name, strio.__all__)

    def test_exceptions_form_one_hierarchy(self) -> None:
        for name in (
            "MissingColumnError",
            "DuplicateColumnError",
            "DuplicateLocusError",
            "NumericValueError",
        ):
            with self.subTest(name=name):
                self.assertTrue(issubclass(getattr(strio, name), strio.ParseError))
        self.assertTrue(issubclass(strio.ParseError, strio.StrioError))
        self.assertTrue(issubclass(strio.InconsistentExtraError, strio.StrioError))
        self.assertTrue(issubclass(strio.StrioError, ValueError))


class VersionTests(unittest.TestCase):
    def test_version_has_three_numeric_parts(self) -> None:
        self.assertRegex(strio.__version__, r"^\d+\.\d+\.\d+$")

    def test_changelog_starts_with_this_version(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first = re.search(r"^## (\S+) - (\d{4}-\d{2}-\d{2})$", changelog, re.MULTILINE)
        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.group(1), strio.__version__)

    def test_install_instructions_name_this_version(self) -> None:
        for document in ("README.md", "docs/MANUAL.md"):
            with self.subTest(document=document):
                text = (ROOT / document).read_text(encoding="utf-8")
                self.assertIn(f"@v{strio.__version__}", text)


@unittest.skipIf(tomllib is None, "tomllib needs Python 3.11")
class PackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            self.project = tomllib.load(handle)

    def test_distribution_name_and_dynamic_version(self) -> None:
        project = self.project["project"]
        self.assertEqual(project["name"], "strio-forensic")
        self.assertEqual(project["dynamic"], ["version"])
        self.assertEqual(
            self.project["tool"]["setuptools"]["dynamic"]["version"],
            {"attr": "strio.version.__version__"},
        )

    def test_no_runtime_dependencies(self) -> None:
        self.assertEqual(self.project["project"]["dependencies"], [])

    def test_type_information_is_shipped(self) -> None:
        self.assertTrue((ROOT / "src" / "strio" / "py.typed").is_file())
        self.assertIn("py.typed", self.project["tool"]["setuptools"]["package-data"]["strio"])


if __name__ == "__main__":
    unittest.main()
