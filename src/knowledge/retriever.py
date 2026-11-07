# -*- coding: utf-8 -*-
"""In-memory Knowledge Retriever for DNA Digital Security Assistant.
Indexes the 55 synthetic guidance passages in data/reference/guidance_corpus.jsonl.
Guarantees fast retrieval of grounded guidance IDs without external vector databases.
"""
import json
import os
from typing import Any, Dict, List, Optional

GUIDANCE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reference", "guidance_corpus.jsonl")

ACTION_GUIDANCE_MAP = {
    "no_action_needed": ["guidance_proportionate_advice", "guidance_legitimate_notifications"],
    "do_not_interact_and_delete": ["guidance_smishing_basics", "guidance_parcel_scam"],
    "verify_via_official_channel": ["guidance_sender_id_spoofing", "guidance_bank_verification"],
    "contact_bank_and_block_cards": ["guidance_card_details_entered", "guidance_bank_verification"],
    "change_password_and_enable_mfa": ["guidance_credential_compromise", "guidance_password_reuse"],
    "contact_operator_support": ["guidance_sim_swap", "guidance_one_time_codes"],
    "isolate_device_and_scan": ["guidance_device_compromise", "guidance_malicious_app"],
    "report_to_authority": ["guidance_report_to_police"],
    "escalate_to_human": ["guidance_handing_off"],
    "decline_out_of_scope": ["guidance_out_of_scope", "guidance_report_to_police"],
}

JOURNEY_GUIDANCE_MAP = {
    "suspicious_message": "guidance_smishing_basics",
    "clicked_link": "guidance_card_details_entered",
    "suspicious_call": "guidance_operator_impersonation",
    "breach_notice": "guidance_breach_response",
    "smb_incident": "guidance_invoice_fraud",
}

class GuidanceRetriever:
    def __init__(self, corpus_path: Optional[str] = None):
        path = corpus_path or GUIDANCE_PATH
        self.corpus: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        self.corpus[record["id"]] = record

    def get_by_id(self, guidance_id: str) -> Optional[Dict[str, Any]]:
        return self.corpus.get(guidance_id)

    def get_citations_for_case(self, action: str, journey: str, audience: str, is_benign: bool = False) -> List[str]:
        """Returns relevant guidance IDs."""
        if is_benign or action == "no_action_needed":
            return ["guidance_proportionate_advice"]
            
        cites = list(ACTION_GUIDANCE_MAP.get(action, ["guidance_proportionate_advice"]))
        if journey in JOURNEY_GUIDANCE_MAP:
            jg = JOURNEY_GUIDANCE_MAP[journey]
            if jg not in cites:
                cites.append(jg)
        return cites[:2]
