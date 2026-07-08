import pytest

from backend.sentiment_engine import SentimentEngine


@pytest.fixture
def engine():
    return SentimentEngine()


def test_detects_hindi_language_and_frustration(engine):
    profile = engine.analyze_text("यह काम नहीं हो रहा है, मैं बहुत frustrated हूँ")
    assert profile["language"] == "hi"
    assert profile["emotion"] == "frustrated"
    assert profile["sentiment"] == "negative"
    assert profile["urgency"] in {"high", "medium"}


def test_detects_english_confusion_and_low_urgency(engine):
    profile = engine.analyze_text("I am confused about the steps and need help")
    assert profile["language"] == "en"
    assert profile["emotion"] == "confused"
    assert profile["sentiment"] == "negative"
    assert profile["urgency"] == "low"


def test_adaptive_response_is_empathy_focused_for_frustration(engine):
    profile = engine.analyze_text("I am very angry and need help immediately")
    response = engine.apply_adaptive_response("Here is the answer.", profile)
    assert "understand" in response.lower() or "frustrating" in response.lower()


def test_escalation_recommendation_for_critical_urgency(engine):
    profile = engine.analyze_text("This is an emergency and I need a human now")
    assert profile["should_escalate"] is True
    assert profile["escalation_reason"]


def test_analytics_summary_tracks_turns(engine):
    engine.analyze_text("I am happy with the service")
    engine.analyze_text("I am angry and need help")
    summary = engine.get_analytics_summary()
    assert summary["total_turns"] == 2
    assert summary["emotion_distribution"]["happy"] >= 1
    assert summary["emotion_distribution"]["angry"] >= 1
