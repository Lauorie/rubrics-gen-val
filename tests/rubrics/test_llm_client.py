import json
import pytest
import httpx
from rubrics.llm_client import LLMClient, LLMConfig


def test_llm_client_completion_calls_endpoint(mocker):
    response = {
        "choices": [{
            "message": {"content": json.dumps({"ok": True})}
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    mock_post = mocker.patch.object(
        httpx.Client, "post",
        return_value=mocker.Mock(status_code=200, json=lambda: response, raise_for_status=lambda: None),
    )
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m")
    client = LLMClient(cfg)
    out = client.complete_json(
        system="sys", user="usr", schema_hint="{ok: bool}",
    )
    assert out == {"ok": True}
    assert mock_post.called


def test_llm_client_retries_on_500(mocker):
    """Server error should trigger retry."""
    side_effects = [
        mocker.Mock(status_code=500, raise_for_status=mocker.Mock(side_effect=httpx.HTTPStatusError(
            "x", request=mocker.Mock(), response=mocker.Mock(status_code=500),
        ))),
        mocker.Mock(status_code=200, json=lambda: {
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }, raise_for_status=lambda: None),
    ]
    mocker.patch.object(httpx.Client, "post", side_effect=side_effects)
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m", max_retries=3)
    client = LLMClient(cfg)
    out = client.complete_json(system="s", user="u", schema_hint="x")
    assert out == {"ok": True}


def test_llm_client_raises_on_non_json_response(mocker):
    mocker.patch.object(
        httpx.Client, "post",
        return_value=mocker.Mock(status_code=200, json=lambda: {
            "choices": [{"message": {"content": "this is not json"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }, raise_for_status=lambda: None),
    )
    cfg = LLMConfig(api_key="sk-x", base_url="https://example/v1", model="m", max_retries=1)
    client = LLMClient(cfg)
    with pytest.raises(ValueError):
        client.complete_json(system="s", user="u", schema_hint="x")
