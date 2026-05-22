import pytest
from rubrics.judge import judge_one_sync, judge_one_async, JUDGE_PROMPT


def test_judge_one_sync_returns_met_true(mocker):
    fake_client = mocker.Mock()
    fake_client.complete_json.return_value = {"met": True, "reason": "matches"}
    result = judge_one_sync(
        fake_client, "Q", "candidate",
        {"text": "明确指出 X", "criterion_type": "factual_anchor"},
    )
    assert result["met"] is True
    assert result["reason"] == "matches"


def test_judge_one_sync_returns_met_false_on_judge_error(mocker):
    fake_client = mocker.Mock()
    fake_client.complete_json.side_effect = RuntimeError("api blew up")
    result = judge_one_sync(
        fake_client, "Q", "candidate",
        {"text": "x", "criterion_type": "factual_anchor"},
    )
    assert result["met"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_judge_one_async_returns_met(mocker):
    fake_client = mocker.Mock()
    async def fake_async(*a, **k):
        return {"met": False, "reason": "no"}
    fake_client.complete_json_async = fake_async
    result = await judge_one_async(
        fake_client, "Q", "cand",
        {"text": "x", "criterion_type": "factual_anchor"},
    )
    assert result["met"] is False


def test_judge_prompt_constant_loaded():
    assert isinstance(JUDGE_PROMPT, str) and len(JUDGE_PROMPT) > 50
