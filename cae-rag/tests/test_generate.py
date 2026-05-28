from cae_rag.generate import build_prompt, generate_answer

def test_build_prompt_includes_question_and_chunks():
    chunks = [{"chunk_id": "d::0", "text": "context-A", "doc": "docX"},
              {"chunk_id": "d::1", "text": "context-B", "doc": "docY"}]
    system, user = build_prompt("为什么会失稳?", chunks)
    assert "仅" in system or "资料" in system  # grounded-only instruction present
    assert "为什么会失稳?" in user
    assert "context-A" in user and "context-B" in user
    assert "docX" in user and "docY" in user

def test_generate_answer_uses_client(monkeypatch):
    class _Msg: content = "  生成的答案  "
    class _Choice: message = _Msg()
    class _Resp: choices = [_Choice()]
    class _Chat:
        def __init__(self): self.kwargs = None
        def create(self, **kw): self.kwargs = kw; return _Resp()
    class _Completions:
        def __init__(self): self.completions = _Chat()
    class _Client:
        def __init__(self): self.chat = _Completions()
    client = _Client()
    chunks = [{"chunk_id": "d::0", "text": "ctx", "doc": "docX"}]
    ans = generate_answer(client, "问题?", chunks, model="deepseek/deepseek-v4-flash", temperature=0.0)
    assert ans == "生成的答案"
    assert client.chat.completions.kwargs["model"] == "deepseek/deepseek-v4-flash"
    assert client.chat.completions.kwargs["temperature"] == 0.0
