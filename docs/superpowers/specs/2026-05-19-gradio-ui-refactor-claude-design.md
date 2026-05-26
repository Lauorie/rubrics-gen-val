# papers_qa Gradio UI Refactor — Claude-style + Live Streaming

**Date:** 2026-05-19
**Project:** `/home/juli/RLM/papers_qa/`
**Goal:** Refactor the existing Gradio web UI (currently ~1380 lines, single file, three layers of patching) into a Claude.ai-style chat interface with real streaming on the left chat panel, a cleaner reasoning panel on the right, and a modular file structure.

---

## 1. Stack decision: keep Gradio, replace `gr.Chatbot` with `gr.HTML`

We keep Gradio because:
- `share=True` (one-line public `*.gradio.live` URL) is a hard requirement.
- Switching to FastAPI/Next.js means re-implementing routing, queue, share tunnel, and concurrency limiting — none of which is the user's problem.
- The existing handler / `stream_ask` / streaming.py infrastructure is solid.

We replace `gr.Chatbot` with our own `gr.HTML` for chat (trace panel is already `gr.HTML`) because:
- `gr.Chatbot`'s DOM is internal: avatars, copy/retry buttons, and message bubble HTML are not under our control — three rounds of CSS hacks have not produced a Claude-pixel-perfect look.
- We need to inject a "thinking progress card" inside the assistant turn while the model is working. `gr.Chatbot` doesn't support this without hacks.
- We need typewriter-style streaming of the final answer with control over chunk size and pacing. `gr.Chatbot` re-renders the whole transcript per yield; with our own HTML, we can yield only the changed last message and let Gradio's diff send minimal updates.

The state across the handler stays as `list[dict[str, str]]` with `role`/`content` keys for backwards compatibility with `streaming.build_history_text` and the `/handler` API consumers (gradio_client tests).

## 2. Streaming UX

### 2.1 During thinking

The assistant bubble appears immediately after the user submits. Its content is a **live progress card** that grows row-by-row as `stream_ask` yields events:

```
✱ 正在分析问题
✱ 检索关键词 ["GSM8K", "Qwen3"] → 命中 12 篇
✱ 读取 Qwen3 Technical Report（76 KB）
✱ 提取预训练评估表
✱ 整合答案中…
```

These rows are **derived from existing iteration events**, not from new LLM calls:

| iteration event | progress row |
|--|--|
| `{type: "iteration", code_blocks: [...]}` where code contains `search_papers(keywords=[...])` | "检索关键词 [...] → 命中 N 篇" (parse keywords + count from stdout) |
| `code_blocks` containing `context[pid]` reference | "读取 {pid}（{N} KB）" |
| `code_blocks` containing `llm_query` / `llm_query_batched` call | "查询 sub-LLM ×{batch_size}" |
| `code_blocks` setting `answer["ready"]` | "整合答案中…" |
| (default fallback) | "推理第 N 轮" |

Zero new LLM calls. The mapping function is `derive_progress_line(code_block) -> str | None` in `papers_qa/ui/render.py`.

### 2.2 When the final answer arrives

The progress card collapses into a small chip: `✓ 8 轮 · 47s`. Below it, the answer text is rendered with a **typewriter effect**: the handler chunks the final string into ~5-character pieces and yields a new chat history snapshot every 80-120 ms.

Mechanics:
- After receiving the `final` event, the handler enters a typewriter loop:
  ```python
  for i in range(0, len(answer), 5):
      partial = answer[: i + 5]
      yield (chat_with_progress + render_assistant(partial), trace, status)
      time.sleep(0.08)
  ```
- Cap: max 600 yields per answer (covers up to ~3000 chars at 5/chunk). Longer answers skip directly to full text after the cap.
- At ~12 fps, Gradio's SSE handles it without backpressure issues (tested in earlier sessions with 4-iteration runs).

### 2.3 Sub-call expansion (optional, in progress card)

If a `llm_query` sub-call took >5s, the progress row gets a small `(已等待 7s)` suffix that auto-updates. This requires timestamps in `stream_ask` event payloads — we already have `iteration_time`, no schema change needed.

## 3. Visual: Claude.ai pixel-targeted

Concrete numbers measured against current claude.ai DOM:

| token | value | source |
|---|---|---|
| body background | `#FAF9F5` | claude.ai body |
| panel background | `#F5F4ED` (chat & trace card) | claude.ai message card |
| code background | `#EEEDE3` | claude.ai inline code |
| primary text | `#3D3D3A` | claude.ai body text |
| muted text | `#6B6B66` | claude.ai timestamps |
| accent | `#C96442` (the actual Claude burnt-orange) | claude.ai logo + send button |
| border hairline | `rgba(0, 0, 0, 0.06)` | claude.ai message border |
| focus ring | `rgba(201, 100, 66, 0.35)` | claude.ai input focus |

