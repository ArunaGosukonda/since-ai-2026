"""Unified ThreatClassifier bridging ML fact estimation, hand-written evidence,
safety rules, and the DNA Digital Security tri-state decision model.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from .dsa.assess import Assessor
from .dsa.facts_model import DEFAULT_PATH, FactModel, build_examples

logger = logging.getLogger(__name__)


class ThreatClassifier:
    """Production ML threat classifier for Since AI."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or DEFAULT_PATH
        self.model = self._load_or_train_model()
        self.assessor = Assessor(model=self.model)

    def _load_or_train_model(self) -> Optional[FactModel]:
        try:
            if os.path.exists(self.model_path):
                model, _ = FactModel.load(self.model_path)
                logger.info("Loaded FactModel from %s", self.model_path)
                return model
        except Exception as e:
            logger.warning("Failed to load FactModel from %s: %s", self.model_path, e)

        # Try training if dev data is available
        try:
            logger.info("Attempting to train FactModel from dev examples...")
            examples = build_examples()
            if examples:
                model = FactModel().fit(examples)
                try:
                    model.save(self.model_path)
                    logger.info("Successfully trained and saved FactModel to %s", self.model_path)
                except Exception as save_err:
                    logger.warning("Could not persist trained model: %s", save_err)
                return model
        except Exception as train_err:
            logger.warning("Could not train FactModel: %s. Using evidence-only Assessor.", train_err)

        return None

    def assess(
        self,
        text: str,
        signals: Optional[Dict[str, Any]] = None,
        answers: Optional[Dict[str, Any]] = None,
        language: str = "en",
        audience: str = "consumer",
        asked: Optional[List[str]] = None,
        final: bool = False,
    ) -> Dict[str, Any]:
        """Assess a situation using user message, signals, and answers.

        Returns structured decision, facts, risk, urgency, and tri-state verdict.
        """
        case = {
            "opening_message": text,
            "language": language,
            "audience": audience,
            "signals": signals or {},
        }
        raw = self.assessor.assess(
            case=case,
            answers=answers or {},
            asked=asked or [],
            final=final,
        )

        dec = raw.get("decision", {})
        action = dec.get("action", "verify_via_official_channel")
        risk_level = dec.get("risk_level", "low")
        urgency = dec.get("urgency", "routine")
        facts_present = dec.get("facts_present", [])

        # Determine tri-state outcome
        if action in ("no_action_needed", "explain_benign") or "legitimate" in facts_present:
            verdict = "BENIGN"
        elif risk_level in ("high", "critical") or any(
            f in facts_present
            for f in (
                "money_sent_to_scammer",
                "bank_access_exposed",
                "device_compromised",
                "phone_number_takeover",
                "account_compromised",
                "personal_safety_risk",
            )
        ):
            verdict = "SUSPICIOUS_OR_MALICIOUS"
        else:
            verdict = "INCONCLUSIVE"

        return {
            "tri_state_verdict": verdict,
            "action": action,
            "secondary_actions": dec.get("secondary_actions", []),
            "risk_level": risk_level,
            "urgency": urgency,
            "facts_present": facts_present,
            "decision_reason": dec.get("decision_reason", ""),
            "steps": dec.get("steps", []),
            "rules_fired": dec.get("rules_fired", []),
            "next": raw.get("next", {"type": "answer"}),
            "open_question": raw.get("open_question"),
            "probabilities": dec.get("p", {}),
            "evidence": dec.get("evidence", {}),
        }


# Singleton accessor
_threat_classifier_instance: Optional[ThreatClassifier] = None


def get_threat_classifier() -> ThreatClassifier:
    global _threat_classifier_instance
    if _threat_classifier_instance is None:
        _threat_classifier_instance = ThreatClassifier()
    return _threat_classifier_instance
