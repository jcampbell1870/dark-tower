from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DT = REPO_ROOT / "dt"
HELLO_FILE = REPO_ROOT / "samples" / "hello" / "main.dt"
HELLO_PROJECT = REPO_ROOT / "samples" / "hello"
CRYPTO_CHESS_PROJECT = REPO_ROOT / "samples" / "crypto-chess"


class DtCliTests(unittest.TestCase):
    def run_dt(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DT), *args],
            check=False,
            capture_output=True,
            text=True,
            cwd=cwd,
        )

    def test_help(self) -> None:
        result = self.run_dt("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Dark Tower Language (DTL) prototype CLI", result.stdout)
        self.assertIn("test", result.stdout)
        self.assertIn("init", result.stdout)

    def test_run_sample_file(self) -> None:
        result = self.run_dt("run", str(HELLO_FILE))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello, Dark Tower!\n")

    def test_run_sample_project_directory(self) -> None:
        result = self.run_dt("run", str(HELLO_PROJECT))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello, Dark Tower!\n")

    def test_run_sample_project_from_cwd(self) -> None:
        result = self.run_dt("run", cwd=HELLO_PROJECT)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello, Dark Tower!\n")

    def test_build_sample_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "hello.dtb"
            result = self.run_dt("build", str(HELLO_PROJECT), "-o", str(artifact), "--target", "linux-x64")
            self.assertEqual(result.returncode, 0)
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "dtl-prototype-v0.3")
            self.assertEqual(payload["package"]["name"], "hello")
            self.assertEqual(payload["functions"], ["main"])
            self.assertEqual(payload["target"], "linux-x64")

    def test_run_interpreted_language_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "features.dt"
            source.write_text(
                """
fn accumulate(limit) {
  let total = 0;
  let current = 1;
  while current <= limit {
    if current % 2 == 0 {
      total = total + current;
    }
    current = current + 1;
  }
  return total;
}

fn main() {
  let values = ["sum", to_string(accumulate(6))];
  println(join(values, ": "));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "sum: 12\n")

    def test_run_supports_nested_list_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "board.dt"
            source.write_text(
                """
fn main() {
  let board = [[".", "."], [".", "."]];
  board[0][1] = "K";
  println(join(board[0], ""));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, ".K\n")

    def test_while_loop_reuses_block_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "loop-scope.dt"
            source.write_text(
                """
fn main() {
  let i = 0;
  while i < 3 {
    let carry = i;
    if carry < 2 {
      i = carry + 1;
    } else {
      i = 3;
    }
  }
  println(to_string(i));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "3\n")

    def test_logical_operators_return_operand_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "logic.dt"
            source.write_text(
                """
fn main() {
  println(to_string(0 || 5));
  println(("left" && "right"));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "5\nright\n")

    def test_test_command_runs_annotated_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = Path(tmp_dir) / "project"
            (project / "src").mkdir(parents=True)
            (project / "DarkTower.toml").write_text(
                "[package]\nname = \"tests\"\nversion = \"0.1.0\"\nedition = \"2026\"\n",
                encoding="utf-8",
            )
            (project / "src" / "main.dt").write_text(
                """
fn add(a, b) {
  return a + b;
}

@test
fn addition_works() {
  assert_eq(add(2, 3), 5);
}

fn main() {
  println("ok");
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_dt("test", str(project))
            self.assertEqual(result.returncode, 0)
            self.assertIn("ok addition_works", result.stdout)
            self.assertIn("1/1 tests passed", result.stdout)

    def test_init_creates_project_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self.run_dt("init", str(Path(tmp_dir) / "demo"))
            self.assertEqual(result.returncode, 0)
            project = Path(tmp_dir) / "demo"
            self.assertTrue((project / "DarkTower.toml").exists())
            self.assertTrue((project / "src" / "main.dt").exists())

    def test_invalid_string_escape_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "invalid-escape.dt"
            source.write_text('fn main() { println("bad\\q"); }', encoding="utf-8")
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error:", result.stderr)
            self.assertIn("invalid string literal", result.stderr)

    def test_run_missing_source(self) -> None:
        missing = REPO_ROOT / "samples" / "hello" / "does-not-exist.dt"
        result = self.run_dt("run", str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertIn("error: source file not found", result.stderr)

    def test_run_non_utf8_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "non-utf8.dt"
            source.write_bytes(b'fn main() { println("' + bytes([0xFF]) + b'"); }')
            result = self.run_dt("run", str(source))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error: source file is not valid UTF-8", result.stderr)

    def test_crypto_chess_sample_runs(self) -> None:
        result = self.run_dt("run", str(CRYPTO_CHESS_PROJECT))
        self.assertEqual(result.returncode, 0)
        self.assertIn("Crypto Chess opening demo", result.stdout)
        self.assertIn("position hash:", result.stdout)
        self.assertIn("reward score:", result.stdout)

    def test_crypto_chess_tests_pass(self) -> None:
        result = self.run_dt("test", str(CRYPTO_CHESS_PROJECT))
        self.assertEqual(result.returncode, 0)
        self.assertIn("2/2 tests passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