Typography:
- UI: `ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` (system stack — claude.ai uses paid Söhne; this is the closest free substitute)
- Body: `Charter, Georgia, ui-serif, serif` (closest to Tiempos)
- Mono (code blocks): `ui-monospace, "JetBrains Mono", Menlo, monospace`

Geometry:
- Base font size: 15.5px; line-height 1.65
- Message vertical gap: 24px
- Message inner padding: 16px 20px
- Border radius: 10px (panel), 8px (chip)
- No drop shadow; rely on flat hairlines

**No avatars.** Following claude.ai's current design — left-aligned for user, slight inset for assistant; differentiated by background tone instead of icons. Removes the entire "double avatar" class of bugs we hit.

Micro-interactions (CSS only, no JS state):
- New message appearance: `opacity: 0 → 1` and `translateY(4px → 0)` over 200ms
- Submit button hover: background `#C96442 → #B85734`
- Textarea focus: border becomes accent + 2px soft focus ring
- Progress card lines: each new row fades in 150ms

## 4. Right panel: flatter iteration cards

Current cards have `<section>`, `<header>`, multiple `<article>` nests, chips, decorative dots — too heavy.

Replacement: each iteration is a single `<details>`:

```html
<details class="iter" data-state="clean" open>
  <summary>
    <span class="iter-n">迭代 3</span>
    <span class="iter-time">6.2s</span>
    <span class="iter-blocks">2 个代码块</span>
  </summary>
  <div class="iter-body">
    <!-- model self-response -->
    <div class="iter-model" hidden-if-empty>...</div>
    <!-- one code/output pair per code_block -->
    <div class="iter-code-pair">
      <pre class="code"><code class="lang-python">...</code></pre>
      <pre class="stdout">...</pre>
    </div>
    <!-- sub-call expansion, if any -->
    <details class="subcall">
      <summary>llm_query × 1 (prompt 88 字, 回复 312 字)</summary>
      <div class="subcall-body">…</div>
    </details>
  </div>
</details>
```

Rules:
- `data-state` ∈ `clean | warn | error | final` → drives left border color (cyan/amber/red/green-burnt)
- **Default expand state: first 3 iterations open, iter 4+ closed**. Stops the right panel from becoming a wall.
- Code blocks: lightweight syntax highlight via hand-written regex (we just need Python keyword + string + comment colors). No `highlight.js`. ~30 lines.
- Sub-call rendering: prompt truncated to 200 chars + response to 400 chars in the summary line; full text in the `<details>` body.

## 5. File structure

Split `scripts/gradio_app.py` (currently ~1380 lines) into a small package + a thin entry:

```
papers_qa/ui/
├── __init__.py          # Exports build_demo
├── theme.py             # gr.themes.Base + .set() tokens (Claude colors)
├── css.py               # The _CSS constant + _HEAD JS
├── render.py            # Pure functions: render_user_msg / render_assistant_msg /
│                        # render_progress_card / render_iter_card / derive_progress_line /
│                        # typewriter_chunks
├── handler.py           # make_chat_handler + typewriter loop
└── highlight.py         # Tiny Python tokenizer for code coloring (~30 lines)

scripts/gradio_app.py    # ~100 lines: parse_args + main + demo composition
tests/test_ui_render.py  # Tests render functions, derive_progress_line, typewriter_chunks
```

Module boundaries:
- **theme.py**: knows nothing about chat / streaming. Exports `build_theme()`.
- **css.py**: pure string. Exports `CSS` and `HEAD_JS`.
- **render.py**: pure functions, no Gradio imports, no state. Each takes data, returns HTML string. Easily unit-testable.
- **handler.py**: imports `papers_qa.streaming.stream_ask` + `render.py`. Owns the typewriter loop. Returns a Gradio-compatible generator.
- **gradio_app.py**: composes the demo, owns CLI argparse, no business logic.

Tests in `tests/test_ui_render.py`:
- `render_progress_card` with various inputs → expected HTML structure
- `derive_progress_line` mapping from code_block to a progress label
- `typewriter_chunks("12345678901234", chunk=5)` → `["12345", "1234567890", "12345678901234"]`
- `render_iter_card` produces the expected `<details>` structure with state class
- `highlight_python("def foo(): pass")` produces colored spans for `def`, `foo`, parens

