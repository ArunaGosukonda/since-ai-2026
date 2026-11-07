# -*- coding: utf-8 -*-
"""Integration test for Interactive Demo UI."""
import io
import unittest
from contextlib import redirect_stdout
from dsakit.scoring import load_jsonl
from src.application.demo_ui import run_cli_demo, SAMPLE_CASES_PATH

class TestDemoUI(unittest.TestCase):
    def test_run_cli_demo(self):
        cases = load_jsonl(SAMPLE_CASES_PATH)
        self.assertEqual(len(cases), 5)
        
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_cli_demo(cases)
            
        out = buf.getvalue()
        self.assertIn("SINCE AI — DNA DIGITAL SECURITY ASSISTANT", out)
        self.assertIn("[1/5] JOURNEY: SUSPICIOUS_MESSAGE", out)
        self.assertIn("[2/5] JOURNEY: CLICKED_LINK", out)
        self.assertIn("[3/5] JOURNEY: SUSPICIOUS_CALL", out)
        self.assertIn("[4/5] JOURNEY: BREACH_NOTICE", out)
        self.assertIn("[5/5] JOURNEY: SMB_INCIDENT", out)
        self.assertIn("SAFETY DECISION SUMMARY", out)

if __name__ == "__main__":
    unittest.main()
