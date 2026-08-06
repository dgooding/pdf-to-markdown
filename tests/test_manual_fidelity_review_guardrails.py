from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import unittest
from pathlib import Path

from fidelity_review_tools import redact_metadata


class ManualFidelityReviewGuardrailTests(unittest.TestCase):
    def test_confidential_metadata_redaction(self) -> None:
        redacted = redact_metadata(r"C:\\Users\\A083101\\Secret\\pilot\\doc1.pdf")
        self.assertEqual(redacted, "doc1.pdf")

    def test_no_conversion_algorithm_file_mutation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app_py = root / "app.py"
        conv_py = root / "convert_to_md.py"

        def sha(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        a1, c1 = sha(app_py), sha(conv_py)
        # invoke review-only helper operation
        _ = redact_metadata(str(app_py))
        a2, c2 = sha(app_py), sha(conv_py)

        self.assertEqual(a1, a2)
        self.assertEqual(c1, c2)

    def test_port_8012_not_auto_started(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            self.assertNotEqual(s.connect_ex(("127.0.0.1", 8012)), 0)
        finally:
            s.close()

    def test_human_review_packet_generated_with_17_fixtures_and_blank_fields(self) -> None:
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["C:/Python39/python.exe", "run_manual_fidelity_review.py"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)

        run_dir = None
        for line in proc.stdout.splitlines():
            if line.startswith("REVIEW_RUN_DIR "):
                run_dir = Path(line.split(" ", 1)[1].strip())
                break
        self.assertIsNotNone(run_dir)

        packet_path = run_dir / "summaries" / "human-review-packet.json"
        self.assertTrue(packet_path.exists())
        payload = json.loads(packet_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload.get("fixtures", [])), 17)

        first = payload["fixtures"][0]
        h = first["blank_human_fields"]
        self.assertEqual(h["reviewer"], "")
        self.assertIsNone(h["human_review_minutes"])
        self.assertIsNone(h["human_cleanup_minutes"])

        summary_path = run_dir / "review-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["calibration"]["agreement_status"], "pending_human_review")

    def test_real_pilot_waiting_when_intake_empty(self) -> None:
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["C:/Python39/python.exe", "run_manual_fidelity_review.py"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        run_dir = None
        for line in proc.stdout.splitlines():
            if line.startswith("REVIEW_RUN_DIR "):
                run_dir = Path(line.split(" ", 1)[1].strip())
                break
        self.assertIsNotNone(run_dir)

        run_manifest = json.loads((run_dir / "review-run.json").read_text(encoding="utf-8"))
        self.assertEqual(run_manifest["real_document_pilot_status"], "waiting_for_approved_inputs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
