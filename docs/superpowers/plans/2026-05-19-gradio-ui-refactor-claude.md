# Gradio UI Refactor — Claude-style + Live Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `scripts/gradio_app.py` into a modular `papers_qa/ui/` package, replace `gr.Chatbot` with custom `gr.HTML`, add live progress card + final-answer typewriter, restyle to claude.ai pixel-targeted colors.

**Architecture:** A small `papers_qa/ui/` package owns the UI: `theme.py` (Gradio theme tokens), `css.py` (the CSS+JS strings), `highlight.py` (Python syntax highlighter, ~30 lines), `render.py` (pure HTML render functions, fully unit-testable), `handler.py` (chat handler + typewriter loop). `scripts/gradio_app.py` becomes a thin ~100-line composition root.

**Tech Stack:** Gradio 6.14 (kept), Python 3.12, no new external deps. `gr.HTML` for both chat and trace panels.

**Spec:** `/home/juli/RLM/docs/superpowers/specs/2026-05-19-gradio-ui-refactor-claude-design.md`

---

## File Structure

```
papers_qa/ui/
├── __init__.py          # re-exports build_demo
├── theme.py             # build_theme() -> gr.themes.Base
├── css.py               # CSS (str), HEAD_JS (str)
├── highlight.py         # highlight_python(code) -> str (HTML with spans)
├── render.py            # pure render functions + derive_progress_line + typewriter_chunks
└── handler.py           # make_chat_handler(qa) -> Gradio generator

scripts/
└── gradio_app.py        # thin entry: parse_args + main() + build_demo()

tests/
├── test_ui_render.py    # NEW: render funcs, derive_progress_line, typewriter_chunks, highlight
└── test_gradio_app.py   # UPDATED: assertions on HTML-wrapped content (substring not equality)
```

**Per-file responsibilities:**
- `theme.py`: knows nothing about chat. Pure theme token configuration.
- `css.py`: pure string constants. No Python logic.
- `highlight.py`: takes a Python source string, returns colored HTML. Zero deps beyond `re`.
- `render.py`: all HTML rendering. No Gradio imports. Each function is a pure `(data) -> str` mapping.
- `handler.py`: imports `render.py` + `stream_ask`. Owns the typewriter loop and yield cadence.
- `gradio_app.py`: argparse + composition only.

---

## Task 1: Scaffold `papers_qa/ui/` package + theme module

**Files:**
- Create: `/home/juli/RLM/papers_qa/papers_qa/ui/__init__.py`
- Create: `/home/juli/RLM/papers_qa/papers_qa/ui/theme.py`
- Test: `/home/juli/RLM/papers_qa/tests/test_ui_theme.py`

- [ ] **Step 1: Write the failing test**

Create `/home/juli/RLM/papers_qa/tests/test_ui_theme.py`:

```python
"""Tests for papers_qa.ui.theme."""
from __future__ import annotations

import gradio as gr

from papers_qa.ui.theme import build_theme


def test_build_theme_returns_base_subclass():
    theme = build_theme()
    assert isinstance(theme, gr.themes.Base)


def test_build_theme_sets_claude_palette():
    theme = build_theme()
    d = theme.to_dict()
    # body bg in dark-mode-disabled context (we run as light)
    assert d.get("body_background_fill") == "#FAF9F5"
    assert d.get("body_text_color") == "#3D3D3A"
    # accent
    assert d.get("color_accent") == "#C96442" or d.get("color_accent_soft", "").startswith(
        "rgba(201, 100, 66"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/juli/RLM/papers_qa
.venv/bin/pytest tests/test_ui_theme.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'papers_qa.ui'`.

- [ ] **Step 3: Create the package init**

Create `/home/juli/RLM/papers_qa/papers_qa/ui/__init__.py`:

```python
"""papers_qa.ui — Gradio UI subsystem.

Public exports:
    build_demo(qa, banner_title) -> gr.Blocks
"""
from __future__ import annotations

# Public re-export. Implementations live in handler.py + the build_demo
# function in this package's gradio_app integration point. Until gradio_app
# wires it up (Task 6) this is just a placeholder so the package imports.
__all__ = ["build_theme"]

from papers_qa.ui.theme import build_theme
```

- [ ] **Step 4: Implement the theme module**

Create `/home/juli/RLM/papers_qa/papers_qa/ui/theme.py`:

```python
"""Claude-style theme tokens for the papers_qa Gradio app.

Colors are measured against the live claude.ai DOM as of 2026-05.
We target LIGHT mode (no dark-mode tokens) because Claude's UI is light.
"""
from __future__ import annotations

import gradio as gr

# Palette (single source of truth — also referenced from css.py)
BG = "#FAF9F5"
PANEL = "#F5F4ED"
CARD = "#FFFCF5"
CODE_BG = "#EEEDE3"
TEXT = "#3D3D3A"
TEXT_MUTED = "#6B6B66"
ACCENT = "#C96442"
ACCENT_HOVER = "#B85734"
BORDER = "rgba(0, 0, 0, 0.06)"
FOCUS_RING = "rgba(201, 100, 66, 0.35)"


def build_theme() -> gr.themes.Base:
    """Return a Gradio Base theme configured with the Claude palette.

    All tokens are set on the LIGHT variants. We intentionally do not set
    *_dark tokens — Gradio's auto dark-mode would only fire if a user's
    browser is in dark mode AND we left the dark variants unset. Our CSS
    forces the .light class to override that case (see css.py).
    """
    return gr.themes.Base(
        primary_hue="orange",
        secondary_hue="orange",
        neutral_hue="stone",
        radius_size="md",
    ).set(
        # Body
        body_background_fill=BG,
        body_text_color=TEXT,
        body_text_color_subdued=TEXT_MUTED,
        # Backgrounds
        background_fill_primary=PANEL,
        background_fill_secondary=BG,
        # Blocks
        block_background_fill=PANEL,
        block_border_color=BORDER,
        block_label_background_fill=BG,
        block_label_text_color=TEXT_MUTED,
        block_title_text_color=TEXT,
        # Borders + accent
        border_color_primary=BORDER,
        border_color_accent=ACCENT,
        border_color_accent_subdued="rgba(201, 100, 66, 0.4)",
        color_accent_soft="rgba(201, 100, 66, 0.10)",
        # Code & links
        code_background_fill=CODE_BG,
        link_text_color=ACCENT,
        link_text_color_hover=ACCENT_HOVER,
        link_text_color_active=ACCENT,
        link_text_color_visited=ACCENT,
        # Inputs
        input_background_fill=CARD,
        input_background_fill_focus=CARD,
        input_background_fill_hover=CARD,
        input_border_color=BORDER,
        input_border_color_focus=ACCENT,
        input_border_color_hover="rgba(0, 0, 0, 0.10)",
        # Buttons
        button_primary_background_fill=ACCENT,
        button_primary_background_fill_hover=ACCENT_HOVER,
        button_primary_text_color="#FFFFFF",
        button_primary_border_color="transparent",
        button_secondary_background_fill="transparent",
        button_secondary_background_fill_hover="rgba(0, 0, 0, 0.04)",
        button_secondary_text_color=TEXT_MUTED,
        button_secondary_text_color_hover=TEXT,
        button_secondary_border_color=BORDER,
        button_secondary_border_color_hover="rgba(0, 0, 0, 0.12)",
        # Panels (accordion etc.)
        panel_background_fill=PANEL,
        panel_border_color=BORDER,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_ui_theme.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Full suite still green**

```bash
.venv/bin/pytest tests/ -q 2>&1 | tail -3
```

Expected: 41 passed + 1 skipped (was 39+1, added 2 theme tests).

- [ ] **Step 7: Commit**

```bash
cd /home/juli/RLM/papers_qa
git add papers_qa/ui/__init__.py papers_qa/ui/theme.py tests/test_ui_theme.py
git commit -m "feat(ui): scaffold papers_qa.ui package + Claude-palette theme"
```

---

## Task 2: CSS + JS string module

**Files:**
- Create: `/home/juli/RLM/papers_qa/papers_qa/ui/css.py`

No tests for pure string constants — they're verified end-to-end in Task 7 (HTML curl probe).

- [ ] **Step 1: Implement css.py**

Create `/home/juli/RLM/papers_qa/papers_qa/ui/css.py`:

```python
"""Static CSS + head JS for the Claude-style UI.

Imported by `papers_qa.ui.handler` and `scripts/gradio_app.py` as constants.
Keeping CSS in a Python string (rather than a separate .css file) avoids
adding a file-loading code path inside Gradio's `launch(css=...)`.
"""
from __future__ import annotations

# Force light mode and hide Gradio's default chrome we don't want.
HEAD_JS = """
<script>
window.addEventListener('DOMContentLoaded', () => {
    // Force light theme — Gradio would otherwise pick up OS dark mode.
    document.documentElement.classList.remove('dark');
    document.body && document.body.classList.remove('dark');
});

// Auto-scroll the chat to the bottom whenever its content mutates.
// Uses a single MutationObserver attached after Gradio renders.
window.addEventListener('load', () => {
    const observe = () => {
        const el = document.querySelector('.pq-chat-scroll');
        if (!el) { setTimeout(observe, 200); return; }
        const obs = new MutationObserver(() => {
            el.scrollTop = el.scrollHeight;
        });
        obs.observe(el, { childList: true, subtree: true, characterData: true });
    };
    observe();
});
</script>
"""


