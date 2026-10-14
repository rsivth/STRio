"""New in 0.1.0: the documentation exists, links resolve and examples are true."""

from __future__ import annotations

import doctest
import os
import re
import unittest
from pathlib import Path

from _support import ROOT

REQUIRED = (
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "docs/MANUAL.md",
    "docs/GENEMAPPER.md",
    "docs/DATA_MODEL.md",
    "docs/DEVELOPMENT.md",
    "docs/TEST_PROVENANCE.md",
)
_LINK = re.compile(r"\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")
_LOWERCASE_NAME = re.compile(r"(?<![\w/.\-])strio(?![\w/\-]|\.[a-zA-Z_])")


def _prose_lines(path: Path) -> list[tuple[int, str]]:
    """Return the lines of a Markdown file outside code, with inline code removed."""

    lines: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or stripped.startswith((">>>", "...")):
            continue
        prose = re.sub(r"`[^`]*`", "", line)
        prose = re.sub(r"\]\([^)]*\)", "]", prose)
        lines.append((number, prose))
    return lines


class DocumentationTests(unittest.TestCase):
    def test_required_documents_exist(self) -> None:
        for name in REQUIRED:
            with self.subTest(name=name):
                self.assertTrue((ROOT / name).is_file())

    def test_relative_links_resolve(self) -> None:
        for name in REQUIRED:
            if not name.endswith(".md"):
                continue
            document = ROOT / name
            for target in _LINK.findall(document.read_text(encoding="utf-8")):
                with self.subTest(document=name, target=target):
                    self.assertTrue((document.parent / target).exists())

    def test_manual_examples_produce_the_shown_output(self) -> None:
        previous = os.getcwd()
        os.chdir(ROOT)
        try:
            result = doctest.testfile(
                str(ROOT / "docs" / "MANUAL.md"),
                module_relative=False,
                optionflags=doctest.ELLIPSIS,
                verbose=False,
                report=True,
            )
        finally:
            os.chdir(previous)
        self.assertGreater(result.attempted, 20)
        self.assertEqual(result.failed, 0)

    def test_prose_writes_the_project_name_as_strio_brand(self) -> None:
        self.assertTrue((ROOT / "README.md").read_text(encoding="utf-8").startswith("# STRio\n"))
        for name in REQUIRED:
            if not name.endswith(".md"):
                continue
            for number, prose in _prose_lines(ROOT / name):
                with self.subTest(document=name, line=number):
                    self.assertIsNone(_LOWERCASE_NAME.search(prose), prose)

    def test_every_legacy_module_is_listed_in_the_provenance(self) -> None:
        provenance = (ROOT / "docs" / "TEST_PROVENANCE.md").read_text(encoding="utf-8")
        for module in sorted((ROOT / "tests").glob("test_*.py")):
            with self.subTest(module=module.name):
                listed = f"`{module.name}`" in provenance
                self.assertTrue(listed, f"{module.name} is missing in docs/TEST_PROVENANCE.md")


if __name__ == "__main__":
    unittest.main()
