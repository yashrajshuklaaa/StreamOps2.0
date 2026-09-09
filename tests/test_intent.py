import pytest
from streamops.intent.detector import IntentDetector

def test_intent_detector_fast_path():
    detector = IntentDetector()
    res = detector.process_chunk("I will write a python script with pandas to compute averages.")
    assert res is not None
    assert res.tool_name == "python"
    assert res.should_trigger is True
    assert res.confidence > 0.3

def test_intent_detector_sql_detection():
    detector = IntentDetector()
    res = detector.process_chunk("Let's query the database using postgres sql.")
    assert res is not None
    assert res.tool_name == "sql"
    assert res.should_trigger is True

def test_intent_detector_browser_detection():
    detector = IntentDetector()
    res = detector.process_chunk("We will scrape the webpage using selenium.")
    assert res is not None
    assert res.tool_name == "browser"
    assert res.should_trigger is True

def test_intent_detector_no_false_positive():
    detector = IntentDetector()
    res = detector.process_chunk("Good morning, how can I help you today?")
    assert res is None

def test_intent_detector_reset():
    detector = IntentDetector()
    detector.process_chunk("I will use python.")
    assert detector.triggered_tool == "python"
    detector.reset()
    assert detector.triggered_tool is None
    assert detector.buffer == ""