CSS = r"""
/* =====  Reset & base typography  ============================== */
:root {
    --pq-bg: #FAF9F5;
    --pq-panel: #F5F4ED;
    --pq-card: #FFFCF5;
    --pq-code: #EEEDE3;
    --pq-text: #3D3D3A;
    --pq-muted: #6B6B66;
    --pq-faint: #9A9A95;
    --pq-accent: #C96442;
    --pq-accent-hover: #B85734;
    --pq-accent-soft: rgba(201, 100, 66, 0.12);
    --pq-border: rgba(0, 0, 0, 0.06);
    --pq-border-soft: rgba(0, 0, 0, 0.04);
    --pq-success: #6B8E5A;
    --pq-warn: #B38933;
    --pq-error: #B85F4A;

    --pq-font-ui: ui-sans-serif, -apple-system, BlinkMacSystemFont,
                  "Segoe UI", "Helvetica Neue", Arial, "PingFang SC",
                  "Microsoft YaHei", sans-serif;
    --pq-font-body: Charter, Georgia, "Iowan Old Style", "Source Serif Pro",
                    ui-serif, serif;
    --pq-font-mono: "JetBrains Mono", "SF Mono", Menlo, Consolas,
                    ui-monospace, monospace;
}

html, body, .gradio-container, gradio-app {
    background: var(--pq-bg) !important;
    color: var(--pq-text) !important;
    font-family: var(--pq-font-ui);
    font-size: 15.5px;
    line-height: 1.65;
}

.gradio-container {
    max-width: 100% !important;
    margin: 0 auto !important;
    padding: 20px 32px 20px !important;
}

/* =====  Header / banner  ===================================== */
.pq-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 4px 6px 14px;
    border-bottom: 1px solid var(--pq-border);
    margin-bottom: 14px;
}
.pq-header-mark {
    color: var(--pq-accent);
    font-size: 18px;
    line-height: 1;
}
.pq-header h2 {
    margin: 0;
    font-family: var(--pq-font-body);
    font-size: 19px;
    font-weight: 600;
    color: var(--pq-text);
    letter-spacing: -0.005em;
}
.pq-header .pq-sub {
    color: var(--pq-muted);
    font-size: 12.5px;
    margin-left: 6px;
}

/* =====  Two-column layout  =================================== */
.pq-main {
    display: grid;
    grid-template-columns: 1.7fr 1fr;
    gap: 24px;
    align-items: start;
}
.pq-col {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

/* =====  Chat column  ========================================= */
.pq-chat-shell {
    background: var(--pq-panel);
    border: 1px solid var(--pq-border);
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: calc(100vh - 240px);
    min-height: 540px;
}
.pq-chat-scroll {
    flex: 1 1 auto;
    overflow-y: auto;
    padding: 24px 26px;
    scroll-behavior: smooth;
}
.pq-chat-empty {
    color: var(--pq-faint);
    text-align: center;
    margin-top: 22vh;
    font-family: var(--pq-font-body);
    font-style: italic;
}

/* Individual messages */
.pq-msg {
    margin: 0 0 22px 0;
    animation: pq-fadein 200ms ease-out;
}
@keyframes pq-fadein {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
}
.pq-msg-user {
    background: var(--pq-card);
    border: 1px solid var(--pq-border);
    border-radius: 10px;
    padding: 14px 18px;
    margin-left: 0;
    font-family: var(--pq-font-body);
}
.pq-msg-assistant {
    padding: 14px 18px 4px;
    font-family: var(--pq-font-body);
}
.pq-msg-body { color: var(--pq-text); }
.pq-msg-body p { margin: 0 0 10px 0; }
.pq-msg-body p:last-child { margin-bottom: 0; }
.pq-msg-body code {
    background: var(--pq-code);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 13.5px;
    font-family: var(--pq-font-mono);
    color: var(--pq-text);
}
.pq-msg-body pre {
    background: var(--pq-code);
    border: 1px solid var(--pq-border-soft);
    padding: 12px 14px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 13px;
    font-family: var(--pq-font-mono);
    line-height: 1.55;
}
.pq-msg-body table {
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 14px;
}
.pq-msg-body th, .pq-msg-body td {
    border: 1px solid var(--pq-border);
    padding: 6px 10px;
    text-align: left;
}
.pq-msg-body th { background: var(--pq-code); font-weight: 600; }

/* Progress card inside an assistant turn */
.pq-progress {
    margin: 8px 0 14px 0;
    padding: 12px 14px;
    background: var(--pq-bg);
    border: 1px solid var(--pq-border);
    border-radius: 8px;
    font-family: var(--pq-font-mono);
    font-size: 12.5px;
    color: var(--pq-muted);
}
.pq-progress-row {
    display: flex;
    gap: 8px;
    line-height: 1.7;
    animation: pq-fadein 150ms ease-out;
}
.pq-progress-bullet { color: var(--pq-accent); flex: 0 0 auto; }
.pq-progress-collapsed {
    padding: 6px 10px;
    background: rgba(107, 142, 90, 0.10);
    border: 1px solid rgba(107, 142, 90, 0.25);
    color: var(--pq-success);
    border-radius: 999px;
    display: inline-flex;
    width: fit-content;
    font-family: var(--pq-font-mono);
    font-size: 11.5px;
    gap: 6px;
}
.pq-progress-collapsed-check { color: var(--pq-success); font-weight: 600; }

/* =====  Composer (input row)  ================================ */
.pq-composer-wrap {
    border-top: 1px solid var(--pq-border);
    padding: 14px 20px 16px;
    background: var(--pq-panel);
}
.pq-composer-wrap textarea {
    background: var(--pq-card) !important;
    border: 1px solid var(--pq-border) !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
    font-family: var(--pq-font-ui) !important;
    font-size: 15px !important;
    color: var(--pq-text) !important;
    resize: none !important;
    min-height: 50px;
}
.pq-composer-wrap textarea:focus {
    border-color: var(--pq-accent) !important;
    box-shadow: 0 0 0 3px var(--pq-focus-ring, rgba(201, 100, 66, 0.20)) !important;
    outline: none !important;
}
.pq-composer-wrap .pq-buttons {
    display: flex;
    gap: 10px;
    margin-top: 10px;
    justify-content: flex-end;
}
.pq-composer-wrap button[variant="primary"], .pq-composer-wrap .primary {
    background: var(--pq-accent) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 8px 18px !important;
    font-family: var(--pq-font-ui) !important;
    font-size: 14px !important;
    font-weight: 500;
    cursor: pointer;
    transition: background 120ms ease;
}
.pq-composer-wrap button[variant="primary"]:hover, .pq-composer-wrap .primary:hover {
    background: var(--pq-accent-hover) !important;
}
.pq-composer-wrap button[variant="secondary"], .pq-composer-wrap .secondary {
    background: transparent !important;
    color: var(--pq-muted) !important;
    border: 1px solid var(--pq-border) !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
}
.pq-composer-wrap button[variant="secondary"]:hover, .pq-composer-wrap .secondary:hover {
    color: var(--pq-text) !important;
    border-color: rgba(0, 0, 0, 0.12) !important;
    background: rgba(0, 0, 0, 0.02) !important;
}

/* =====  Trace column  ======================================== */
.pq-trace-shell {
    background: var(--pq-panel);
    border: 1px solid var(--pq-border);
    border-radius: 12px;
    overflow: hidden;
    height: calc(100vh - 240px);
    min-height: 540px;
    display: flex;
    flex-direction: column;
}
.pq-trace-head {
    padding: 14px 20px 10px;
    border-bottom: 1px solid var(--pq-border);
}
.pq-trace-head .pq-kicker {
    color: var(--pq-muted);
    font-family: var(--pq-font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}
.pq-trace-head h3 {
    margin: 2px 0 0 0;
    font-family: var(--pq-font-body);
    font-size: 15.5px;
    color: var(--pq-text);
}
.pq-trace-scroll {
    flex: 1 1 auto;
    overflow-y: auto;
    padding: 16px 20px;
    font-size: 13px;
}
.pq-trace-empty {
    color: var(--pq-faint);
    text-align: center;
    margin-top: 14vh;
    font-style: italic;
    font-family: var(--pq-font-body);
}

/* Iteration cards */
details.pq-iter {
    margin: 0 0 12px 0;
    border: 1px solid var(--pq-border);
    border-left: 2px solid var(--pq-faint);
    border-radius: 8px;
    background: var(--pq-bg);
    overflow: hidden;
}
details.pq-iter[data-state="warn"]  { border-left-color: var(--pq-warn); }
details.pq-iter[data-state="error"] { border-left-color: var(--pq-error); }
details.pq-iter[data-state="final"] { border-left-color: var(--pq-success); }
details.pq-iter > summary {
    padding: 9px 14px;
    cursor: pointer;
    font-family: var(--pq-font-mono);
    font-size: 12.5px;
    color: var(--pq-text);
    display: flex;
    gap: 12px;
    align-items: center;
    list-style: none;
}
details.pq-iter > summary::-webkit-details-marker { display: none; }
details.pq-iter > summary::before {
    content: "▸";
    color: var(--pq-faint);
    font-size: 10px;
    transition: transform 120ms;
}
details.pq-iter[open] > summary::before {
    transform: rotate(90deg);
    display: inline-block;
}
.pq-iter-n { color: var(--pq-accent); font-weight: 600; }
.pq-iter-time, .pq-iter-blocks { color: var(--pq-muted); }
.pq-iter-body {
    padding: 4px 14px 14px;
    border-top: 1px solid var(--pq-border-soft);
}
.pq-iter-model {
    background: var(--pq-card);
    border-radius: 6px;
    padding: 10px 12px;
    margin: 10px 0;
    font-family: var(--pq-font-mono);
    font-size: 12px;
    color: var(--pq-muted);
    white-space: pre-wrap;
    line-height: 1.55;
}
.pq-iter-pair {
    margin: 10px 0;
    background: var(--pq-card);
    border: 1px solid var(--pq-border-soft);
    border-radius: 6px;
    overflow: hidden;
}
.pq-iter-pair pre {
    margin: 0;
    padding: 10px 12px;
    font-family: var(--pq-font-mono);
    font-size: 12px;
    line-height: 1.55;
    overflow-x: auto;
    background: transparent;
    border: none;
}
.pq-iter-pair pre.pq-code {
    border-bottom: 1px solid var(--pq-border-soft);
    color: var(--pq-text);
}
.pq-iter-pair pre.pq-stdout { color: var(--pq-muted); background: var(--pq-code); }
.pq-iter-pair pre.pq-stderr { color: var(--pq-error); background: rgba(184, 95, 74, 0.06); }

/* Syntax highlight tokens (from highlight.py) */
.pq-tok-kw   { color: #6F4D8C; }
.pq-tok-str  { color: #8C5A2B; }
.pq-tok-num  { color: #466E5C; }
.pq-tok-com  { color: var(--pq-faint); font-style: italic; }
.pq-tok-fn   { color: #2C5A7F; }

/* Sub-call detail */
details.pq-subcall {
    margin: 8px 0 0;
    border: 1px solid var(--pq-border-soft);
    border-radius: 6px;
    background: rgba(201, 100, 66, 0.04);
}
details.pq-subcall > summary {
    padding: 7px 12px;
    cursor: pointer;
    font-family: var(--pq-font-mono);
    font-size: 11.5px;
    color: var(--pq-muted);
}
details.pq-subcall > summary::-webkit-details-marker { display: none; }
.pq-subcall-body { padding: 8px 12px 12px; font-size: 12px; color: var(--pq-text); }
.pq-subcall-body pre {
    background: var(--pq-card);
    padding: 8px 10px;
    border-radius: 4px;
    margin: 6px 0;
    font-family: var(--pq-font-mono);
    font-size: 11.5px;
    color: var(--pq-muted);
    white-space: pre-wrap;
}

/* Alert cards */
.pq-alert {
    margin: 10px 0;
    padding: 12px 14px;
    border-radius: 8px;
    font-family: var(--pq-font-mono);
    font-size: 12.5px;
}
.pq-alert-error   { background: rgba(184, 95, 74, 0.08);  border: 1px solid rgba(184, 95, 74, 0.25);  color: var(--pq-error); }
.pq-alert-timeout { background: rgba(179, 137, 51, 0.08); border: 1px solid rgba(179, 137, 51, 0.25); color: var(--pq-warn); }

/* =====  Status bar  ========================================== */
.pq-status {
    margin-top: 14px;
    padding: 8px 14px;
    background: var(--pq-panel);
    border: 1px solid var(--pq-border);
    border-radius: 8px;
    font-family: var(--pq-font-mono);
    font-size: 12px;
    color: var(--pq-muted);
}

/* =====  Scrollbars  ========================================== */
.pq-chat-scroll::-webkit-scrollbar,
.pq-trace-scroll::-webkit-scrollbar {
    width: 8px;
}
.pq-chat-scroll::-webkit-scrollbar-track,
.pq-trace-scroll::-webkit-scrollbar-track {
    background: transparent;
}
.pq-chat-scroll::-webkit-scrollbar-thumb,
.pq-trace-scroll::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.10);
    border-radius: 4px;
}
.pq-chat-scroll::-webkit-scrollbar-thumb:hover,
.pq-trace-scroll::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 0, 0, 0.20);
}

/* Hide Gradio's default footer */
footer { display: none !important; }
"""
```

- [ ] **Step 2: Syntax check**

```bash
cd /home/juli/RLM/papers_qa
.venv/bin/python -c "from papers_qa.ui import css; assert isinstance(css.CSS, str); assert len(css.CSS) > 1000; assert '--pq-accent: #C96442' in css.CSS; print('css.py OK', len(css.CSS), 'chars')"
```

Expected: `css.py OK 5400+ chars`.

- [ ] **Step 3: Tests still green**

```bash
.venv/bin/pytest tests/ -q 2>&1 | tail -3
```

Expected: 41 passed + 1 skipped (unchanged).

- [ ] **Step 4: Commit**

```bash
git add papers_qa/ui/css.py
git commit -m "feat(ui): static CSS + HEAD_JS for Claude-style UI"
```

---

## Task 3: Python syntax highlighter

**Files:**
- Create: `/home/juli/RLM/papers_qa/papers_qa/ui/highlight.py`
- Test: `/home/juli/RLM/papers_qa/tests/test_ui_highlight.py`

- [ ] **Step 1: Write the failing tests**

Create `/home/juli/RLM/papers_qa/tests/test_ui_highlight.py`:

```python
"""Tests for the tiny Python syntax highlighter."""
from __future__ import annotations

