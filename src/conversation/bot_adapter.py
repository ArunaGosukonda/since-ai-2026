# -*- coding: utf-8 -*-
"""Multi-Turn Bot Adapter for DNA Digital Security Assistant.
Conforms to sim/PROTOCOL.md and executes through sim/run_conversation.py.
"""
import copy
from typing import Any, Dict

from src.application.assistant import DigitalSecurityAssistant
from src.intelligence.signal_fusion import fuse_signals
from src.consent.consent_manager import ConsentManager
from src.decision.twin_resolver import detect_decisive_question

_assistant = DigitalSecurityAssistant()

def step(event: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Processes an incoming event from the simulator and returns a valid reply."""
    etype = event.get("type")
    
    if etype == "start":
        state.clear()
        case = copy.deepcopy(event.get("case", {}))
        state["case"] = case
        state["facts"] = {}
        state["granted_consent"] = set(case.get("consent", {}).get("pre_granted", []))
        state["refused_consent"] = set()
        state["last_topic"] = None
        state["turns"] = 0
        
        ctx = fuse_signals(state["case"], state["facts"])
        nec_signals = ConsentManager.determine_necessary_signals(ctx)
        pending = [s for s in nec_signals if s not in state["granted_consent"] and s not in state["refused_consent"]]
        
        if pending and state["turns"] < 5:
            state["turns"] += 1
            lang = state["case"].get("language", "fi")
            return {
                "type": "consent_request",
                "fields": pending,
                "text": ConsentManager.get_consent_request_text(pending, lang=lang),
            }
            
        decisive = detect_decisive_question(ctx, state["facts"])
        if decisive and state["turns"] < 5:
            topic, q_text = decisive
            state["last_topic"] = topic
            state["turns"] += 1
            return {
                "type": "question",
                "text": q_text,
                "topics": [topic],
            }
            
        ans = _assistant.process_case(state["case"], facts=state["facts"], mode="multi_turn", granted_consent=state["granted_consent"])
        return {"type": "final", "answer": ans}
        
    elif etype == "consent_reply":
        state["granted_consent"].update(event.get("granted", []))
        state["refused_consent"].update(event.get("refused", []))
        
        signals = event.get("signals") or {}
        for path, val in signals.items():
            parts = path.split(".")
            cur = state["case"].setdefault("signals", {})
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = val
            
        ctx = fuse_signals(state["case"], state["facts"])
        decisive = detect_decisive_question(ctx, state["facts"])
        if decisive and state["turns"] < 5:
            topic, q_text = decisive
            state["last_topic"] = topic
            state["turns"] += 1
            return {
                "type": "question",
                "text": q_text,
                "topics": [topic],
            }
            
        ans = _assistant.process_case(state["case"], facts=state["facts"], mode="multi_turn", granted_consent=state["granted_consent"])
        return {"type": "final", "answer": ans}
        
    elif etype == "user_reply":
        if state.get("last_topic"):
            state["facts"][state["last_topic"]] = event.get("text", "")
            
        ans = _assistant.process_case(state["case"], facts=state["facts"], mode="multi_turn", granted_consent=state["granted_consent"])
        return {"type": "final", "answer": ans}
        
    elif etype == "turn_limit":
        ans = _assistant.process_case(state.get("case", {}), facts=state.get("facts", {}), mode="multi_turn", granted_consent=state.get("granted_consent"))
        return {"type": "final", "answer": ans}
        
    # Fallback
    ans = _assistant.process_case(state.get("case", {}), facts=state.get("facts", {}), mode="multi_turn", granted_consent=state.get("granted_consent"))
    return {"type": "final", "answer": ans}
