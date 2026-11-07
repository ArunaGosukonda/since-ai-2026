# -*- coding: utf-8 -*-
import unittest
from src.data.loader import (
    load_jsonl,
    sanitize_for_inference,
    DEV_ONLY_KEYS,
)

class TestDataLoader(unittest.TestCase):
    def test_load_dev_cases(self):
        cases = load_jsonl("data/dev/cases.jsonl")
        self.assertEqual(len(cases), 588)
        self.assertIn("ground_truth", cases[0])

    def test_load_test_inputs(self):
        inputs = load_jsonl("data/test/inputs.jsonl")
        self.assertEqual(len(inputs), 335)
        self.assertNotIn("ground_truth", inputs[0])

    def test_sanitize_for_inference(self):
        cases = load_jsonl("data/dev/cases.jsonl")
        raw = cases[0]
        clean = sanitize_for_inference(raw)
        for key in DEV_ONLY_KEYS:
            self.assertNotIn(key, clean)
        self.assertEqual(clean["case_id"], raw["case_id"])
        self.assertIn("opening_message", clean)
        self.assertIn("signals", clean)
        self.assertIn("consent", clean)

if __name__ == "__main__":
    unittest.main()