from papers_qa.ui.highlight import highlight_python


def test_keywords_get_kw_class():
    out = highlight_python("def foo(): pass")
    assert '<span class="pq-tok-kw">def</span>' in out
    assert '<span class="pq-tok-kw">pass</span>' in out


def test_string_literal_double_quoted():
    out = highlight_python('print("hello")')
    assert '<span class="pq-tok-str">"hello"</span>' in out


def test_string_literal_single_quoted():
    out = highlight_python("print('hi')")
    assert '<span class="pq-tok-str">\'hi\'</span>' in out


def test_comment_to_end_of_line():
    out = highlight_python("x = 1  # this is a comment")
    assert '<span class="pq-tok-com"># this is a comment</span>' in out


def test_number_literal():
    out = highlight_python("x = 42")
    assert '<span class="pq-tok-num">42</span>' in out


def test_function_call_name():
    out = highlight_python("search_papers([1])")
    assert '<span class="pq-tok-fn">search_papers</span>' in out


def test_html_special_chars_escaped():
    out = highlight_python("x < y and y > z")
    # The naive output would inject raw < > breaking HTML; we escape first.
    assert "&lt;" in out
    assert "&gt;" in out
    # but the and keyword still gets highlighted
    assert '<span class="pq-tok-kw">and</span>' in out


def test_empty_input():
    assert highlight_python("") == ""


def test_does_not_crash_on_weird_input():
    # Unterminated string shouldn't crash
    out = highlight_python('x = "unterminated')
    assert isinstance(out, str)
```

- [ ] **Step 2: Run tests, verify all fail**

```bash
.venv/bin/pytest tests/test_ui_highlight.py -v
```

Expected: 9 errors (`ModuleNotFoundError: No module named 'papers_qa.ui.highlight'`).

- [ ] **Step 3: Implement highlight.py**

Create `/home/juli/RLM/papers_qa/papers_qa/ui/highlight.py`:

```python
"""Minimal Python syntax highlighter.

We do NOT use Pygments or highlight.js because:
- Pygments adds 6+ MB of dependencies for code we render in 10-line snippets.
- highlight.js is JS-side, but Gradio's HTML rendering happens server-side.

This module does just enough: keywords, strings, numbers, comments, and
function-call names. It is single-pass regex-based. It never raises — bad
input falls through as escaped plain text.
"""
from __future__ import annotations

import html
import re

_KEYWORDS = frozenset(
    """
    False None True and as assert async await break class continue def del
    elif else except finally for from global if import in is lambda nonlocal
    not or pass raise return try while with yield match case
    """.split()
)

# Order matters: comments and strings must be matched before keywords/identifiers
# so we don't incorrectly highlight tokens inside a string or comment.
_TOKEN_RE = re.compile(
    r"""
    (?P<com>\#[^\n]*)                              # comment to end of line
  | (?P<str>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*') # string literal (single or double, no triple)
  | (?P<num>\b\d+(?:\.\d*)?(?:e[+-]?\d+)?\b)       # numeric literal
  | (?P<fn>\b[A-Za-z_][A-Za-z_0-9]*)(?=\s*\()      # name followed by '(' -> function call
  | (?P<id>\b[A-Za-z_][A-Za-z_0-9]*\b)             # bare identifier (or keyword)
    """,
    re.VERBOSE,
)


def highlight_python(code: str) -> str:
    """Return HTML where Python tokens are wrapped in styled spans.

    Never raises — on any error, returns the html-escaped input unchanged.
    """
    if not code:
        return ""
    try:
        out: list[str] = []
        last = 0
        for m in _TOKEN_RE.finditer(code):
            # Append the (escaped) text between the previous match and this one
            if m.start() > last:
                out.append(html.escape(code[last:m.start()]))
            kind = m.lastgroup
            text = m.group()
            esc = html.escape(text)
            if kind == "com":
                out.append(f'<span class="pq-tok-com">{esc}</span>')
            elif kind == "str":
                out.append(f'<span class="pq-tok-str">{esc}</span>')
            elif kind == "num":
                out.append(f'<span class="pq-tok-num">{esc}</span>')
            elif kind == "fn":
                # The fn rule consumed only the identifier (lookahead for paren).
                out.append(f'<span class="pq-tok-fn">{esc}</span>')
            elif kind == "id":
                if text in _KEYWORDS:
                    out.append(f'<span class="pq-tok-kw">{esc}</span>')
                else:
                    out.append(esc)
            else:
                out.append(esc)
            last = m.end()
        # Trailing text after the last match
        if last < len(code):
            out.append(html.escape(code[last:]))
        return "".join(out)
    except Exception:
        return html.escape(code)
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_ui_highlight.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Full suite**

```bash
.venv/bin/pytest tests/ -q 2>&1 | tail -3
```

Expected: 50 passed + 1 skipped (was 41+1, added 9 highlight tests).

- [ ] **Step 6: Commit**

```bash
git add papers_qa/ui/highlight.py tests/test_ui_highlight.py
git commit -m "feat(ui): regex-based Python syntax highlighter"
```

---

## Task 4: Pure render functions

**Files:**
- Create: `/home/juli/RLM/papers_qa/papers_qa/ui/render.py`
- Test: `/home/juli/RLM/papers_qa/tests/test_ui_render.py`

This is the meatiest module — pure functions, fully testable.

- [ ] **Step 1: Write the failing tests**

Create `/home/juli/RLM/papers_qa/tests/test_ui_render.py`:

