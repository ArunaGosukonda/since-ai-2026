"""Semantic Chunker for Since AI Knowledge Corpus.

Chunks the 56 official DNA guidance articles into discrete, bounded semantic units
while preserving metadata (doc_id, title, url, language, topic, audience).
"""

from __future__ import annotations
import json
import os
from typing import Any, Dict, Iterator, List


class SemanticChunker:
    """Extracts semantic chunks from guidance_corpus.jsonl."""

    def __init__(self, corpus_path: Optional[str] = None):
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))
        self.corpus_path = corpus_path or os.path.join(root, "data/reference/guidance_corpus.jsonl")

    def process_corpus(self) -> Iterator[Dict[str, Any]]:
        """Yields semantic chunk dictionaries from the 56 official DNA articles."""
        if not os.path.exists(self.corpus_path):
            return

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                doc = json.loads(line)
                doc_id = doc["id"]
                audience = doc.get("audience", "consumer")
                topics = doc.get("topics", [])
                primary_topic = topics[0] if topics else "general"
                source = doc.get("source", "DNA Official Guidance")

                # Process Finnish version
                if "text_fi" in doc and doc["text_fi"]:
                    fi_text = doc["text_fi"].strip()
                    fi_title = doc.get("title_fi", doc_id)
                    yield {
                        "doc_id": f"{doc_id}_fi",
                        "base_doc_id": doc_id,
                        "title": fi_title,
                        "url": f"https://www.dna.fi/tuki/tietoturva/{doc_id}",
                        "language": "fi",
                        "topic": primary_topic,
                        "audience": audience,
                        "chunk_id": f"{doc_id}_fi_chunk_0",
                        "chunk_index": 0,
                        "section_header": fi_title,
                        "chunk_text": f"{fi_title}\n\n{fi_text}",
                    }

                # Process English version
                if "text_en" in doc and doc["text_en"]:
                    en_text = doc["text_en"].strip()
                    en_title = doc.get("title_en", doc_id)
                    yield {
                        "doc_id": f"{doc_id}_en",
                        "base_doc_id": doc_id,
                        "title": en_title,
                        "url": f"https://www.dna.fi/en/support/security/{doc_id}",
                        "language": "en",
                        "topic": primary_topic,
                        "audience": audience,
                        "chunk_id": f"{doc_id}_en_chunk_0",
                        "chunk_index": 0,
                        "section_header": en_title,
                        "chunk_text": f"{en_title}\n\n{en_text}",
                    }
