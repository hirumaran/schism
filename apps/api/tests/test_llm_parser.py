from __future__ import annotations

from pydantic import ValidationError

from app.services.llm_parser import ClaimResult, ContradictionResult, parse_llm_json


def test_parse_llm_json_handles_clean_json_correctly() -> None:
    result = parse_llm_json(
        '{"found": true, "claim": "Omega 3 reduces blood pressure in adults over time", "direction": "positive", "confidence": 0.8}',
        ClaimResult,
    )
    assert isinstance(result, ClaimResult)
    assert result.claim is not None


def test_parse_llm_json_strips_json_blocks() -> None:
    result = parse_llm_json(
        '```json\n{"found": true, "claim": "Omega 3 reduces blood pressure in adults over time", "direction": "positive", "confidence": 0.8}\n```',
        ClaimResult,
    )
    assert isinstance(result, ClaimResult)
    assert result.direction == "positive"


def test_parse_llm_json_recovers_from_leading_explanation_text() -> None:
    result = parse_llm_json(
        'Here is the JSON you asked for: {"is_contradiction": true, "score": 0.7, "type": "direct", "explanation": "These findings conflict.", "could_both_be_true": false}',
        ContradictionResult,
    )
    assert isinstance(result, ContradictionResult)
    assert result.score == 0.7


def test_parse_llm_json_returns_none_on_unparseable_input() -> None:
    result = parse_llm_json("not remotely json", ClaimResult)
    assert result is None


def test_claim_result_rejects_confidence_outside_range() -> None:
    try:
        ClaimResult.model_validate(
            {
                "found": True,
                "claim": "Omega 3 reduces blood pressure in adults over time",
                "direction": "positive",
                "confidence": 1.5,
            }
        )
    except ValidationError:
        return
    raise AssertionError("ClaimResult accepted an invalid confidence value")


def test_contradiction_result_rejects_score_outside_range() -> None:
    try:
        ContradictionResult.model_validate(
            {
                "is_contradiction": True,
                "score": -0.2,
                "type": "direct",
                "explanation": "These findings conflict.",
            }
        )
    except ValidationError:
        return
    raise AssertionError("ContradictionResult accepted an invalid score value")
