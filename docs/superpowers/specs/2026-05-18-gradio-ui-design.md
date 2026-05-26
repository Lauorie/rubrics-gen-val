# Gradio UI for papers_qa — Design Spec

**Date:** 2026-05-18
**Project:** `/home/juli/RLM/papers_qa/`
**Goal:** Add a beautiful Gradio web UI for `papers_qa` that streams the LLM's reasoning trajectory live, supports multi-turn chat, and can be shared publicly with `share=True`.

---

## 1. Requirements (resolved with user)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Reasoning detail | Per-iteration full trajectory (model response + each ```repl code + stdout/stderr + sub-call info) | User wants to actually see the reasoning, not just summary timings |
| 2 | Access control | Fully public (no auth) | User explicitly chose this — accepts the trade-off |
| 3 | Interaction mode | Multi-turn chat | User wants follow-ups |
| 4 | Layout | Left-right split (chat left, trace right, status bar bottom) | Desktop-friendly; trace stays visible while chatting |

---

## 2. Architecture

### 2.1 New files

```
papers_qa/streaming.py       # ~100 lines: _QueueLogger + stream_ask()
scripts/gradio_app.py        # ~200 lines: Blocks + handlers + launch
tests/test_streaming.py      # ~60 lines: mocked iteration events + error path
```

### 2.2 Reused unchanged

- `papers_qa/config.py` — frozen config from env (Task 2)
- `papers_qa/loader.py` — `load_papers()` (Task 3)
- `papers_qa/search.py` — `build_search_tool()` (Task 4)
- `papers_qa/prompts.py` — `build_bilingual_system_prompt()` (Task 5)
- `papers_qa/runner.py` — `PapersQA` driver (Task 6)
- `papers_qa/__init__.py` — public exports

### 2.3 Modified files

- `pyproject.toml` — add `[project.optional-dependencies] ui = ["gradio>=4.44.0"]`
- `.env.example` — append `PAPERS_QA_GRADIO_SHARE / PORT / HOST` (commented out, optional)
- `README.md` — small section "Web UI" pointing to the new script
- `中文文档.md` — short paragraph under "使用文档"

---

## 3. Streaming mechanism

### 3.1 `_QueueLogger`

Subclasses `rlm.logger.RLMLogger`:

```python
class _QueueLogger(RLMLogger):
    def __init__(self, log_dir: str | None, events: "queue.Queue") -> None:
        super().__init__(log_dir=log_dir)
        self._events = events

    def log(self, iteration: RLMIteration) -> None:
        super().log(iteration)              # keep on-disk JSONL behavior
        self._events.put({
            "type": "iteration",
            "response": iteration.response,
            "code_blocks": [
                {
                    "code": cb.code,
                    "stdout": cb.result.stdout if cb.result else "",
                    "stderr": cb.result.stderr if cb.result else "",
                    "final_answer": getattr(cb.result, "final_answer", None) if cb.result else None,
                }
                for cb in iteration.code_blocks
            ],
            "final_answer": iteration.final_answer,
            "iteration_time": iteration.iteration_time,
        })
```

**Why this and not RLM's `on_iteration_*` callbacks:** the callbacks only pass `(depth, iter_num, duration)`. The Logger interface gets the full `RLMIteration` object including the model's response text, every code block executed, every sub-call invocation. That's what "完整轨迹" requires.

### 3.2 `stream_ask(qa, question, history_text) -> Iterator[dict]`

- Creates a `queue.Queue` for events
- Temporarily swaps `qa.rlm.logger` to a `_QueueLogger` bound to that queue
- Builds the final `root_prompt` by prepending prior chat history (if any) to `question`
- Starts a daemon thread that calls `qa.rlm.completion(prompt=qa.papers, root_prompt=root_prompt)`
- Main thread loops on `events.get(timeout=600)`:
  - On `"iteration"` event → yield as-is
  - On internal `"_done"` sentinel → yield either `{"type": "final", ...}` (with `answer`, `duration_s`, `cost_usd`) or `{"type": "error", "error": "..."}`
- On `queue.Empty` (600 s) → yield `{"type": "timeout"}` and break
- Restores `qa.rlm.logger` in a `finally` so even on error the original logger is back

### 3.3 Concurrency

- One shared `PapersQA` instance (loaded once at app startup) is used by all Gradio sessions
- Per request: `_QueueLogger` swap is short-lived inside `stream_ask`. To avoid races between concurrent requests, the Gradio queue is limited (see §6.1)

---

## 4. Multi-turn chat (stateless)

No RLM `persistent=True`. Reasons:
- Public link means concurrent users. Persistent mode requires per-session `PapersQA(config)`, each of which reloads 79 papers (~7 MB JSON serialize + REPL exec). Multi-user load would melt RAM and burn startup time.
- The model doesn't actually need REPL-state continuity for the kind of follow-ups users will ask ("then what about MoE?", "elaborate on point 2", etc.). Textual context is enough.

