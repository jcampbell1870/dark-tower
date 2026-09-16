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
    def test_help(self) -> None:
        result = subprocess.run([str(DT), "--help"], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Dark Tower Language (DTL) prototype CLI", result.stdout)

    def test_run_sample(self) -> None:
        result = subprocess.run([str(DT), "run", str(SAMPLE)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "Hello, Dark Tower!\n")

    def test_build_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "hello.dtb"
            result = subprocess.run(
                [str(DT), "build", str(SAMPLE), "-o", str(artifact)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(artifact.exists())

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "dtl-prototype-v0.2")
            self.assertEqual(payload["prints"], ["Hello, Dark Tower!\n"])


if __name__ == "__main__":
    unittest.main()
