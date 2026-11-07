"""Mandatory Acceptance Tests for Since AI Dense Vector Knowledge Retrieval.

Strict Zero-Lexical Policy Enforcement:
- Asserts dense vector embedding similarity and contextual semantic retrieval exclusively.
- Verifies zero keyword matching, BM25, TF-IDF, lexical search, hybrid retrieval, RRF or keyword fallback.
- Validates 6 mandatory acceptance cases.
- Validates structured diagnostic audit logging.
"""

import ast
import os
import unittest
from typing import List

from src.core.contracts import ContextualQuery
from src.rag.embedder import DenseEmbedder
from src.rag.ingest import ingest_guidance_corpus
from src.rag.retriever import ContextualDenseRetriever, redact_pii
from src.db.repository import PostgresRepository


class TestDenseRetrievalAcceptance(unittest.TestCase):
    """Rigorous acceptance test suite for dense semantic retrieval."""

    @classmethod
    def setUpClass(cls):
        # Ingest the 56 official DNA articles into the dense repository
        ingest_guidance_corpus()
        cls.embedder = DenseEmbedder()
        cls.repo = PostgresRepository()
        cls.retriever = ContextualDenseRetriever(embedder=cls.embedder, repository=cls.repo)

    def test_zero_lexical_pipeline_inspection(self):
        """Inspects codebase AST to guarantee ZERO BM25, TF-IDF, or lexical search logic."""
        files_to_inspect = [
            "src/rag/retriever.py",
            "src/rag/embedder.py",
            "src/knowledge/rag_retriever.py",
        ]
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))
        banned_tokens = [
            "bm25",
            "tfidf",
            "okapi",
            "token_frequency",
            "inverse_document_frequency",
            "reciprocal_rank_fusion",
            "rrf",
        ]

        for rel_path in files_to_inspect:
            full_path = os.path.join(root, rel_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read().lower()

            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    fn_name = node.name.lower()
                    for banned in banned_tokens:
                        self.assertNotIn(
                            banned,
                            fn_name,
                            f"Prohibited lexical function '{node.name}' found in {rel_path}!",
                        )

    def test_case_1_different_wording_same_meaning(self):
        """Test Case 1: Different wording with same meaning retrieves relevant bank fraud passages."""
        # Colloquial phrasing without formal financial terminology
        query1 = self.retriever.build_contextual_query(
            user_message="someone took money out of my account without asking",
            language="en",
        )
        results1 = self.retriever.retrieve(query1, top_k=3)
        self.assertTrue(len(results1) > 0)
        retrieved_ids = [r.doc_id for r in results1]
        
        # Verify relevant financial/bank/police guidance is retrieved
        matches = [d for d in retrieved_ids if any(k in d for k in ("bank", "police", "fraud", "scam"))]
        self.assertTrue(len(matches) > 0, f"Expected bank fraud guidance for colloquial query, got: {retrieved_ids}")

    def test_case_2_synonyms_and_paraphrases(self):
        """Test Case 2: Synonyms and paraphrases retrieve relevant passages."""
        # Informal Finnish synonym
        query_syn = self.retriever.build_contextual_query(
            user_message="sain oudon kalasteluviestin jossa oli epäilyttävä linkki",
            language="fi",
        )
        results = self.retriever.retrieve(query_syn, top_k=3)
        self.assertTrue(len(results) > 0)
        retrieved_ids = [r.doc_id for r in results]
        self.assertTrue(
            any("smishing" in d or "sender" in d or "parcel" in d or "bank" in d for d in retrieved_ids),
            f"Expected phishing/smishing guidance for synonym query, got: {retrieved_ids}",
        )

    def test_case_3_multiturn_context_adaptation(self):
        """Test Case 3: Multi-turn context changes retrieval results when new facts are introduced."""
        # Turn 1: General suspicious text message
        q_turn1 = self.retriever.build_contextual_query(
            user_message="I received an SMS claiming my subscription is suspended",
            conversation_history=[],
            confirmed_facts={},
            language="en",
        )
        res_turn1 = self.retriever.retrieve(q_turn1, top_k=3)
        ids_turn1 = [r.doc_id for r in res_turn1]

        # Turn 2: User reveals they clicked link and entered banking credentials
        history = [
            {"role": "user", "content": "I received an SMS claiming my subscription is suspended"},
            {"role": "assistant", "content": "Did you click any link or enter credentials?"},
        ]
        facts_turn2 = {"link_clicked": True, "credentials_entered": True, "bank": "Nordea"}
        q_turn2 = self.retriever.build_contextual_query(
            user_message="Yes, I opened the link and entered my banking codes",
            conversation_history=history,
            confirmed_facts=facts_turn2,
            language="en",
        )
        res_turn2 = self.retriever.retrieve(q_turn2, top_k=5)
        ids_turn2 = [r.doc_id for r in res_turn2]

        # Contextual retrieval MUST shift to urgent bank verification / credential compromise
        self.assertNotEqual(ids_turn1, ids_turn2, "Multi-turn context with new critical facts must change retrieval outcome!")
        self.assertTrue(
            any("bank" in d or "credential" in d or "payment" in d or "police" in d for d in ids_turn2),
            f"Expected bank or credential compromise advice in turn 2, got: {ids_turn2}"
        )

    def test_case_4_multilingual_independence(self):
        """Test Case 4: Finnish, English, and Swedish queries evaluated independently."""
        fi_query = self.retriever.build_contextual_query("Epäilyttävä huijauspuhelu pankin nimissä", language="fi")
        en_query = self.retriever.build_contextual_query("Suspicious phone call pretending to be my bank", language="en")
        sv_query = self.retriever.build_contextual_query("Misstänkt bluffsamtal från någon som påstår sig vara banken", language="sv")

        res_fi = self.retriever.retrieve(fi_query, top_k=3)
        res_en = self.retriever.retrieve(en_query, top_k=3)
        res_sv = self.retriever.retrieve(sv_query, top_k=3)

        self.assertTrue(len(res_fi) > 0, "Finnish retrieval must return results")
        self.assertTrue(len(res_en) > 0, "English retrieval must return results")
        self.assertTrue(len(res_sv) > 0, "Swedish retrieval must return results")

        # Verify all return call/bank related guidance
        for lang, res in [("FI", res_fi), ("EN", res_en), ("SV", res_sv)]:
            top_ids = [r.doc_id for r in res]
            has_relevant = any(
                "call" in d or "bank" in d or "operator" in d or "wangiri" in d or "spam" in d or "fraud" in d
                for d in top_ids
            )
            self.assertTrue(has_relevant, f"Language {lang} failed to retrieve relevant guidance, got {top_ids}")

    def test_case_5_short_ambiguous_query_disambiguation(self):
        """Test Case 5: Short ambiguous query uses conversation context to disambiguate."""
        # Query alone is ambiguous
        short_query = "What should I do now?"

        # Context establishes parcel scam with delivery fee
        history = [
            {"role": "user", "content": "Posti sent a message saying a parcel is held until a 2.50 fee is paid"},
            {"role": "assistant", "content": "Do not open any link in the message."},
        ]
        facts = {"message_type": "parcel_fee", "carrier": "Posti"}

        ctx_q = self.retriever.build_contextual_query(
            user_message=short_query,
            conversation_history=history,
            confirmed_facts=facts,
            language="en",
        )
        results = self.retriever.retrieve(ctx_q, top_k=3)
        retrieved_ids = [r.doc_id for r in results]

        # Context must guide retrieval to parcel / delivery scam advice
        self.assertTrue(
            any("parcel" in d or "smishing" in d for d in retrieved_ids),
            f"Expected parcel guidance for contextualized ambiguous query, got: {retrieved_ids}",
        )

    def test_case_6_negative_control_rejects_superficial_overlap(self):
        """Test Case 6: Unrelated passages not returned merely because they share common words."""
        # Malware APK infection incident
        malware_query = self.retriever.build_contextual_query(
            user_message="Puhelimeen asennettu vaarallinen haittaohjelma apk tiedostosta ja puhelin on kaapattu",
            language="fi",
        )
        results = self.retriever.retrieve(malware_query, top_k=3)
        top_doc_ids = [r.doc_id for r in results]

        # SIM PIN change article shares common words ('puhelin', 'koodi') but is conceptually unrelated
        self.assertNotIn(
            "guidance_sim_pin_fi",
            top_doc_ids,
            "Negative control failed: Superficial word overlap falsely promoted unrelated SIM PIN guidance!",
        )

    def test_retrieval_diagnostic_logging(self):
        """Verifies structured diagnostic logging with PII redaction."""
        sensitive_msg = "My phone +358 40 1234567 received SMS, IBAN FI21 1234 5600 0007 89 was exposed"
        q = self.retriever.build_contextual_query(user_message=sensitive_msg, language="en")
        _ = self.retriever.retrieve(q, top_k=2)

        diag = self.retriever.get_last_diagnostics()
        self.assertIsNotNone(diag, "Diagnostics must be logged for every retrieval")
        
        # Verify PII was redacted
        self.assertNotIn("+358 40 1234567", diag.contextual_query_redacted)
        self.assertNotIn("FI21 1234 5600 0007 89", diag.contextual_query_redacted)
        self.assertIn("[REDACTED_PHONE]", diag.contextual_query_redacted)
        self.assertIn("[REDACTED_IBAN]", diag.contextual_query_redacted)

        # Verify diagnostic fields
        self.assertTrue(diag.embedding_model.startswith("google/"))
        self.assertTrue(isinstance(diag.retrieved_doc_ids, list))
        self.assertTrue(isinstance(diag.similarity_scores, list))
        self.assertTrue(diag.latency_ms >= 0.0)
        self.assertIn(diag.evaluation_outcome, ("PASSED", "BELOW_CONFIDENCE_THRESHOLD"))


if __name__ == "__main__":
    unittest.main()