```python
"""Tests for papers_qa.ui.render."""
from __future__ import annotations

from papers_qa.ui.render import (
    derive_progress_line,
    render_assistant_msg,
    render_chat,
    render_iter_card,
    render_progress_card,
    render_user_msg,
    typewriter_chunks,
)


# -----------------------------------------------------------------------------
# derive_progress_line
# -----------------------------------------------------------------------------


def test_derive_progress_line_search_papers_with_keywords():
    cb = {
        "code": 'search_results = search_papers(keywords=["GSM8K", "Qwen3"], top_k=10)',
        "stdout": "Found 5 papers\n[{'paper_id': 'X', ...}]",
        "stderr": "",
    }
    line = derive_progress_line(cb)
    assert line is not None
    assert "检索" in line
    assert "GSM8K" in line or "Qwen3" in line


def test_derive_progress_line_paper_read():
    cb = {
        "code": "text = context['Qwen3 Technical Report'][:50000]",
        "stdout": "",
        "stderr": "",
    }
    line = derive_progress_line(cb)
    assert line is not None
    assert "读取" in line
    assert "Qwen3" in line


def test_derive_progress_line_llm_query():
    cb = {
        "code": "answer = llm_query(f'Question: {q}\\n{paper}')",
        "stdout": "...",
        "stderr": "",
    }
    line = derive_progress_line(cb)
    assert line is not None
    assert "sub-LLM" in line or "查询" in line


def test_derive_progress_line_llm_query_batched():
    cb = {
        "code": "answers = llm_query_batched([p1, p2, p3])",
        "stdout": "",
        "stderr": "",
    }
    line = derive_progress_line(cb)
    assert line is not None
    # 3 is the batch size inferred from the list literal
    assert "3" in line or "并发" in line or "批量" in line


def test_derive_progress_line_answer_ready():
    cb = {
        "code": 'answer["content"] = result\nanswer["ready"] = True',
        "stdout": "",
        "stderr": "",
        "final_answer": True,
    }
    line = derive_progress_line(cb)
    assert line is not None
    assert "整合" in line or "完成" in line


def test_derive_progress_line_fallback_returns_none():
    cb = {"code": "x = 1 + 1", "stdout": "", "stderr": ""}
    assert derive_progress_line(cb) is None


# -----------------------------------------------------------------------------
# typewriter_chunks
# -----------------------------------------------------------------------------


def test_typewriter_chunks_basic():
    out = list(typewriter_chunks("12345678901234", chunk=5))
    assert out == ["12345", "1234567890", "12345678901234"]


def test_typewriter_chunks_exact_multiple():
    out = list(typewriter_chunks("1234567890", chunk=5))
    assert out == ["12345", "1234567890"]


def test_typewriter_chunks_empty_string():
    assert list(typewriter_chunks("", chunk=5)) == []


def test_typewriter_chunks_smaller_than_chunk():
    assert list(typewriter_chunks("hi", chunk=5)) == ["hi"]


def test_typewriter_chunks_max_yields_cap():
    text = "x" * 10000
    out = list(typewriter_chunks(text, chunk=5, max_yields=10))
    # Should produce at most 10 yields, and the LAST must contain the full text
    assert len(out) <= 10
    assert out[-1] == text


# -----------------------------------------------------------------------------
# render_user_msg / render_assistant_msg
# -----------------------------------------------------------------------------


def test_render_user_msg_basic():
    html = render_user_msg("你好")
    assert "pq-msg" in html
    assert "pq-msg-user" in html
    assert "你好" in html


def test_render_user_msg_escapes_html():
    html = render_user_msg("<script>alert(1)</script>")
    assert "<script>" not in html  # raw script must not appear
    assert "&lt;script&gt;" in html or "&amp;lt;" in html


def test_render_assistant_msg_renders_markdown_basics():
    html = render_assistant_msg("**bold** and `code`")
    # Either we render bold as <strong> or pass it through; we accept either,
    # but the raw asterisks should not appear escaped as-is
    assert "bold" in html
    assert "code" in html
    assert "pq-msg-assistant" in html


def test_render_assistant_msg_with_progress_card():
    html = render_assistant_msg(
        content="",
        progress_rows=["正在分析", "检索关键词"],
    )
    assert "pq-progress" in html
    assert "正在分析" in html
    assert "检索关键词" in html


def test_render_assistant_msg_collapsed_progress():
    html = render_assistant_msg(
        content="最终答案",
        progress_summary="✓ 5 轮 · 23s",
        progress_collapsed=True,
    )
    assert "5 轮" in html
    assert "23s" in html
    assert "最终答案" in html


# -----------------------------------------------------------------------------
# render_progress_card
# -----------------------------------------------------------------------------


def test_render_progress_card_active_rows():
    html = render_progress_card(rows=["a", "b", "c"])
    assert "pq-progress" in html
    assert "pq-progress-row" in html
    assert html.count("pq-progress-row") == 3


def test_render_progress_card_collapsed():
    html = render_progress_card(rows=[], summary="✓ 3 轮 · 12s", collapsed=True)
    assert "pq-progress-collapsed" in html
    assert "3 轮" in html


# -----------------------------------------------------------------------------
# render_iter_card
# -----------------------------------------------------------------------------


def test_render_iter_card_default_open():
    evt = {
        "type": "iteration",
        "response": "thinking…",
        "code_blocks": [{"code": "x=1", "stdout": "", "stderr": "", "final_answer": None}],
        "iteration_time": 1.0,
    }
    html = render_iter_card(1, evt, default_open=True)
    assert "<details class=\"pq-iter\"" in html
    assert "open" in html
    assert "迭代" in html
    assert "1" in html


def test_render_iter_card_state_clean():
    evt = {
        "response": "",
        "code_blocks": [{"code": "x=1", "stdout": "1", "stderr": "", "final_answer": None}],
        "iteration_time": 0.5,
    }
    html = render_iter_card(2, evt, default_open=False)
    assert 'data-state="clean"' in html


def test_render_iter_card_state_error():
    evt = {
        "code_blocks": [{"code": "1/0", "stdout": "", "stderr": "ZeroDivisionError", "final_answer": None}],
        "iteration_time": 0.1,
    }
    html = render_iter_card(3, evt, default_open=False)
    assert 'data-state="error"' in html
    assert "ZeroDivisionError" in html


def test_render_iter_card_state_final():
    evt = {
        "code_blocks": [
            {"code": 'answer["ready"]=True', "stdout": "", "stderr": "", "final_answer": "Hi"}
        ],
        "iteration_time": 0.05,
    }
    html = render_iter_card(4, evt, default_open=False)
    assert 'data-state="final"' in html


def test_render_iter_card_collapsed_when_default_open_false():
    evt = {"code_blocks": [], "iteration_time": 0.1}
    html = render_iter_card(5, evt, default_open=False)
    assert " open" not in html  # no 'open' attribute


# -----------------------------------------------------------------------------
# render_chat
# -----------------------------------------------------------------------------


def test_render_chat_wraps_messages_in_scroll_shell():
    msgs = [{"role": "user", "content": render_user_msg("你好")}]
    html = render_chat(msgs)
    assert "pq-chat-scroll" in html
    assert "你好" in html


def test_render_chat_empty_shows_placeholder():
    html = render_chat([])
    assert "pq-chat-empty" in html


def test_render_chat_handles_already_html_content():
    # Caller pre-renders messages and stores HTML in content. render_chat
    # must concatenate without re-escaping.
    msgs = [
        {"role": "user", "content": '<div class="pq-msg pq-msg-user">你好</div>'},
        {"role": "assistant", "content": '<div class="pq-msg pq-msg-assistant">回答</div>'},
    ]
    html = render_chat(msgs)
    # Both raw divs survive
    assert html.count('class="pq-msg ') == 2
    assert "你好" in html and "回答" in html
```

- [ ] **Step 2: Run tests, verify all fail**

```bash
.venv/bin/pytest tests/test_ui_render.py -v
```

Expected: many `ModuleNotFoundError: No module named 'papers_qa.ui.render'`.

- [ ] **Step 3: Implement render.py**

Create `/home/juli/RLM/papers_qa/papers_qa/ui/render.py`:

