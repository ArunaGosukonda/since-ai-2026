"""Classifier module integrating ML threat classification with evidence reasoning."""
from .threat_classifier import ThreatClassifier, get_threat_classifier

__all__ = ["ThreatClassifier", "get_threat_classifier"]