**Implementation:**

`gr.State` holds the chat history as `list[tuple[str, str]]` of `(user, bot)` pairs.

Before each `stream_ask`, build a `history_text` block:

```
对话历史（参考用，不要重复回答已答过的部分）：
Q: <prior user msg 1>
A: <prior bot msg 1>
Q: <prior user msg 2>
A: <prior bot msg 2>

新问题：<current user msg>
```

This becomes `root_prompt`. Truncate prior bot messages to ~800 chars each to keep root prompt small (RLM root LLM doesn't need full prior answers; just enough for context).

---

## 5. UI layout

### 5.1 Tree

```
gr.Blocks(theme=indigo_soft, css=...)
├── Row: Markdown banner "papers_qa · 79 papers · model: …"
├── Row:
│   ├── Column scale=2:
│   │   ├── Chatbot (height=520, bubble_full_width=False)
│   │   ├── Row:
│   │   │   ├── Textbox (placeholder="提问，例：GKD 跟 SeqKD 在训练数据上的差异")
│   │   │   ├── Button "提交" (variant="primary")
│   │   │   └── Button "清空" (variant="secondary")
│   │   └── (示例问题 Accordion: 3 个一键填入按钮)
│   └── Column scale=1:
│       ├── Markdown "## 推理轨迹"
│       └── Markdown trace_md (elem_classes=["trace-panel"])
├── Row: Markdown status_md (small text)
└── State: history (list[tuple[str,str]])
```

### 5.2 Custom CSS

```css
.trace-panel {
  max-height: 600px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  font-size: 12.5px;
}
.trace-panel details { margin: 8px 0; padding: 8px; background: rgba(99,102,241,0.04); border-left: 3px solid rgb(99,102,241); border-radius: 6px; }
.trace-panel summary { cursor: pointer; font-weight: 600; }
.trace-panel pre { background: #f8f9fb; padding: 8px; border-radius: 4px; overflow-x: auto; }
```

### 5.3 Theme

```python
gr.themes.Soft(primary_hue="indigo", neutral_hue="slate", radius_size="md")
```

### 5.4 Per-iteration markdown rendering

```python
def render_iteration_md(n: int, evt: dict) -> str:
    parts = [f"\n### 🔹 迭代 {n} · {evt.get('iteration_time', 0):.1f}s\n"]
    resp = (evt.get("response") or "").strip()
    if resp:
        snippet = resp if len(resp) <= 600 else resp[:600] + "…"
        parts.append(f"**模型输出：**\n\n```\n{snippet}\n```\n")
    for i, cb in enumerate(evt.get("code_blocks") or [], 1):
        parts.append(f"<details><summary>📦 代码块 {i}</summary>\n\n")
        parts.append(f"```python\n{cb['code']}\n```\n\n")
        if cb.get("stdout"):
            out = cb["stdout"]
            if len(out) > 1500: out = out[:1500] + "\n… (truncated)"
            parts.append(f"**stdout:**\n\n```\n{out}\n```\n\n")
        if cb.get("stderr"):
            parts.append(f"**stderr:**\n\n```\n{cb['stderr'][:500]}\n```\n\n")
        if cb.get("final_answer"):
            parts.append(f"✅ **此块标记 answer.ready = True**\n\n")
        parts.append("</details>\n\n")
    return "".join(parts)
```

---

## 6. Launch & configuration

### 6.1 Gradio queue

```python
demo.queue(default_concurrency_limit=2, max_size=20)
```

- Caps concurrent answers at 2 (don't melt the API on a public link)
- Queue depth 20 max — beyond that, new users get a polite "队列已满" message

### 6.2 Launch options (resolved precedence: CLI > env > default)

| Setting | CLI | Env var | Default |
|---------|-----|---------|---------|
| Share public link | `--share` | `PAPERS_QA_GRADIO_SHARE=true` | `False` |
| Port | `--port 7860` | `PAPERS_QA_GRADIO_PORT` | `7860` |
| Host | `--host 0.0.0.0` | `PAPERS_QA_GRADIO_HOST` | `127.0.0.1` |
| Server name on banner | `--title "..."` | — | `"papers_qa"` |

`demo.launch(share=share, server_port=port, server_name=host, show_error=True)`

### 6.3 Startup

```python
def main() -> int:
    args = parse_args()
    setup_logging(...)
    cfg = PapersQAConfig.from_env(args.env_file)
    qa = PapersQA(cfg)                                    # one-time load of 79 papers
    demo = build_demo(qa, banner_title=args.title or "papers_qa")
    demo.queue(default_concurrency_limit=2, max_size=20)
    demo.launch(
        share=args.share or os.environ.get("PAPERS_QA_GRADIO_SHARE", "").lower() == "true",
        server_port=args.port or int(os.environ.get("PAPERS_QA_GRADIO_PORT", "7860")),
        server_name=args.host or os.environ.get("PAPERS_QA_GRADIO_HOST", "127.0.0.1"),
        show_error=True,
    )
    return 0
```

---

## 7. Error handling

| Failure mode | UI behavior |
|--------------|-------------|
| RLM raises `BudgetExceededError` / `TimeoutExceededError` / `ErrorThresholdExceededError` | Bot message becomes `❌ 出错：{type}: {message}` in red; trace pane shows partial trajectory up to failure point; status bar shows `❌ 失败 · {duration}` |
| Generic `Exception` in background thread | Same path; full traceback logged server-side, only one-line summary shown to user |
| Queue timeout (no event in 600 s) | Bot message: `⚠️ 模型无响应（600s 无事件），请重试` |
| Concurrent slot full | Gradio shows its built-in "请稍候" status; we don't override |

---

## 8. Testing

### 8.1 `tests/test_streaming.py`

Three tests, all mocked (no real API):

1. **`test_stream_ask_yields_iterations_then_final`**
   - Build a minimal `PapersQA` with a stub corpus
   - Monkeypatch `qa.rlm.completion`: invoke `qa.rlm.logger.log(...)` twice with two fake `RLMIteration` objects, then return a fake `RLMChatCompletion`
   - Consume `stream_ask` → expect 2 iteration events + 1 final event
   - Assert `final` has `answer`, `duration_s`, `cost_usd`

2. **`test_stream_ask_handles_exception`**
   - Monkeypatch `qa.rlm.completion` to raise `RuntimeError("boom")`
   - Expect a single `{"type": "error", "error": "RuntimeError: boom"}` event
   - Assert that `qa.rlm.logger` is restored to its pre-call value afterward (logger swap leak guard)

3. **`test_logger_swap_is_restored_on_success`**
   - Run a successful stream, assert `qa.rlm.logger is original_logger` after consumption

### 8.2 Not tested (cost vs value)

- `scripts/gradio_app.py` end-to-end. Gradio has no first-class headless test harness; spinning a real demo for tests is high-friction. Manual smoke is fine for a UI.

---

## 9. Verification plan

Manual smoke test once implemented:

```bash
source .venv/bin/activate
uv pip install -e ".[ui]"
python scripts/gradio_app.py --share     # opens https://*.gradio.live
```

Expected:
- App boots within ~5 s (load 79 papers once)
- Open browser, type a Chinese question, click 提交
- Within 2-3 s: first iteration card appears in right panel
- Within 15-30 s: final answer appears in left chat
- Right panel scrolls naturally as iterations stack
- Click 清空 → chat + trace + state all clear
- Follow-up question references prior context

---

## 10. Risks & mitigations

| Severity | Risk | Mitigation |
|----------|------|------------|
| HIGH | Public link with no auth burns API budget on bad actors | `default_concurrency_limit=2`, `max_size=20`. Cost cap via existing `PAPERS_QA_MAX_BUDGET_USD` (per-request). Operator can rotate API key if abused. Document that fact in README. |
| MEDIUM | `_QueueLogger` swap is racy if two requests hit at exactly the same time | Logger swap happens inside `stream_ask` which Gradio queues serializes via `default_concurrency_limit=2`. Two concurrent calls could theoretically interleave logger writes; we accept this for v1 (worst case: trace lines appear under wrong user). Proper fix in v2 = per-request RLM instance or pass logger as kwarg. |
| MEDIUM | `share=True` link is ephemeral (gradio.live 72h TTL) | Document this; user can restart with same command to get a new link. For long-lived hosting, suggest Hugging Face Spaces. |
| LOW | Trace markdown grows unbounded in long conversations | Per-iteration truncation (response: 600 chars, stdout: 1500 chars, stderr: 500 chars). Trace pane has CSS `max-height` + scroll. |
| LOW | Chat history grows unbounded | Truncate prior bot messages to 800 chars when building history_text. UI clear button resets. |

---

## 11. Out of scope (YAGNI)

- Streaming sub-LLM call tokens word-by-word (we stream per-iteration, that's plenty)
- Per-user state / login / database
- Export trajectory as file from UI (use existing `outputs/logs/*.jsonl`)
- Theme switcher in UI
- Inline rendering of LaTeX in chat (Gradio Chatbot supports it by default; we won't fight it)
- Markdown sanitization (we control all rendered content; no XSS surface from user input since chat is text-only)

---

## 12. Public API additions

- `papers_qa.streaming.stream_ask(qa: PapersQA, question: str, history_text: str = "") -> Iterator[dict]`

That's the only new public function. `_QueueLogger` is private (underscore prefix).

---

*Spec done. Awaiting user review before invoking writing-plans.*
