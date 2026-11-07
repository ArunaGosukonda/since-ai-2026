# -*- coding: utf-8 -*-
"""Data loading, sanitization, and schema validation module for DNA SimSet v2.0.1.
Enforces strict exclusion of ground truth and simulation facts from runtime inference.
"""
import copy
import json
import os
from typing import Any, Dict, Generator, List

DEV_ONLY_KEYS = {
    "ground_truth",
    "simulation",
    "split",
    "tags",
    "difficulty",
    "scenario_family",
    "title",
    "holdout_family",
}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSON Lines file into a list of dicts."""
    records = []
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num} of {path}: {e}")
    return records


def sanitize_for_inference(case: Dict[str, Any]) -> Dict[str, Any]:
    """Strip all development-only fields from a case dictionary.
    Returns a pristine case object containing strictly permitted inference fields.
    """
    clean_case = copy.deepcopy(case)
    for key in DEV_ONLY_KEYS:
        clean_case.pop(key, None)
    return clean_case


def stream_inference_cases(path: str) -> Generator[Dict[str, Any], None, None]:
    """Stream cases from path, ensuring every case is sanitized for inference."""
    for case in load_jsonl(path):
        yield sanitize_for_inference(case)


def load_dev_with_ground_truth(path: str) -> List[Dict[str, Any]]:
    """Load dev cases with ground truth strictly for evaluation and analysis."""
    cases = load_jsonl(path)
    for c in cases:
        if "ground_truth" not in c:
            raise ValueError(f"Case {c.get('case_id')} lacks required ground_truth")
    return cases
