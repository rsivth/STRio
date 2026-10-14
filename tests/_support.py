"""Shared helpers for the STRio test suite (not a test module)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
EXPORTS = FIXTURES / "genemapper_exports"
RFU_LIMIT = 32_767
"""Height ceiling EPG-Renderer applies; used where renderer behaviour is ported."""


def write_temp(
    case: unittest.TestCase,
    text: str,
    *,
    encoding: str = "utf-8",
    suffix: str = ".csv",
    newline: str | None = None,
) -> Path:
    """Write ``text`` to a temporary file that is removed after the test."""

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
        path = Path(temporary.name)
    with path.open("w", encoding=encoding, newline=newline) as handle:
        handle.write(text)
    case.addCleanup(path.unlink, missing_ok=True)
    return path


def write_bytes(case: unittest.TestCase, data: bytes, *, suffix: str = ".txt") -> Path:
    """Write raw bytes to a temporary file that is removed after the test."""

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
        path = Path(temporary.name)
    path.write_bytes(data)
    case.addCleanup(path.unlink, missing_ok=True)
    return path
