"""Independent multilingual sentiment and emotion intelligence engine.

This module is intentionally isolated from the existing RAG, guardrails,
PII redaction, HITL, and voice pipeline. It provides lightweight analysis
for text and optional speech-derived transcript data and can be integrated
by the current pipeline without altering its core business logic.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "gu": "Gujarati",
    "mr": "Marathi",
    "pa": "Punjabi",
    "bn": "Bengali",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
    "ne": "Nepali",
    "kok": "Konkani",
    "mai": "Maithili",
    "brx": "Bodo",
    "sat": "Santali",
    "doi": "Dogri",
    "ks": "Kashmiri",
    "mni": "Manipuri",
    "sd": "Sindhi",
}

EMOTION_LABELS = [
    "neutral",
    "happy",
    "satisfied",
    "confused",
    "frustrated",
    "angry",
    "sad",
    "anxious",
    "urgent",
    "complaint",
    "grateful",
    "emergency",
]

SENTIMENT_LABELS = ["positive", "neutral", "negative", "mixed"]
URGENCY_LABELS = ["low", "medium", "high", "critical"]
COMPLAINT_SEVERITY_LABELS = ["low", "medium", "high"]


@dataclass
class EmotionProfile:
    language: str = "en"
    emotion: str = "neutral"
    emotion_confidence: float = 0.0
    sentiment: str = "neutral"
    sentiment_confidence: float = 0.0
    urgency: str = "low"
    urgency_confidence: float = 0.0
    complaint_severity: str = "low"
    complaint_severity_confidence: float = 0.0
    should_escalate: bool = False
    escalation_reason: str = ""
    adaptive_response: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class SentimentEngine:
    """A lightweight multilingual sentiment and emotion analysis engine."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            "enable_multilingual": True,
            "min_confidence": 0.5,
            "urgency_thresholds": {"low": 0.3, "medium": 0.5, "high": 0.75, "critical": 0.9},
            "escalation_policy": {
                "high_frustration": 0.8,
                "high_urgency": 0.8,
                "repeated_failure": 0.8,
                "low_confidence": 0.4,
            },
            "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
        }
        if config:
            self.config.update(config)

        self._memory: List[Dict[str, Any]] = []
        self._emotion_history: List[str] = []
        self._analytics: Dict[str, Any] = {
            "total_turns": 0,
            "emotion_distribution": Counter(),
            "sentiment_distribution": Counter(),
            "urgency_distribution": Counter(),
            "complaint_volume": 0,
            "escalations": 0,
            "language_distribution": Counter(),
            "conversation_lengths": [],
            "resolution_success": 0,
        }

    def analyze_text(self, text: str, *, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not text or not str(text).strip():
            return self._empty_profile()

        cleaned = re.sub(r"\s+", " ", str(text).strip())
        language = self._detect_language(cleaned)
        emotion, emotion_conf = self._detect_emotion(cleaned, language)
        sentiment, sentiment_conf = self._detect_sentiment(cleaned, emotion)
        urgency, urgency_conf = self._detect_urgency(cleaned, emotion)
        complaint_severity, complaint_conf = self._detect_complaint_severity(cleaned, emotion, urgency)
        should_escalate, reason = self._should_escalate(emotion, urgency, sentiment, complaint_severity)
        adaptive = self.apply_adaptive_response(cleaned, {
            "emotion": emotion,
            "emotion_confidence": emotion_conf,
            "sentiment": sentiment,
            "urgency": urgency,
            "complaint_severity": complaint_severity,
            "should_escalate": should_escalate,
            "escalation_reason": reason,
            "language": language,
        })

        profile = {
            "language": language,
            "emotion": emotion,
            "emotion_confidence": round(emotion_conf, 2),
            "sentiment": sentiment,
            "sentiment_confidence": round(sentiment_conf, 2),
            "urgency": urgency,
            "urgency_confidence": round(urgency_conf, 2),
            "complaint_severity": complaint_severity,
            "complaint_severity_confidence": round(complaint_conf, 2),
            "should_escalate": should_escalate,
            "escalation_reason": reason,
            "adaptive_response": adaptive,
            "metadata": metadata or {},
        }
        self._memory.append(profile)
        self._emotion_history.append(emotion)
        self._update_analytics(profile)
        logger.info("sentiment_profile", extra={"profile": self._sanitize_profile(profile)})
        return profile

    def analyze_voice(self, transcript: str, *, speaking_rate: Optional[float] = None, pauses: Optional[int] = None, interruption_frequency: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        profile = self.analyze_text(transcript, metadata=metadata)
        if speaking_rate is not None:
            profile["metadata"]["speaking_rate"] = speaking_rate
        if pauses is not None:
            profile["metadata"]["pauses"] = pauses
        if interruption_frequency is not None:
            profile["metadata"]["interruption_frequency"] = interruption_frequency
        return profile

    def apply_adaptive_response(self, text: str, profile: Dict[str, Any]) -> str:
        emotion = (profile or {}).get("emotion", "neutral")
        urgency = (profile or {}).get("urgency", "low")
        language = (profile or {}).get("language", "en")
        if emotion == "frustrated" or emotion == "angry":
            base = "I understand this is frustrating. I will keep my response calm and concise." if language == "en" else "मैं समझता/समझती हूँ कि यह परेशान करने वाला है। मैं शांत और संक्षिप्त उत्तर दूँगा।"
        elif emotion == "confused":
            base = "I will explain this step by step in a simple way." if language == "en" else "मैं इसे सरल चरणों में समझाऊँगा।"
        elif emotion == "urgent" or urgency in {"high", "critical"}:
            base = "I will prioritize the most useful next step and escalate if needed." if language == "en" else "मैं सबसे उपयोगी अगला कदम पहले बताऊँगा और जरूरत पड़ने पर escalation करूँगा।"
        elif emotion == "satisfied" or emotion == "happy":
            base = "I’m glad this helped." if language == "en" else "मुझे खुशी है कि इससे मदद मिली।"
        else:
            base = "I will respond clearly and helpfully." if language == "en" else "मैं स्पष्ट और उपयोगी तरीके से उत्तर दूँगा।"
        return base

    def get_conversation_memory(self) -> List[Dict[str, Any]]:
        return list(self._memory)

    def get_emotion_trends(self) -> List[str]:
        return list(self._emotion_history)

    def get_analytics_summary(self) -> Dict[str, Any]:
        summary = dict(self._analytics)
        summary["emotion_distribution"] = dict(summary["emotion_distribution"])
        summary["sentiment_distribution"] = dict(summary["sentiment_distribution"])
        summary["urgency_distribution"] = dict(summary["urgency_distribution"])
        summary["language_distribution"] = dict(summary["language_distribution"])
        return summary

    def reset(self) -> None:
        self._memory.clear()
        self._emotion_history.clear()
        self._analytics = {
            "total_turns": 0,
            "emotion_distribution": Counter(),
            "sentiment_distribution": Counter(),
            "urgency_distribution": Counter(),
            "complaint_volume": 0,
            "escalations": 0,
            "language_distribution": Counter(),
            "conversation_lengths": [],
            "resolution_success": 0,
        }

    def _detect_language(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["नहीं", "खुशी", "मदद", "है", "क्या"]):
            return "hi"
        if any(token in lowered for token in ["தமிழ்", "என்ன", "உதவி", "சிக்கல்"]):
            return "ta"
        if any(token in lowered for token in ["తెలుగు", "సహాయం", "సమస్య"]):
            return "te"
        if any(token in lowered for token in ["ಕನ್ನಡ", "ಸಹಾಯ", "ಸಮಸ್ಯ"]):
            return "kn"
        if any(token in lowered for token in ["മലയാളം", "സഹായം", "പ്രശ്നം"]):
            return "ml"
        if any(token in lowered for token in ["ગુજરાતી", "મદદ", "સમस्या"]):
            return "gu"
        if any(token in lowered for token in ["मराठी", "मदत", "समस्या"]):
            return "mr"
        if any(token in lowered for token in ["ਪੰਜਾਬੀ", "ਮਦਦ", "ਸਮੱਸਿਆ"]):
            return "pa"
        if any(token in lowered for token in ["বাংলা", "সাহায্য", "সমস্যা"]):
            return "bn"
        if any(token in lowered for token in ["اردو", "مدد", "مسئلہ"]):
            return "ur"
        if any(token in lowered for token in ["ଓଡ଼ିଆ", "ସହାୟତା", "ସମସ୍ୟା"]):
            return "or"
        if any(token in lowered for token in ["অসমীয়া", "সহায়", "সমস্যা"]):
            return "as"
        if any(token in lowered for token in ["नेपाली", "मद्दत", "समस्या"]):
            return "ne"
        if any(token in lowered for token in ["ಕೋಂಕಣಿ", "मदत", "समस्या"]):
            return "kok"
        if any(token in lowered for token in ["मैथिली", "मदद", "समस्या"]):
            return "mai"
        if any(token in lowered for token in ["बोड़ो", "मदद", "समस्या"]):
            return "brx"
        if any(token in lowered for token in ["संताली", "मदद", "समस्या"]):
            return "sat"
        if any(token in lowered for token in ["डोगरी", "मदद", "समस्या"]):
            return "doi"
        if any(token in lowered for token in ["कश्मीरी", "मदद", "समस्या"]):
            return "ks"
        if any(token in lowered for token in ["মণিপুরি", "সাহায্য", "সমস্যা"]):
            return "mni"
        if any(token in lowered for token in ["سنڌي", "مدد", "مسئلہ"]):
            return "sd"
        return "en"

    def _detect_emotion(self, text: str, language: str) -> tuple[str, float]:
        lowered = text.lower()
        scores = defaultdict(float)
        if any(token in lowered for token in ["angry", "furious", "rage", "irritated", "भड़क", "गुस्सा", "क्रोधित"]):
            scores["angry"] += 0.95
        if any(token in lowered for token in ["frustrated", "frustration", "annoyed", "problem", "issue", "not working", "काम नहीं", "परेशान", "समस्या"]):
            scores["frustrated"] += 0.9
        if any(token in lowered for token in ["confused", "unclear", "don't understand", "not sure", "समझ नहीं", "साफ नहीं"]):
            scores["confused"] += 0.88
        if any(token in lowered for token in ["happy", "great", "thanks", "thank you", "good", "खुशी", "धन्यवाद", "बहुत अच्छा"]):
            scores["happy"] += 0.9
        if any(token in lowered for token in ["satisfied", "happy with", "resolved", "done", "संतुष्ट", "हल", "हो गया"]):
            scores["satisfied"] += 0.88
        if any(token in lowered for token in ["sad", "upset", "disappointed", "दुख", "उदास"]):
            scores["sad"] += 0.82
        if any(token in lowered for token in ["anxious", "worried", "nervous", "scared", "चिंता", "डर", "घबराया"]):
            scores["anxious"] += 0.84
        if any(token in lowered for token in ["urgent", "immediately", "asap", "now", "तुरंत", "अभी", "इमरजेंसी"]):
            scores["urgent"] += 0.8
        if any(token in lowered for token in ["complaint", "complain", "dispute", "grievance", "शिकायत", "गुनाह"]):
            scores["complaint"] += 0.83
        if any(token in lowered for token in ["grateful", "thank you", "thanks", "appreciate", "धन्यवाद", "आभार"]):
            scores["grateful"] += 0.9
        if any(token in lowered for token in ["emergency", "critical", "life threatening", "danger", "आपात", "आपातकाल"]):
            scores["emergency"] += 0.98
        if not scores:
            return "neutral", 0.5
        best_emotion, best_score = max(scores.items(), key=lambda item: item[1])
        return best_emotion, min(0.99, max(0.5, best_score))

    def _detect_sentiment(self, text: str, emotion: str) -> tuple[str, float]:
        lowered = text.lower()
        if any(token in lowered for token in ["thank", "thanks", "great", "good", "happy", "satisfied", "resolved", "धन्यवाद", "बहुत अच्छा", "मदद मिली"]):
            return "positive", 0.86
        if any(token in lowered for token in ["angry", "frustrated", "confused", "problem", "issue", "bad", "not working", "गुस्सा", "परेशान", "समस्या"]):
            return "negative", 0.88
        if any(token in lowered for token in ["but", "however", "yet", "though", "though", "लेकिन", "पर"]):
            return "mixed", 0.72
        return "neutral", 0.6

    def _detect_urgency(self, text: str, emotion: str) -> tuple[str, float]:
        lowered = text.lower()
        if any(token in lowered for token in ["emergency", "critical", "immediately", "now", "urgent", "asap", "तुरंत", "आपात", "अभी"]):
            return "critical", 0.95
        if emotion in {"angry", "frustrated"} or any(token in lowered for token in ["not working", "issue", "problem", "मदद", "समस्या", "जल्दी"]):
            return "high", 0.73
        if any(token in lowered for token in ["confused", "unclear", "question", "ask", "समझ नहीं", "सवाल"]):
            return "low", 0.58 if emotion == "confused" else 0.5
        if any(token in lowered for token in ["need help", "help me", "मदद"]):
            return "low", 0.5
        return "low", 0.5

    def _detect_complaint_severity(self, text: str, emotion: str, urgency: str) -> tuple[str, float]:
        if urgency == "critical" or emotion in {"angry", "emergency"}:
            return "high", 0.94
        if emotion in {"frustrated", "complaint"}:
            return "medium", 0.78
        return "low", 0.6

    def _should_escalate(self, emotion: str, urgency: str, sentiment: str, complaint_severity: str) -> tuple[bool, str]:
        if urgency == "critical" or emotion == "emergency":
            return True, "critical urgency"
        if emotion in {"frustrated", "angry"} and urgency in {"high", "critical"}:
            return True, "high frustration and urgency"
        if complaint_severity == "high":
            return True, "high complaint severity"
        if sentiment == "negative" and emotion in {"confused", "angry", "frustrated"}:
            return True, "negative sentiment with high emotional load"
        return False, ""

    def _update_analytics(self, profile: Dict[str, Any]) -> None:
        self._analytics["total_turns"] += 1
        self._analytics["emotion_distribution"][profile["emotion"]] += 1
        self._analytics["sentiment_distribution"][profile["sentiment"]] += 1
        self._analytics["urgency_distribution"][profile["urgency"]] += 1
        self._analytics["language_distribution"][profile["language"]] += 1
        self._analytics["conversation_lengths"].append(len(self._memory))
        if profile["should_escalate"]:
            self._analytics["escalations"] += 1
        if profile["sentiment"] == "positive":
            self._analytics["resolution_success"] += 1

    def _empty_profile(self) -> Dict[str, Any]:
        return {
            "language": "en",
            "emotion": "neutral",
            "emotion_confidence": 0.0,
            "sentiment": "neutral",
            "sentiment_confidence": 0.0,
            "urgency": "low",
            "urgency_confidence": 0.0,
            "complaint_severity": "low",
            "complaint_severity_confidence": 0.0,
            "should_escalate": False,
            "escalation_reason": "",
            "adaptive_response": "",
            "metadata": {},
        }

    def _sanitize_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = dict(profile)
        sanitized["metadata"] = {}
        return sanitized


__all__ = ["SentimentEngine", "EmotionProfile", "SUPPORTED_LANGUAGES", "EMOTION_LABELS"]