## 6. Sharing

Unchanged. `demo.launch(share=share, ...)` continues to work. The redesign affects only what Gradio serves; share-tunnel behavior is identical.

## 7. Backward compatibility

What stays the same and must not break:

| Surface | Contract |
|---|---|
| `/handler` Gradio API endpoint | Same `api_name="handler"`, same input/output shape |
| Handler input | `(message: str, history: list[dict[str,str]])` |
| Handler output | `Iterator[tuple[list[dict[str,str]], str, str]]` for `(chat, trace_html, status)` |
| `stream_ask` signature | Unchanged |
| `_messages_to_pairs` | Unchanged |
| `parse_args()` CLI flags | `--share / --no-share / --port / --host / --title / --env-file / --log-level` |
| Env vars | `PAPERS_QA_GRADIO_SHARE / PORT / HOST` |
| Existing 39 tests | All pass without modification |

What changes:
- Chat is rendered via `gr.HTML` instead of `gr.Chatbot`.
- Assistant content during thinking is no longer empty — it's a progress card.
- Final answer streams char-by-char.

## 8. Risks & mitigations

| Severity | Risk | Mitigation |
|---|---|---|
| HIGH | gradio_client tests expect message format `list[{"role": "user"/"assistant", "content": str}]` — must keep this exact shape | Handler still yields this shape. Inside `content`, we'll put pre-rendered HTML strings, which gradio_client will receive verbatim. Existing tests check `chat[1]["role"] == "assistant"` and `"correct_text" in chat[1]["content"]` — both still hold. |
| HIGH | Typewriter at 12 fps × 47s = ~560 yields could backpressure SSE on slow networks | Cap total yields at 600; if answer is longer than ~3000 chars, flush remainder in single yield. Configurable via `PAPERS_QA_TYPEWRITER_FPS` env (default 12). |
| MEDIUM | `derive_progress_line` parses code by regex — fragile if model writes weird code | If no rule matches, fall back to "推理第 N 轮"; never error. Tested. |
| MEDIUM | First iteration may take 5-15s with no events yielded yet → user sees blank assistant bubble briefly | Yield an initial "✱ 正在分析问题..." row immediately when handler enters, before `stream_ask` even starts. |
| LOW | `gr.HTML` doesn't auto-scroll on update — assistant bubble may go below viewport on long answers | Inject ~10 lines of JS via `head=` that scrolls the `.chat-scroll` div to bottom on DOM mutation. |
| LOW | Code syntax highlight via regex breaks on edge cases (raw strings, triple quotes in odd places) | We accept imperfect highlighting; never crash. Falls back to plain monospace if highlight throws. |

## 9. Out of scope (YAGNI)

- True token-by-token streaming from OpenAI/DeepSeek API. Our typewriter is **cosmetic** — RLM returns the full completion at once; we chunk it client-visible-side. Real token streaming requires modifying RLM's `OpenAIClient.completion` to use `stream=True`, plumbing through the LMHandler socket protocol, etc. Big change, out of scope.
- Authentication / user accounts.
- Persistent chat history across sessions.
- Multi-language UI strings (we hardcode Chinese labels; trivial to externalize later).
- Code syntax highlighting beyond Python. The corpus is Python-only.
- Resizable / collapsible right panel. Could add later via JS.

## 10. Verification plan

After implementation:

1. **Unit tests**: `pytest tests/ -q` → all green, 39 existing + 5-7 new.
2. **Boot smoke**: `python scripts/gradio_app.py --port 7861 --no-share`, confirm no traceback, `Running on local URL` appears.
3. **HTML probe**: `curl http://127.0.0.1:7861/ | grep -E 'FAF9F5|C96442|chat-scroll|iter-n'` — confirm Claude tokens + new class names in served HTML.
4. **Real chat E2E**: gradio_client `predict("/handler", "Qwen 3 各个版本模型在 GSM8K 上的结果", [])` → returns Chinese answer with correct numbers; trace contains `<details class="iter"`; final chat[-1].content includes the answer text (rendered into our HTML wrapper).
5. **Manual visual**: open `http://127.0.0.1:7861/` in browser, submit a question, watch:
   - User message appears immediately, fades in
   - Assistant bubble appears with progress card, rows accumulate
   - Right panel iteration cards animate in
   - Final answer types out character-by-character
   - Layout feels like claude.ai
6. **Share smoke**: `python scripts/gradio_app.py --share`, confirm `Running on public URL: https://*.gradio.live` line appears.

Each of these 6 must pass before declaring done.
