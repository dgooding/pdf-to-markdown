from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BatchConvertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="batch-convert-tests-"))
        self.inp = self.tmp / "input"
        self.out = self.tmp / "out"
        self.inp.mkdir(parents=True, exist_ok=True)
        self.out.mkdir(parents=True, exist_ok=True)

        (self.inp / "a.txt").write_text("hello world", encoding="utf-8")
        (self.inp / "b.md").write_text("# sample\n\ntext", encoding="utf-8")
        (self.inp / "artifacts").mkdir(parents=True, exist_ok=True)
        (self.inp / "artifacts" / "ignored.txt").write_text("ignore", encoding="utf-8")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "batch_convert.py"),
            str(self.inp),
            "--output-root",
            str(self.out),
            "--recursive",
            *args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_batch_dry_run(self) -> None:
        res = self._run("--dry-run")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["mode"], "dry_run")
        self.assertGreaterEqual(payload["count"], 2)
        self.assertFalse(any("ignored.txt" in s for s in payload["sources"]))

    def test_batch_run_and_resume(self) -> None:
        res = self._run("--force")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        state = json.loads((self.out / "batch-state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(state["summary"]["ok"], 2)

        res2 = self._run("--resume")
        self.assertEqual(res2.returncode, 0, res2.stdout + res2.stderr)
        state2 = json.loads((self.out / "batch-state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(state2["summary"]["skipped"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