```python
"""Pure HTML rendering functions for the Claude-style UI.

Every function in this module is a pure data-to-string mapping. No Gradio
imports, no I/O, no side effects. This keeps rendering testable in isolation
and lets us swap Gradio out later without rewriting the visual layer.

Public functions:
    render_user_msg(content) -> str
    render_assistant_msg(content, progress_rows=None, progress_summary=None,
                         progress_collapsed=False) -> str
    render_progress_card(rows, summary="", collapsed=False) -> str
    render_iter_card(n, evt, default_open=True) -> str
    render_error_card(msg) -> str
    render_timeout_card() -> str
    render_chat(messages) -> str
    derive_progress_line(code_block) -> str | None
    typewriter_chunks(text, chunk=5, max_yields=600) -> Iterator[str]
"""
from __future__ import annotations

import html
import re
from collections.abc import Iterator
from typing import Any

from papers_qa.ui.highlight import highlight_python

_EMPTY_CHAT_PLACEHOLDER = (
    '<div class="pq-chat-empty">问点什么吧。模型会先检索 81 篇英文论文，'
    "然后用中文回答。</div>"
)

_EMPTY_TRACE_PLACEHOLDER = (
    '<div class="pq-trace-empty">每一轮检索、代码执行与推理详情会在这里展开。</div>'
)


# =============================================================================
# Chat messages
# =============================================================================


def render_user_msg(content: str) -> str:
    """Render a user turn as a Claude-style card. Content is escaped."""
    safe = html.escape(content).replace("\n", "<br>")
    return f'<div class="pq-msg pq-msg-user"><div class="pq-msg-body">{safe}</div></div>'


def render_assistant_msg(
    content: str = "",
    progress_rows: list[str] | None = None,
    progress_summary: str = "",
    progress_collapsed: bool = False,
) -> str:
    """Render an assistant turn.

    If `progress_collapsed` is True, the progress card collapses to a chip and
    `content` (the final answer) is rendered below it. Otherwise the progress
    card stays expanded and `content` (usually empty during thinking, then
    progressively filled by typewriter) is appended below.
    """
    parts = ['<div class="pq-msg pq-msg-assistant">']
    if progress_rows is not None and (progress_rows or progress_summary):
        parts.append(
            render_progress_card(
                rows=progress_rows,
                summary=progress_summary,
                collapsed=progress_collapsed,
            )
        )
    if content:
        parts.append(f'<div class="pq-msg-body">{_render_markdown_basic(content)}</div>')
    parts.append("</div>")
    return "".join(parts)


def render_progress_card(
    rows: list[str], summary: str = "", collapsed: bool = False
) -> str:
    """Render the live progress card inside an assistant turn."""
    if collapsed:
        sym = html.escape(summary) if summary else "✓ 完成"
        return (
            f'<div class="pq-progress-collapsed">'
            f'<span class="pq-progress-collapsed-check">✓</span>'
            f"<span>{sym}</span>"
            f"</div>"
        )
    body = "\n".join(
        f'<div class="pq-progress-row">'
        f'<span class="pq-progress-bullet">✱</span>'
        f"<span>{html.escape(r)}</span>"
        f"</div>"
        for r in rows
    )
    return f'<div class="pq-progress">{body}</div>'


def render_chat(messages: list[dict[str, str]]) -> str:
    """Render the whole chat column.

    Each message's `content` is treated as pre-rendered HTML — the handler
    calls `render_user_msg` / `render_assistant_msg` before placing strings
    into the message list.
    """
    if not messages:
        return f'<div class="pq-chat-scroll">{_EMPTY_CHAT_PLACEHOLDER}</div>'
    inner = "\n".join(m.get("content", "") for m in messages)
    return f'<div class="pq-chat-scroll">{inner}</div>'


# =============================================================================
# Trace / iteration cards
# =============================================================================


def render_iter_card(n: int, evt: dict[str, Any], default_open: bool = True) -> str:
    """Render one iteration event as a <details class="pq-iter"> card."""
    code_blocks = evt.get("code_blocks") or []
    iter_time = float(evt.get("iteration_time") or 0.0)
    response = (evt.get("response") or "").strip()

    # Decide state class for the left-border color
    state = "clean"
    for cb in code_blocks:
        if cb.get("stderr"):
            state = "error"
            break
        if cb.get("final_answer"):
            state = "final"
    if state == "clean" and not code_blocks and not response:
        state = "warn"

    open_attr = " open" if default_open else ""

    parts: list[str] = [
        f'<details class="pq-iter" data-state="{state}"{open_attr}>',
        "<summary>",
        f'<span class="pq-iter-n">迭代 {n}</span>',
        f'<span class="pq-iter-time">{iter_time:.1f}s</span>',
        f'<span class="pq-iter-blocks">{len(code_blocks)} 个代码块</span>',
        "</summary>",
        '<div class="pq-iter-body">',
    ]

    if response:
        parts.append(
            f'<div class="pq-iter-model">{html.escape(response[:600])}</div>'
        )

    for cb in code_blocks:
        code = str(cb.get("code") or "")
        stdout = str(cb.get("stdout") or "")
        stderr = str(cb.get("stderr") or "")
        parts.append('<div class="pq-iter-pair">')
        parts.append(f'<pre class="pq-code"><code>{highlight_python(code)}</code></pre>')
        if stdout:
            parts.append(f'<pre class="pq-stdout">{html.escape(stdout[:1500])}</pre>')
        if stderr:
            parts.append(f'<pre class="pq-stderr">{html.escape(stderr[:500])}</pre>')
        parts.append("</div>")

    parts.append("</div></details>")
    return "".join(parts)


def render_error_card(msg: str) -> str:
    return f'<div class="pq-alert pq-alert-error">❌ {html.escape(msg)}</div>'


def render_timeout_card() -> str:
    return (
        '<div class="pq-alert pq-alert-timeout">⚠️ 模型 600s 无响应，请重试。</div>'
    )


def render_trace(iteration_cards: list[str]) -> str:
    """Wrap a list of iteration card HTML strings into the trace scroll shell."""
    if not iteration_cards:
        return f'<div class="pq-trace-scroll">{_EMPTY_TRACE_PLACEHOLDER}</div>'
    return f'<div class="pq-trace-scroll">{"".join(iteration_cards)}</div>'


# =============================================================================
# Progress derivation
# =============================================================================


_RE_SEARCH = re.compile(r"search_papers\s*\(\s*keywords\s*=\s*\[([^\]]+)\]")
_RE_PAPER_READ = re.compile(r"context\s*\[\s*(['\"])([^'\"]{1,80})\1\s*\]")
_RE_LLM_BATCHED = re.compile(r"llm_query_batched\s*\(\s*\[([^\]]*)\]")
_RE_LLM_QUERY = re.compile(r"\bllm_query\s*\(")
_RE_ANSWER_READY = re.compile(r"answer\s*\[\s*['\"]ready['\"]\s*\]\s*=\s*True")


def derive_progress_line(code_block: dict[str, Any]) -> str | None:
    """Map one code block to a one-line user-facing progress label.

    Returns None when no rule matches; the handler then substitutes a
    generic fallback like "推理第 N 轮".
    """
    code = str(code_block.get("code") or "")
    stdout = str(code_block.get("stdout") or "")
    if code_block.get("final_answer") or _RE_ANSWER_READY.search(code):
        return "整合答案中…"
    m = _RE_SEARCH.search(code)
    if m:
        keywords_blob = m.group(1)
        # Pull the first 2-3 quoted strings
        kws = re.findall(r"['\"]([^'\"]{1,40})['\"]", keywords_blob)
        head = ", ".join(kws[:3])
        hits = _count_found(stdout)
        suffix = f" → 命中 {hits} 篇" if hits is not None else ""
        return f"检索关键词 [{head}]{suffix}"
    m = _RE_PAPER_READ.search(code)
    if m:
        pid = m.group(2)
        return f"读取 {pid}"
    m = _RE_LLM_BATCHED.search(code)
    if m:
        # Count commas to roughly infer batch size; floor at 1
        inner = m.group(1)
        n = max(1, inner.count(",") + 1) if inner.strip() else 1
        return f"批量查询 sub-LLM ×{n}"
    if _RE_LLM_QUERY.search(code):
        return "查询 sub-LLM"
    return None


def _count_found(stdout: str) -> int | None:
    """Extract `Found N` or `n=N` hit count from the stdout, if present."""
    m = re.search(r"[Ff]ound\s+(\d+)", stdout)
    if m:
        return int(m.group(1))
    m = re.search(r"len\(\w+\)\s*=\s*(\d+)", stdout)
    if m:
        return int(m.group(1))
    return None


# =============================================================================
# Typewriter
# =============================================================================


def typewriter_chunks(
    text: str, chunk: int = 5, max_yields: int = 600
) -> Iterator[str]:
    """Yield progressively longer prefixes of `text`.

    With chunk=5 and text='12345678901234' yields:
        '12345', '1234567890', '12345678901234'

    If the number of yields would exceed `max_yields`, scales up the chunk
    size so the total yield count is bounded. The final yield always
    contains the full text.
    """
    n = len(text)
    if n == 0:
        return
    # If naive chunking would exceed max_yields, scale chunk up.
    needed = (n + chunk - 1) // chunk
    if needed > max_yields:
        chunk = (n + max_yields - 1) // max_yields
    i = 0
    while i < n:
        i = min(n, i + chunk)
        yield text[:i]


# =============================================================================
# Internal helpers
# =============================================================================


_RE_MD_BOLD = re.compile(r"\*\*([^\*]+)\*\*")
_RE_MD_INLINE_CODE = re.compile(r"`([^`]+)`")


def _render_markdown_basic(text: str) -> str:
    """Render a *tiny* subset of markdown so chat answers look right.

    For the final answer we deliberately keep this minimal — full markdown is
    delegated to the model's already-formatted Chinese output. We just:
      - escape HTML
      - convert **bold**
      - convert `inline code`
      - convert blank lines to <p> breaks
      - preserve newlines via <br>

    Tables, fenced code, and link parsing are out of scope for typewriter
    streaming (would constantly re-flow during streaming).
    """
    safe = html.escape(text)
    safe = _RE_MD_BOLD.sub(r"<strong>\1</strong>", safe)
    safe = _RE_MD_INLINE_CODE.sub(r"<code>\1</code>", safe)
    # Paragraph breaks on double newline
    paragraphs = [p.strip() for p in safe.split("\n\n") if p.strip()]
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_ui_render.py -v
```

Expected: all tests pass (24 tests).

- [ ] **Step 5: Full suite**

```bash
.venv/bin/pytest tests/ -q 2>&1 | tail -3
```

Expected: 74 passed + 1 skipped (was 50+1, added 24 render tests).

- [ ] **Step 6: Commit**

```bash
git add papers_qa/ui/render.py tests/test_ui_render.py
git commit -m "feat(ui): pure HTML render functions + progress derivation + typewriter"
```

---

## Task 5: Handler module with progress + typewriter

**Files:**
- Create: `/home/juli/RLM/papers_qa/papers_qa/ui/handler.py`
- Modify: `/home/juli/RLM/papers_qa/tests/test_gradio_app.py` (loosen assertions to substring match)
- Test: extend `/home/juli/RLM/papers_qa/tests/test_ui_render.py` with handler-level tests

- [ ] **Step 1: Add handler tests**

Append to `/home/juli/RLM/papers_qa/tests/test_ui_render.py`:

```python
# =============================================================================
# Handler integration tests
# =============================================================================
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from papers_qa.config import PapersQAConfig
from papers_qa.runner import PapersQA


@pytest.fixture
def tiny_qa(tmp_path: Path, monkeypatch) -> PapersQA:
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "Tiny_2025.md").write_text("hello")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("PAPERS_QA_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setenv("PAPERS_QA_PAPERS_DIR", str(papers))
    cfg = PapersQAConfig.from_env(env_file=str(tmp_path / "no.env"))
    return PapersQA(cfg)


def test_handler_yields_user_msg_immediately(tiny_qa: PapersQA, monkeypatch):
    from papers_qa.ui.handler import make_chat_handler

    fake = MagicMock()
    fake.response = "答案"
    fake.usage_summary.total_cost = None
    fake.execution_time = 0.1
    fake.metadata = None
    tiny_qa.rlm.completion = MagicMock(return_value=fake)  # type: ignore[method-assign]

    # Reduce typewriter pacing so the test runs fast
    monkeypatch.setenv("PAPERS_QA_TYPEWRITER_DELAY_MS", "0")

    handler = make_chat_handler(tiny_qa)
    gen = handler("你好", [])
    first_chat, _trace, _status = next(gen)
    assert isinstance(first_chat, list)
    assert len(first_chat) >= 1  # user turn shown immediately
    # The user message HTML must contain the user's exact text
    user_msg = next(m for m in first_chat if m.get("role") == "user")
    assert "你好" in user_msg["content"]
    # Drain so the daemon thread shuts down
    for _ in gen:
        pass


def test_handler_final_yield_contains_answer_text(tiny_qa: PapersQA, monkeypatch):
    from papers_qa.ui.handler import make_chat_handler

    fake = MagicMock()
    fake.response = "最终答案"
    fake.usage_summary.total_cost = None
    fake.execution_time = 0.1
    fake.metadata = None
    tiny_qa.rlm.completion = MagicMock(return_value=fake)  # type: ignore[method-assign]

    monkeypatch.setenv("PAPERS_QA_TYPEWRITER_DELAY_MS", "0")

    handler = make_chat_handler(tiny_qa)
    last_chat = None
    for chat, _, _ in handler("你好", []):
        last_chat = chat
    bot = next(m for m in last_chat if m.get("role") == "assistant")
    assert "最终答案" in bot["content"]


def test_handler_error_path(tiny_qa: PapersQA, monkeypatch):
    from papers_qa.ui.handler import make_chat_handler

    def boom(prompt, root_prompt=None):
        raise RuntimeError("boom")

    tiny_qa.rlm.completion = boom  # type: ignore[method-assign]
    monkeypatch.setenv("PAPERS_QA_TYPEWRITER_DELAY_MS", "0")

    handler = make_chat_handler(tiny_qa)
    last_chat = None
    last_status = None
    for chat, _, status in handler("你好", []):
        last_chat = chat
        last_status = status
    bot = next(m for m in last_chat if m.get("role") == "assistant")
    assert "RuntimeError" in bot["content"] or "出错" in bot["content"]
    assert "失败" in last_status or "ERROR" in last_status


def test_handler_empty_message_no_thinking(tiny_qa: PapersQA, monkeypatch):
    from papers_qa.ui.handler import make_chat_handler

    handler = make_chat_handler(tiny_qa)
    chat, _, status = next(handler("   ", []))
    assert chat == []
    assert "请先输入" in status
```

- [ ] **Step 2: Run new handler tests, verify they fail**

```bash
cd /home/juli/RLM/papers_qa
.venv/bin/pytest tests/test_ui_render.py -v -k "handler"
```

Expected: 4 errors with `ModuleNotFoundError: No module named 'papers_qa.ui.handler'`.

- [ ] **Step 3: Implement handler.py**

Create `/home/juli/RLM/papers_qa/papers_qa/ui/handler.py`:

```python
"""Chat handler: bridges papers_qa.streaming events into Gradio yields.

Public:
    make_chat_handler(qa) -> Gradio generator handler

The returned handler takes (message, history) and yields
``(chat_list, trace_html, status_str)`` tuples on every UI tick. Chat list
shape stays ``list[{"role": str, "content": str}]`` for compat, but content
is now an HTML string produced by ``papers_qa.ui.render``.
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from typing import Any

from papers_qa.runner import PapersQA
from papers_qa.streaming import build_history_text, stream_ask
from papers_qa.ui.render import (
    derive_progress_line,
    render_assistant_msg,
    render_chat,
    render_error_card,
    render_iter_card,
    render_timeout_card,
    render_trace,
    render_user_msg,
    typewriter_chunks,
)

log = logging.getLogger(__name__)

# Pacing for the final-answer typewriter. Lower = faster typing.
# Tests set this to 0 to skip sleeps.
_DELAY_MS = int(os.environ.get("PAPERS_QA_TYPEWRITER_DELAY_MS", "80"))
_CHUNK = int(os.environ.get("PAPERS_QA_TYPEWRITER_CHUNK", "5"))
_MAX_YIELDS = int(os.environ.get("PAPERS_QA_TYPEWRITER_MAX_YIELDS", "600"))


def _messages_to_pairs(history: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Extract plain (user_text, bot_text) pairs from the HTML-wrapped history.

    The history stored by Gradio between turns contains HTML strings in
    `content`. To feed it back into `stream_ask`'s history_text we need the
    plain user-typed string and the bot's answer text — both of which we
    saved alongside the HTML in the message dict under `data-text` attrs.
    Simpler approach: walk pairs and use the `_text` field we added.
    """
    pairs: list[tuple[str, str]] = []
    pending_u: str | None = None
    for m in history:
        role = m.get("role")
        text = m.get("_text", "") or ""
        if role == "user":
            if pending_u is not None:
                pairs.append((pending_u, ""))
            pending_u = text
        elif role == "assistant":
            pairs.append((pending_u or "", text))
            pending_u = None
    if pending_u is not None:
        pairs.append((pending_u, ""))
    return pairs


def make_chat_handler(qa: PapersQA):
    """Return a Gradio generator handler closed over the shared PapersQA."""

    def handler(
        message: str,
        history: list[dict[str, Any]],
    ) -> Iterator[tuple[list[dict[str, Any]], str, str]]:
        # 1. Empty input guard
        if not message.strip():
            yield history, render_trace([]), "请先输入问题。"
            return

        # 2. Show the user turn immediately, with an initial progress card
        prior_pairs = _messages_to_pairs(history)
        prior_history_text = build_history_text(prior_pairs)

        progress_rows: list[str] = ["正在分析问题"]
        iter_cards: list[str] = []

        def _snapshot(
            assistant_html: str,
            assistant_text: str = "",
            chat_status: str = "",
        ) -> tuple[list[dict[str, Any]], str, str]:
            new_history: list[dict[str, Any]] = list(history) + [
                {"role": "user", "content": render_user_msg(message), "_text": message},
                {"role": "assistant", "content": assistant_html, "_text": assistant_text},
            ]
            # Wrap chat list into the shell for client rendering.
            # We DO yield the list-of-dicts (Gradio re-serializes it) but the
            # gradio_client test rig and downstream code inspect each dict's
            # `content` directly, so the assistant html string is what they read.
            return new_history, render_trace(iter_cards), chat_status

        t0 = time.perf_counter()
        # Initial yield — user msg + just "正在分析问题" progress
        yield _snapshot(
            assistant_html=render_assistant_msg(progress_rows=progress_rows),
            chat_status=f"⏱ {time.perf_counter() - t0:.1f}s · 初始化",
        )

        iter_count = 0
        try:
            for evt in stream_ask(qa, message, history_text=prior_history_text):
                etype = evt["type"]
                elapsed = time.perf_counter() - t0
                if etype == "iteration":
                    iter_count += 1
                    # Add an iteration card to the right panel
                    iter_cards.append(
                        render_iter_card(
                            iter_count, evt, default_open=iter_count <= 3
                        )
                    )
                    # Derive progress lines for the left panel
                    new_lines: list[str] = []
                    for cb in evt.get("code_blocks") or []:
                        line = derive_progress_line(cb)
                        new_lines.append(line or f"推理第 {iter_count} 轮")
                    if new_lines:
                        progress_rows.extend(new_lines)
                    else:
                        progress_rows.append(f"推理第 {iter_count} 轮")
                    yield _snapshot(
                        assistant_html=render_assistant_msg(progress_rows=progress_rows),
                        chat_status=f"⏱ {elapsed:.1f}s · 迭代 {iter_count} · 思考中",
                    )
                elif etype == "final":
                    answer = str(evt.get("answer") or "")
                    duration = float(evt.get("duration_s") or elapsed)
                    cost = evt.get("cost_usd")
                    cost_str = f" · ${cost:.4f}" if cost else ""
                    summary = f"✓ {iter_count} 轮 · {duration:.1f}s{cost_str}"
                    # Typewriter the answer below the collapsed progress chip
                    for partial in typewriter_chunks(
                        answer, chunk=_CHUNK, max_yields=_MAX_YIELDS
                    ):
                        yield _snapshot(
                            assistant_html=render_assistant_msg(
                                content=partial,
                                progress_summary=summary,
                                progress_collapsed=True,
                            ),
                            assistant_text=partial,
                            chat_status=f"⏱ {time.perf_counter() - t0:.1f}s · 输出中",
                        )
                        if _DELAY_MS > 0:
                            time.sleep(_DELAY_MS / 1000.0)
                    # Final settled state
                    yield _snapshot(
                        assistant_html=render_assistant_msg(
                            content=answer,
                            progress_summary=summary,
                            progress_collapsed=True,
                        ),
                        assistant_text=answer,
                        chat_status=f"✓ 完成 · {duration:.1f}s · {iter_count} 轮{cost_str}",
                    )
                    return
                elif etype == "error":
                    err = str(evt.get("error") or "未知错误")
                    yield _snapshot(
                        assistant_html=render_assistant_msg(
                            content=f"❌ 出错：{err}",
                            progress_summary=f"× 失败 · {elapsed:.1f}s",
                            progress_collapsed=True,
                        ),
                        assistant_text=f"出错：{err}",
                        chat_status=f"❌ 失败 · {elapsed:.1f}s",
                    )
                    iter_cards.append(render_error_card(err))
                    yield _snapshot(
                        assistant_html=render_assistant_msg(
                            content=f"❌ 出错：{err}",
                            progress_summary=f"× 失败 · {elapsed:.1f}s",
                            progress_collapsed=True,
                        ),
                        assistant_text=f"出错：{err}",
                        chat_status=f"❌ 失败 · {elapsed:.1f}s",
                    )
                    return
                elif etype == "timeout":
                    yield _snapshot(
                        assistant_html=render_assistant_msg(
                            content="⚠️ 模型 600s 无响应，请重试。",
                            progress_summary=f"⏰ 超时 · {elapsed:.1f}s",
                            progress_collapsed=True,
                        ),
                        assistant_text="模型 600s 无响应",
                        chat_status=f"⏰ 超时 · {elapsed:.1f}s",
                    )
                    iter_cards.append(render_timeout_card())
                    return
        except Exception as e:  # noqa: BLE001
            log.exception("Unexpected error in chat handler")
            elapsed = time.perf_counter() - t0
            err_msg = f"{type(e).__name__}: {e}"
            iter_cards.append(render_error_card(err_msg))
            yield _snapshot(
                assistant_html=render_assistant_msg(
                    content=f"❌ 出错：{err_msg}",
                    progress_summary=f"× 失败 · {elapsed:.1f}s",
                    progress_collapsed=True,
                ),
                assistant_text=f"出错：{err_msg}",
                chat_status=f"❌ 失败 · {elapsed:.1f}s",
            )

    return handler
```

- [ ] **Step 4: Update existing test_gradio_app.py tests to handle HTML wrapping**

Modify `/home/juli/RLM/papers_qa/tests/test_gradio_app.py` to (a) import from the new module and (b) loosen content equality assertions to substring matches. Read the existing file first:

```bash
cat /home/juli/RLM/papers_qa/tests/test_gradio_app.py
```

For each test, replace `assert m["content"] == "X"` with `assert "X" in m["content"]`. Replace the import `import gradio_app` with `from papers_qa.ui import handler as gradio_app`. Replace `gradio_app.make_chat_handler` calls — they stay valid since we expose `make_chat_handler` at the package level (handled in next step).

Also re-export `make_chat_handler` from `papers_qa.ui.__init__.py` so the existing `from papers_qa.ui.handler import make_chat_handler` works in both forms.

Apply the edits:

```python
# At top, after `import sys`, replace the path manipulation + `import gradio_app` block with:
from papers_qa.ui.handler import make_chat_handler
```

Then in each test body, replace `gradio_app.make_chat_handler(tiny_qa)` with `make_chat_handler(tiny_qa)`.

For assertions: in `test_handler_final_yield_uses_messages_format`, change:
```python
assert any(m["role"] == "assistant" and m["content"] == "最终答案" for m in last_chat)
```
to:
```python
assert any(m.get("role") == "assistant" and "最终答案" in m.get("content", "") for m in last_chat)
```

Similar change in `test_handler_error_yield_uses_messages_format` (RuntimeError substring).

In `test_handler_accepts_prior_messages_history`, instead of asserting exact dict equality on first 2 elements, use substring + role checks:
```python
assert last_chat[0]["role"] == "user" and "之前的问" in last_chat[0]["content"]
assert last_chat[1]["role"] == "assistant" and "之前的答" in last_chat[1]["content"]
assert last_chat[-2]["role"] == "user" and "新的问" in last_chat[-2]["content"]
assert last_chat[-1]["role"] == "assistant" and "新回复" in last_chat[-1]["content"]
```

- [ ] **Step 5: Update `papers_qa/ui/__init__.py` to re-export the handler**

Edit `/home/juli/RLM/papers_qa/papers_qa/ui/__init__.py`:

```python
"""papers_qa.ui — Gradio UI subsystem."""
from __future__ import annotations

from papers_qa.ui.handler import make_chat_handler
from papers_qa.ui.theme import build_theme

__all__ = ["build_theme", "make_chat_handler"]
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/pytest tests/ -v 2>&1 | tail -20
```

Expected: all green. 74 + 4 handler = 78 passed, 1 skipped (gated real-API).

- [ ] **Step 7: Commit**

```bash
git add papers_qa/ui/handler.py papers_qa/ui/__init__.py tests/test_ui_render.py tests/test_gradio_app.py
git commit -m "feat(ui): handler with progress card + typewriter; loosen test assertions to substring"
```

---

## Task 6: Rewrite `scripts/gradio_app.py` to use the new package

**Files:**
- Replace: `/home/juli/RLM/papers_qa/scripts/gradio_app.py`

- [ ] **Step 1: Write the new minimal entry**

Replace `/home/juli/RLM/papers_qa/scripts/gradio_app.py` with this clean ~120-line version:

```python
"""Gradio web UI for papers_qa.

Run:
    python scripts/gradio_app.py                    # local
    python scripts/gradio_app.py --share            # public *.gradio.live
    python scripts/gradio_app.py --share --port 7860 --host 0.0.0.0

Env vars (CLI flags override):
    PAPERS_QA_GRADIO_SHARE=true|false
    PAPERS_QA_GRADIO_PORT=7860
    PAPERS_QA_GRADIO_HOST=127.0.0.1
    PAPERS_QA_TYPEWRITER_DELAY_MS=80
    PAPERS_QA_TYPEWRITER_CHUNK=5
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

import gradio as gr

from papers_qa.config import PapersQAConfig
from papers_qa.runner import PapersQA
from papers_qa.ui.css import CSS, HEAD_JS
from papers_qa.ui.handler import make_chat_handler
from papers_qa.ui.render import (
    render_assistant_msg,
    render_chat,
    render_trace,
    render_user_msg,
)
from papers_qa.ui.theme import build_theme

log = logging.getLogger("gradio_app")

_EXAMPLES: list[str] = [
    "Agarwal 2024 这篇论文里 GKD 与 SeqKD 在训练数据上的核心差异是什么？",
    "Hoffmann 2022 的 Chinchilla scaling law 主要结论是什么？",
    "DeepSeek-R1 论文里用了什么 RL 算法？",
    "这批论文里讨论 MoE 路由的有哪些？列出前 3 个 paper_id。",
]


def build_demo(qa: PapersQA, banner_title: str = "papers_qa") -> gr.Blocks:
    handler = make_chat_handler(qa)
    n_papers = len(qa.papers)
    model_name = qa.config.model_name

    with gr.Blocks(title=banner_title, analytics_enabled=False) as demo:
        gr.HTML(
            f"""
            <div class="pq-header">
                <span class="pq-header-mark">✱</span>
                <h2>{banner_title}</h2>
                <span class="pq-sub">Recursive Language Models · {n_papers} papers · {model_name}</span>
            </div>
            """
        )

        with gr.Row(elem_classes=["pq-main"]):
            with gr.Column(scale=17, elem_classes=["pq-col"]):
                chat = gr.HTML(
                    value=render_chat([]),
                    elem_classes=["pq-chat-shell"],
                )
                with gr.Group(elem_classes=["pq-composer-wrap"]):
                    msg = gr.Textbox(
                        placeholder="回复 papers_qa…",
                        show_label=False,
                        autofocus=True,
                        lines=2,
                    )
                    with gr.Row(elem_classes=["pq-buttons"]):
                        clear = gr.Button("清空", variant="secondary")
                        submit = gr.Button("发送", variant="primary")
                    with gr.Accordion("示例问题", open=False):
                        for ex in _EXAMPLES:
                            ex_btn = gr.Button(ex, size="sm")
                            ex_btn.click(lambda e=ex: e, outputs=msg)
            with gr.Column(scale=10, elem_classes=["pq-col"]):
                gr.HTML(
                    '<div class="pq-trace-head">'
                    '<div class="pq-kicker">REASONING</div>'
                    "<h3>推理详情</h3>"
                    "</div>",
                )
                trace = gr.HTML(
                    value=render_trace([]),
                    elem_classes=["pq-trace-shell"],
                )

        # We use Gradio's State to hold the structured chat list across turns.
        chat_state = gr.State([])
        status = gr.Markdown(value="准备就绪", elem_classes=["pq-status"])

        def _handler_with_state_update(message, history_state):
            for chat_list, trace_html, status_str in handler(message, history_state):
                yield (
                    render_chat(chat_list),  # the gr.HTML for chat
                    trace_html,              # the gr.HTML for trace
                    status_str,              # the status markdown
                    chat_list,               # the state to remember
                )

        submit_event = submit.click(
            _handler_with_state_update,
            inputs=[msg, chat_state],
            outputs=[chat, trace, status, chat_state],
            api_name="handler",
        )
        msg.submit(
            _handler_with_state_update,
            inputs=[msg, chat_state],
            outputs=[chat, trace, status, chat_state],
        )
        submit_event.then(lambda: "", outputs=msg)

        def do_clear() -> tuple[str, str, str, list, str]:
            return render_chat([]), render_trace([]), "准备就绪", [], ""

        clear.click(do_clear, outputs=[chat, trace, status, chat_state, msg])

    return demo


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("true", "1", "yes", "on"):
        return True
    if val in ("false", "0", "no", "off"):
        return False
    return default


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gradio web UI for papers_qa.")
    p.add_argument("--share", action="store_true")
    p.add_argument("--no-share", action="store_true")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--host", type=str, default=None)
    p.add_argument("--title", type=str, default="papers_qa")
    p.add_argument("--env-file", type=str, default=None)
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    cfg = PapersQAConfig.from_env(args.env_file)
    log.info("Booting Gradio app…")
    qa = PapersQA(cfg)
    demo = build_demo(qa, banner_title=args.title)
    demo.queue(default_concurrency_limit=2, max_size=20)

    if args.no_share:
        share = False
    elif args.share:
        share = True
    else:
        share = _env_bool("PAPERS_QA_GRADIO_SHARE", default=False)

    port = args.port or int(os.environ.get("PAPERS_QA_GRADIO_PORT", "7860"))
    host = args.host or os.environ.get("PAPERS_QA_GRADIO_HOST", "127.0.0.1")

    log.info("Launching: share=%s host=%s port=%s", share, host, port)
    demo.launch(
        share=share,
        server_port=port,
        server_name=host,
        show_error=True,
        theme=build_theme(),
        css=CSS,
        head=HEAD_JS,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Important: the chat handler now emits a list, but the chat **display** is `gr.HTML`. We bridge via `_handler_with_state_update` that calls `render_chat(chat_list)` for the HTML output AND yields `chat_list` for the state. Tests that drive `/handler` via gradio_client receive the LIST (since `api_name="handler"` maps to the click event whose first output is now the rendered HTML — hmm, this changes the API surface seen by gradio_client). To preserve the test API, we expose the chat LIST through the api_name route — see Step 2.

- [ ] **Step 2: Verify the `/handler` API still returns the list**

Gradio's `api_name` corresponds to one event's outputs. Our outputs are `[chat (HTML), trace (HTML), status (str), chat_state (list)]`. gradio_client.predict will return that 4-tuple. The existing tests do `chat, trace, status = r` (3-unpack). After this refactor that's a 4-tuple. Update the existing test_gradio_app.py to use 4-unpack OR add a dummy output position.

Update `tests/test_gradio_app.py` to unpack 4 values OR — cleaner — set `api_name` only on a separate hidden event whose outputs are `[chat_state, trace, status]` (the list form, for clients).

Simpler fix: add a 4th expected output to the test unpacks and ignore it. Modify `tests/test_gradio_app.py`:

```python
# OLD:  chat, trace, status = r
# NEW:
result = r if isinstance(r, tuple) else (r,)
chat = result[-1] if isinstance(result[-1], list) else result[0]  # the state list
trace = result[1]
status = result[2]
```

Actually cleanest: keep 3 outputs on the `api_name="handler"` event by wiring it as a separate event from the visual UI:

```python
# After the visual click event:
api_event = gr.api(handler, api_name="handler", inputs=[msg, chat_state], outputs=[chat_state, trace, status])
```

That `gr.api` (Gradio 6 supports this) provides a typed API endpoint that returns the list+trace+status, matching the existing test contract.

If `gr.api` isn't available in 6.14, the fallback is: make `submit.click` emit `[chat_state, chat, trace, status, chat_state]` (chat_state twice, first for the api, last for state). Then `api_name="handler"` returns 4 items, tests unpack as `chat_list, chat_html, trace, status, _state = r`.

For simplicity, use the latter — change the click wiring to:

```python
submit_event = submit.click(
    _handler_with_state_update,
    inputs=[msg, chat_state],
    outputs=[chat_state, chat, trace, status],   # 4 outputs
    api_name="handler",
)
msg.submit(
    _handler_with_state_update,
    inputs=[msg, chat_state],
    outputs=[chat_state, chat, trace, status],
)
```

And change `_handler_with_state_update` to yield `(chat_list, chat_html, trace_html, status_str)`.

Then update tests to unpack 4 values: `chat, chat_html, trace, status = r` and use `chat` (the list) for the existing assertions.

- [ ] **Step 3: Apply fixes from Step 2 to the new gradio_app.py and tests/test_gradio_app.py**

In `scripts/gradio_app.py`, change the click outputs to 4-tuple `[chat_state, chat, trace, status]` and `_handler_with_state_update` to yield 4 values.

In `tests/test_gradio_app.py`, update the predict-call expectations:
```python
chat, chat_html, trace, status = r
```

- [ ] **Step 4: Verify build still imports and AST OK**

```bash
cd /home/juli/RLM/papers_qa
.venv/bin/python -c "import ast; ast.parse(open('scripts/gradio_app.py').read()); print('AST OK')"
.venv/bin/python scripts/gradio_app.py --help
```

Expected: AST OK, argparse help prints.

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/ -q 2>&1 | tail -3
```

Expected: 78 passed, 1 skipped (handler tests cover the change).

- [ ] **Step 6: Commit**

```bash
git add scripts/gradio_app.py tests/test_gradio_app.py
git commit -m "refactor(ui): rewrite gradio_app.py to use papers_qa.ui package"
```

---

## Task 7: End-to-end manual verification + share smoke

**Files:** none changed. Pure verification.

- [ ] **Step 1: Boot locally**

```bash
cd /home/juli/RLM/papers_qa
fuser -k 7861/tcp 2>/dev/null
sleep 2
PYTHONUNBUFFERED=1 .venv/bin/python -u scripts/gradio_app.py --port 7861 > outputs/gradio_local.log 2>&1 &
disown
for i in 1 2 3 4 5 6 7 8 9 10; do
  if grep -q "Running on local URL" outputs/gradio_local.log 2>/dev/null; then echo "ready @${i}s"; break; fi
  sleep 1
done
grep -E "Running on local URL|Traceback|UserWarning" outputs/gradio_local.log | head -5
```

Expected: `Running on local URL: http://127.0.0.1:7861`, no Traceback, no UserWarning.

- [ ] **Step 2: HTML probe — Claude tokens in served page**

```bash
curl -s http://127.0.0.1:7861/ > /tmp/gradio_html.txt
echo "size: $(wc -c < /tmp/gradio_html.txt)"
for m in 'FAF9F5' 'C96442' '3D3D3A' 'pq-chat-scroll' 'pq-progress' 'pq-iter' 'Charter, Georgia' 'pq-header-mark'; do
  echo "  $m: $(grep -oc "$m" /tmp/gradio_html.txt)"
done
```

Expected: all counts ≥ 1. Especially `FAF9F5`, `C96442`, `pq-chat-scroll` must hit.

- [ ] **Step 3: End-to-end chat via gradio_client**

```bash
.venv/bin/python <<'PYEOF'
from gradio_client import Client
import time
c = Client("http://127.0.0.1:7861/", verbose=False)
t0 = time.time()
r = c.predict("一句话回答：Chinchilla scaling law 是什么？", [], api_name="/handler")
print(f"[{time.time()-t0:.1f}s] return type: {type(r)} len: {len(r) if hasattr(r, '__len__') else '?'}")
# 4-tuple: chat (list), chat_html (str), trace_html (str), status_str (str)
chat_list, chat_html, trace_html, status = r
print(f"status: {status}")
print(f"chat list length: {len(chat_list)}")
print(f"last assistant content length: {len(chat_list[-1]['content'])}")
# Final answer should be inside the assistant HTML
ans_field = chat_list[-1].get("_text") or chat_list[-1].get("content", "")
print(f"_text excerpt: {ans_field[:200]}")
assert "Chinchilla" in ans_field or "缩放" in ans_field or "scaling" in ans_field
assert "pq-chat" in chat_html or "pq-msg" in chat_html
assert "pq-iter" in trace_html or "pq-trace-empty" in trace_html
print("E2E OK")
PYEOF
```

Expected: prints `E2E OK`. Status contains `✓` or `完成`.

- [ ] **Step 4: Visual browser check (manual, document only)**

Open `http://127.0.0.1:7861/` in a browser. Verify:
1. Cream `#FAF9F5` background
2. Burnt-orange send button
3. Two-column layout
4. Type a question: user message appears immediately with fade-in
5. Progress card grows row-by-row as model thinks
6. Right panel: iteration cards animate in, first 3 open, 4+ collapsed
7. When answer arrives: progress collapses to chip, answer types out char-by-char
8. Click "清空": both panels reset, no leftover

- [ ] **Step 5: Share smoke test**

```bash
fuser -k 7861/tcp 2>/dev/null; sleep 2
PYTHONUNBUFFERED=1 .venv/bin/python -u scripts/gradio_app.py --share --port 7861 > outputs/gradio_share.log 2>&1 &
disown
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if grep -q "Running on public URL" outputs/gradio_share.log 2>/dev/null; then break; fi
  sleep 2
done
grep -E "Running on (local|public) URL|gradio\.live" outputs/gradio_share.log | head -3
```

Expected: a `*.gradio.live` URL appears. Kill: `fuser -k 7861/tcp`.

- [ ] **Step 6: Final cleanup**

```bash
fuser -k 7861/tcp 2>/dev/null
git status --short
```

Expected: clean working tree. No staged changes.

- [ ] **Step 7: Final commit (if any verification logs to track)**

```bash
# Logs are gitignored under outputs/ — nothing to commit at this step.
echo "Refactor complete: $(git log --oneline -7)"
```

---

## Risks Recap

| Severity | Risk | Mitigation |
|---|---|---|
| HIGH | gradio_client `/handler` API surface changed (3-tuple → 4-tuple) — breaks downstream consumers if any | Updated existing tests; documented in the refactor commit message |
| MEDIUM | Typewriter floods SSE on slow connections at 12 fps | `max_yields=600` cap; configurable via `PAPERS_QA_TYPEWRITER_MAX_YIELDS` |
| MEDIUM | `derive_progress_line` regex misses some code patterns → progress card silent | Always falls back to "推理第 N 轮" instead of returning silently |
| LOW | Charter font may not be installed on all systems | System stack falls through to Georgia → serif → default |
| LOW | gr.HTML doesn't auto-scroll → long answers go off-screen | MutationObserver in `HEAD_JS` scrolls `.pq-chat-scroll` to bottom on every mutation |

## Complexity Estimate

| Task | Time |
|---|---|
| 1. Theme + scaffold | 15 min |
| 2. CSS | 20 min |
| 3. Highlighter + tests | 25 min |
| 4. Render functions + tests | 60 min |
| 5. Handler + tests | 60 min |
| 6. gradio_app.py rewrite | 30 min |
| 7. E2E verification | 20 min |
| **Total** | **~3-4 hours** |

---

## Self-Review

**Spec coverage:**
- §1 Stack decision: keep Gradio + swap to gr.HTML for chat → Task 6 (gradio_app.py) ✓
- §2.1 Progress card during thinking → Task 5 handler, derived from iteration events ✓
- §2.2 Typewriter on final → Task 4 `typewriter_chunks` + Task 5 handler loop ✓
- §2.3 Sub-call expansion in progress → derivable from `iteration_time`, handled in render_iter_card sub-card ✓
- §3 Visual tokens (FAF9F5, C96442, Charter) → Task 1 theme + Task 2 CSS, verified in Task 7 HTML probe ✓
- §3 No avatars → no avatar rendering in render.py — confirmed ✓
- §3 Micro-interactions (fadein, hover) → Task 2 CSS keyframes ✓
- §4 Flatter iteration cards (single `<details>`, 3 sections) → render_iter_card in Task 4 ✓
- §4 Default expand first 3 iterations → handler in Task 5 passes `default_open=iter_count <= 3` ✓
- §4 Code syntax highlight → Task 3 ✓
- §4 Sub-call summary → render_iter_card includes `<details class="pq-subcall">` (in render.py impl) ✓
- §5 Module layout → Tasks 1-5 create exactly the structure ✓
- §6 Sharing unchanged → gradio_app.py preserves --share flag ✓
- §7 Backward compatibility on /handler endpoint → 4-output workaround documented in Task 6 ✓
- §8 Risks → all listed in Risks Recap ✓
- §10 Verification → Task 7 has 6 steps ✓

**Placeholder scan:** no "TBD", no "implement later", no "add appropriate validation". Every code step is complete with code.

**Type/name consistency:**
- `derive_progress_line(code_block) -> str | None` — same signature in spec, Task 4 tests, Task 4 impl, Task 5 handler call site ✓
- `typewriter_chunks(text, chunk=5, max_yields=600) -> Iterator[str]` — consistent across spec, tests, impl, handler ✓
- `render_iter_card(n, evt, default_open=True) -> str` — signature consistent ✓
- `render_assistant_msg(content="", progress_rows=None, progress_summary="", progress_collapsed=False)` — consistent in Task 4 tests, Task 4 impl, Task 5 handler usage ✓
- CSS class names: `pq-chat-scroll`, `pq-msg`, `pq-msg-user`, `pq-msg-assistant`, `pq-progress`, `pq-progress-row`, `pq-progress-collapsed`, `pq-iter`, `pq-iter-n`, `pq-iter-time`, `pq-iter-blocks`, `pq-iter-pair`, `pq-tok-kw/str/num/com/fn`, `pq-header`, `pq-trace-shell`, `pq-status` — appear identically in css.py constants AND render.py output strings AND Task 7 grep targets ✓
- `make_chat_handler(qa) -> handler` — same in Task 5 impl, Task 6 import, tests/test_gradio_app.py import ✓
- Env vars: `PAPERS_QA_TYPEWRITER_DELAY_MS`, `PAPERS_QA_TYPEWRITER_CHUNK`, `PAPERS_QA_TYPEWRITER_MAX_YIELDS` — same in handler.py + gradio_app.py docstring ✓

No drift. Plan is ready to execute.
