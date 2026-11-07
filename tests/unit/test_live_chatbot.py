# -*- coding: utf-8 -*-
"""Unit tests for Grounded RAG Retriever and Live Chatbot."""
import unittest
import uuid
from src.knowledge.rag_retriever import GuidanceRAGRetriever
from src.conversation.live_chatbot import LiveChatbot

class TestLiveChatbot(unittest.TestCase):
    def setUp(self):
        self.rag = GuidanceRAGRetriever()
        self.bot = LiveChatbot()

    def test_rag_retrieval(self):
        docs = self.rag.retrieve("pakettimaksu linkki posti", top_k=3)
        self.assertGreater(len(docs), 0)
        self.assertTrue(any(d["id"].startswith("guidance_") for d in docs))

    def test_live_chatbot_multi_turn(self):
        sid = f"test-unit-{uuid.uuid4().hex[:6]}"
        # Turn 1: user asks about a caller asking for a code
        resp1 = self.bot.handle_user_message(sid, "Joku soitti operaattorilta ja pyysi koodia.")
        self.assertEqual(resp1["reply_type"], "question")
        self.assertIn("koodi", resp1["text"].lower())

        # Turn 2: user replies
        resp2 = self.bot.handle_user_message(sid, "En kertonut koodia, lopetin puhelun heti.")
        self.assertEqual(resp2["reply_type"], "final")
        self.assertIn("decision", resp2)
        self.assertIn(resp2["decision"]["primary_action"], ["verify_via_official_channel", "contact_operator_support", "do_not_interact_and_delete"])

if __name__ == "__main__":
    unittest.main()
