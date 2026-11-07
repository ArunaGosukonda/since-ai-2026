"""DNA Digital Security Assistant: deterministic walking skeleton (no LLM calls).

Pipeline: signals -> facts (keyword extractor) -> policy (situations.yaml) -> compose -> validate.
"""
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the read-only vendor kit
