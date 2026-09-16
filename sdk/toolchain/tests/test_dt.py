from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DT = REPO_ROOT / "dt"
SAMPLE = REPO_ROOT / "samples" / "hello" / "main.dt"


class DtCliTests(unittest.TestCase):
    def run_dt(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DT), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_help(self) -> None:
        result = self.run_dt("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Dark Tower Language (DTL) prototype CLI", result.stdout)

    def test_run_sample(self) -> None:
        result = self.run_dt("run", str(SAMPLE))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello, Dark Tower!\n")

    def test_build_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "hello.dtb"
            result = self.run_dt("build", str(SAMPLE), "-o", str(artifact))
            self.assertEqual(result.returncode, 0)
            self.assertTrue(artifact.exists())

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "dtl-prototype-v0.2")
            self.assertEqual(payload["prints"], ["Hello, Dark Tower!\n"])

    def test_run_and_build_unicode_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "unicode.dt"
            source.write_text('fn main() { print("café ☕\\n"); }', encoding="utf-8")

            run_result = self.run_dt("run", str(source))
            self.assertEqual(run_result.returncode, 0)
            self.assertEqual(run_result.stdout, "café ☕\n")

            artifact = Path(tmp_dir) / "unicode.dtb"
            build_result = self.run_dt("build", str(source), "-o", str(artifact))
            self.assertEqual(build_result.returncode, 0)

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["prints"], ["café ☕\n"])

    def test_run_missing_source(self) -> None:
        missing = REPO_ROOT / "samples" / "hello" / "does-not-exist.dt"
        result = self.run_dt("run", str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertIn("error: source file not found", result.stderr)

    def test_build_without_print_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "empty-output.dt"
            source.write_text("fn main() {}", encoding="utf-8")
            artifact = Path(tmp_dir) / "empty-output.dtb"

            result = self.run_dt("build", str(source), "-o", str(artifact))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: no runnable output found", result.stderr)

    def test_run_escaped_string_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "escaped.dt"
            source.write_text('fn main() { print("line1\\nline2\\"ok\\"\\n"); }', encoding="utf-8")
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, 'line1\nline2"ok"\n')

    def test_run_invalid_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "invalid-escape.dt"
            source.write_text('fn main() { print("bad\\q"); }', encoding="utf-8")
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: invalid string literal", result.stderr)

    def test_build_invalid_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "invalid-escape.dt"
            source.write_text('fn main() { print("bad\\q"); }', encoding="utf-8")
            artifact = Path(tmp_dir) / "invalid-escape.dtb"
            result = self.run_dt("build", str(source), "-o", str(artifact))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: invalid string literal", result.stderr)

    def test_build_output_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "hello.dt"
            source.write_text('fn main() { print("ok\\\\n"); }', encoding="utf-8")
            output_dir = Path(tmp_dir) / "artifact-dir"
            output_dir.mkdir()

            result = self.run_dt("build", str(source), "-o", str(output_dir))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: output path is not a regular file", result.stderr)

    def test_run_non_utf8_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "non-utf8.dt"
            source.write_bytes(b'fn main() { print("' + bytes([0xFF]) + b'"); }')
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: source file is not valid UTF-8", result.stderr)

    def test_build_non_utf8_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "non-utf8.dt"
            source.write_bytes(b'fn main() { print("' + bytes([0xFF]) + b'"); }')
            artifact = Path(tmp_dir) / "non-utf8.dtb"
            result = self.run_dt("build", str(source), "-o", str(artifact))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: source file is not valid UTF-8", result.stderr)

    def test_run_ignores_print_inside_string_literal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "nested-print.dt"
            source.write_text('fn main() { print("print(\\"x\\");\\n"); }', encoding="utf-8")
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, 'print("x");\n')


if __name__ == "__main__":
    unittest.main()
