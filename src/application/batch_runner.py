#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch Inference Runner for DNA Digital Security Assistant.
Processes data/dev/cases.jsonl or data/test/inputs.jsonl and generates
schema-compliant prediction JSONL files.
"""
import argparse
import json
import os
import sys

# Ensure repository root is on PYTHONPATH
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)

from src.data.loader import stream_inference_cases
from src.application.assistant import DigitalSecurityAssistant

def run_batch(cases_path: str, out_path: str, limit: int = 0):
    assistant = DigitalSecurityAssistant()
    count = 0
    with open(out_path, "w", encoding="utf-8") as out_f:
        for clean_case in stream_inference_cases(cases_path):
            answer = assistant.process_case(clean_case, mode="single_turn")
            out_f.write(json.dumps(answer, ensure_ascii=False) + "\n")
            count += 1
            if limit and count >= limit:
                break
    print(f"Wrote {count} predictions to {out_path}")

def main():
    parser = argparse.ArgumentParser(description="DNA Assistant Batch Prediction Runner")
    parser.add_argument("--cases", required=True, help="Path to input cases JSONL")
    parser.add_argument("--out", required=True, help="Path to output predictions JSONL")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on processed cases")
    args = parser.parse_args()
    
    run_batch(args.cases, args.out, args.limit)

if __name__ == "__main__":
    main()
