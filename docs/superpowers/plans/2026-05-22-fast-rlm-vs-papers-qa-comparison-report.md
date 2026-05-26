# fast-rlm vs papers_qa Comparison Report — Plan

> **For agentic workers / future-me:** This plan describes a research-writing task, not a code-implementation task. Tasks are research/drafting steps rather than TDD cycles. The deliverable is a single Markdown report.

**Goal:** Produce a side-by-side comparison report of the RLM implementations / usage in `/home/juli/RLM/fast-rlm` and `/home/juli/RLM/papers_qa`, covering architecture, algorithm, features, design trade-offs, and a pros/cons summary.

**Deliverable:** `docs/superpowers/specs/2026-05-22-fast-rlm-vs-papers-qa-comparison.md` (a single self-contained Markdown report, ~600–900 lines, in Chinese to match the user's question language).

---

## Critical scope finding — must confirm before writing

`papers_qa` is **not its own RLM core**. Its `pyproject.toml` declares `rlms = { path = "../rlm", editable = true }`, and `runner.py` imports `from rlm import RLM` / `from rlm.logger import RLMLogger`. The actual RLM engine that powers papers_qa lives in `/home/juli/RLM/rlm/` (a separate Python RLM library with `clients/`, `core/`, `environments/`, `logger/`).

So a literal "compare fast-rlm and papers_qa" gives an apples-to-oranges comparison:

| Side | What's in the directory |
|---|---|
| `fast-rlm` | A **standalone RLM library** (TS engine + Python wrapper) |
| `papers_qa` | A **domain application** (loader + search tool + bilingual prompt + Gradio UI) that *consumes* the separate `rlm` library |

I'll handle this by **proposing three scope options** in the plan and asking the user to pick before drafting. My recommendation is **Option B**.

### Scope options

- **Option A — Strict scope:** Compare only what is inside the two directories. papers_qa shows up as an application layer with no RLM core of its own; the report explicitly says "papers_qa does not implement RLM — its RLM behavior comes from the `rlms` dependency." Trade-off: the comparison is structurally lopsided.
- **Option B (recommended) — Effective scope:** Compare `fast-rlm` against `papers_qa + its rlms dependency` (the package at `/home/juli/RLM/rlm/`). Two RLM cores actually get compared. The papers_qa-specific customizations (search tool, bilingual prompt, OpenAI monkey-patch, Gradio streaming) become a separate "application layer on top of rlms" section.
- **Option C — Three-way:** Treat `fast-rlm`, `rlms` (the library), and `papers_qa` (the app) as three peers and compare each pair. Most thorough; longer report.

---

## What's already been read (do not re-read)

### fast-rlm
- `README.md` — full overview, RLM definition, install, structured I/O, tools, env vars, config, log viewer
- `pyproject.toml`, `deno.json`, `rlm_config.yaml` — packaging + runtime config
- `fast_rlm/__init__.py`, `fast_rlm/_runner.py` (286 lines) — Python CLI wrapper that builds Deno subprocess command
- `fast_rlm/_cli.py` (95 lines) — `fast-rlm-log` log viewer CLI
- `fast_rlm.py` (top-level legacy stub, 27 lines)
- `src/subagents.ts` (672 lines) — **the core RLM loop**: Pyodide setup, REPL initialization, llm_query, FINAL handling, schema validation
- `src/prompt.ts` (322 lines) — full `SYSTEM_PROMPT` + `LEAF_AGENT_SYSTEM_PROMPT`
- `src/call_llm.ts` (110 lines) — OpenAI client wrapper, ```repl``` code-block extraction
- `src/logging.ts` (162 lines) — Pino-based JSONL logger
- Listed (not read): `src/ui.ts`, `src/usage.ts`, `src/view_logs.ts`, `benchmarks/*`, `examples/*`

### papers_qa
- `README.md` (English), `中文文档.md` listed but not read
- `pyproject.toml` — confirms dependency on `rlms` from `../rlm`
- `papers_qa/__init__.py`, `papers_qa/runner.py` (95 lines) — driver wrapping `RLM(backend, environment, max_iterations, ..., custom_system_prompt, custom_tools, logger).completion(...)`
- `papers_qa/config.py` (65 lines) — `PapersQAConfig` (frozen dataclass, `from_env`)
- `papers_qa/prompts.py` (125 lines) — `build_bilingual_system_prompt`: extends `RLM_SYSTEM_PROMPT` with a Chinese/English bilingual addendum (keyword translation, dedup, no-hallucination, citation rules)
- `papers_qa/search.py` (89 lines) — `search_papers` substring keyword search tool, registered via `custom_tools`
- `papers_qa/loader.py` (34 lines) — directory of `.md` → `dict[paper_id, str]`
- `papers_qa/streaming.py` (197 lines) — `_QueueLogger` subclass + `stream_ask` generator for Gradio
- `papers_qa/openai_patch.py` (112 lines) — monkey-patches `rlm.clients.openai.OpenAIClient.completion` to force temperature + DeepSeek `thinking=disabled`
- Listed (not read): `papers_qa/ui/*`, `tests/*`, `scripts/*`

### Verified context
- `/home/juli/RLM/rlm/` exists with `rlm/{clients,core,environments,logger,utils}` — it is the upstream library papers_qa depends on. **Not yet read.** Required if user chooses Option B or C.

---

## Tasks

### Task 1: Confirm scope with user

- [ ] **Step 1: Ask the user which scope (A/B/C) to use.**
  Present the trade-off; recommend Option B.
  Do not proceed to Task 2 until answered.

### Task 2 (conditional on B or C): Read the `rlms` library

Files to read in order of importance:
- `rlm/__init__.py` — public API surface
- `rlm/core/types.py` — `RLMIteration`, completion result types (already referenced in streaming.py)
- `rlm/core/*.py` — main RLM loop / executor
- `rlm/environments/*.py` — REPL backends (local? sandboxed?)
- `rlm/clients/openai.py` — base class that papers_qa monkey-patches
- `rlm/logger/*.py` — logging interface
- `rlm/utils/prompts.py` — `RLM_SYSTEM_PROMPT` (the base papers_qa extends)
- `README.md`, `AGENTS.md`

- [ ] **Step 1:** Inventory files (`ls rlm/rlm/**/*.py`).
- [ ] **Step 2:** Read core types and public API.
- [ ] **Step 3:** Read the main RLM loop and environment(s) — how the Python REPL is hosted (subprocess? in-process exec? Pyodide?), how iterations work, how `custom_tools` are injected, how `llm_query` is exposed, how `FINAL` is captured.
- [ ] **Step 4:** Read the OpenAI client (the patch target).
- [ ] **Step 5:** Read the logger interface (the streaming layer's parent class).
- [ ] **Step 6:** Note: distribution model, dependencies, safety controls (depth, budget), schema support.

### Task 3 (optional): Spot-check secondary files

Only if a comparison axis remains unclear after Task 2:
- fast-rlm: `src/ui.ts`, `src/usage.ts`, `examples/parallel_r_count.py`, `examples/structured_io.py`, `examples/tools_market_scanner.py` (to confirm how tools/schemas are used in practice)
- papers_qa: `papers_qa/ui/handler.py`, `papers_qa/ui/render.py`, `scripts/ask.py`, `scripts/ask_batch.py`, `scripts/gradio_app.py`, `中文文档.md`

### Task 4: Draft the report at the target path

**Target file:** `docs/superpowers/specs/2026-05-22-fast-rlm-vs-papers-qa-comparison.md`

**Language:** Chinese (matches user's question language and the user's other written docs in the repo).

**Length target:** ~600–900 lines including code excerpts and tables. Concise where possible; do not pad.

**Report outline:**

```
# fast-rlm 与 papers_qa 的 RLM 实现对比报告

## 0. 摘要 (Executive Summary)
   - 一段话：两者本质 / 共同祖先（RLM 论文 arxiv 2512.24601）/ 一句话结论

## 1. 项目定位 (Project Positioning)
   1.1 fast-rlm：单仓库 RLM 库（PyPI 包）
   1.2 papers_qa：基于 rlms 库的领域应用
   1.3 与上游 RLM 论文的关系
   表格：包名 / 版本 / License / 入口 API / 主依赖

## 2. 运行架构 (Runtime Architecture)
   2.1 fast-rlm：Python 薄壳 → Deno 子进程 → Pyodide WASM REPL
       - 为什么这样切分（沙箱、独立 Python 环境、与宿主隔离）
       - 启动开销 / 跨语言数据传递（JSON / stdin / 临时文件）
   2.2 papers_qa：纯 Python，依赖 rlms 库提供的 REPL 环境
       - rlms 的 REPL backend（待 Task 2 确认：本机 exec？子进程？）
   架构图（ASCII）

## 3. RLM 核心循环 (Core RLM Loop)
   3.1 迭代结构对比
       - fast-rlm: `for i in 0..MAX_CALLS`，单一函数 `subagent()` 递归
       - papers_qa via rlms: `rlm.completion(prompt, root_prompt)` → 待 Task 2 揭示内部循环
   3.2 输入 / 输出契约
       - fast-rlm: `query: str | dict` + `output_schema` (Pydantic/JSON Schema 双口) → `dict{results, usage, log_file}`
       - papers_qa: `prompt: dict[paper_id, str]` + `root_prompt: str` → `Completion{response, execution_time, usage_summary, metadata}`
   3.3 "FINAL" 语义
       - fast-rlm: REPL 内 `FINAL(value)` + JSON Schema 校验失败可重试
       - papers_qa via rlms: 待确认
   3.4 子代理递归
       - fast-rlm: `await llm_query(context, schema, tools=[...])` → 真正派生新 subagent，深度 +1；非根用 SUB_AGENT 模型，叶节点用专门的 LEAF prompt
       - papers_qa via rlms: 待 Task 2 确认
   代码片段并排展示主循环（fast-rlm subagents.ts:432-553 vs rlms 核心 loop）

## 4. 提示词工程 (Prompt Engineering)
   4.1 fast-rlm 的两套 system prompt
       - SYSTEM_PROMPT（~200 行）：完整 REPL 玩法、并行 asyncio.gather 示范、tools 传递规则、chunking 范例
       - LEAF_AGENT_SYSTEM_PROMPT：剥离 llm_query 段，给最深层节点
   4.2 papers_qa 的 prompt 构造
       - 复用 rlms 的 `RLM_SYSTEM_PROMPT` 作为基底
       - 用 `BILINGUAL_ADDENDUM` 追加：5–15 个英文关键词扩展、近重复论文去重、强制中文回答、严禁猜数字、必须引用 paper_id
       - 双 `{...}` 转义技巧（因为 rlms 后续会跑一次 `.format(custom_tools_section=...)`）
   并排：fast-rlm SYSTEM_PROMPT 节选 vs BILINGUAL_ADDENDUM 节选

## 5. 工具系统 (Tools)
   5.1 fast-rlm
       - 任意 Python 函数 → `inspect.getsource` → JSON 文件 → Deno 读 → Pyodide `__register_tool__`
       - 子代理默认 **不继承** 父代理工具；必须 `llm_query(..., tools=[...])` 显式下传
       - 工具必须 self-contained（imports 写在函数体里）
       - 自定义工具 vs 内置 `llm_query`
   5.2 papers_qa
       - `custom_tools={"search_papers": {"tool": fn, "description": ...}}` 传给 RLM 构造函数
       - `search_papers(keywords, top_k, snippet_chars, paper_ids)` 是闭包，捕获 `papers` 字典
       - 是否子代理继承 / 是否要求 self-contained：待 Task 2 确认
   5.3 工具描述呈现给 LLM 的方式

## 6. 数据与安全控制 (Data Plane & Safety)
   6.1 上下文注入
       - fast-rlm: 字符串 → 嵌入 Python 字面量；dict/list → `json.loads(...)` 得真正的 Python dict（不是 JsProxy）
       - papers_qa: 直接 `prompt=papers_dict`，由 rlms 注入为 `context`
   6.2 输出截断
       - fast-rlm: `truncate_len`，REPL stdout 末尾保留 N 字符；过半预算后追加预算横幅
       - papers_qa via rlms: 待 Task 2 确认
   6.3 预算 / 超时
       - fast-rlm: `max_money_spent` $, `max_completion_tokens`, `max_prompt_tokens`，违反即抛错
       - papers_qa: `max_budget_usd`, `max_timeout_s`, `max_iterations`, `max_depth`
   6.4 输出 schema 校验
       - fast-rlm: Ajv `strict:false, allErrors:true`，失败将错误 path/message 反馈给 agent
       - papers_qa via rlms: 是否支持 schema？（runner.py 未传 schema → 待 Task 2 确认）
   6.5 env_variables 通道
       - fast-rlm: dict[str,str] 注入到 Pyodide os.environ，不污染 Deno 宿主，不入提示词
       - papers_qa: 直接读宿主 os.environ（OPENAI_API_KEY、PAPERS_QA_PAPERS_DIR 等）
   6.6 沙箱安全模型
       - fast-rlm: WebAssembly + Deno 显式 `--allow-*` 权限；网络通过 micropip-pyodide-http
       - papers_qa: 跑在宿主 Python，访问真实文件系统；Gradio `--share` 暴露 PAPERS_QA_PAPERS_DIR

## 7. 可观测性 (Observability)
   7.1 fast-rlm
       - Pino → JSONL，事件 `agent_start/code_generated/execution_result/final_result/agent_end`，含 run_id/parent_run_id/depth/usage/timestamps
       - 终端 spinner + 用量摘要
       - `fast-rlm-log` 统计 + 可选 Bun TUI viewer
   7.2 papers_qa
       - rlms RLMLogger（待 Task 2 揭示原生格式）
       - papers_qa 在其上加 `_QueueLogger` 子类，把 `RLMIteration` 推到 `queue.Queue` 喂 Gradio
       - Gradio UI 渲染：响应、每个 ```repl``` 块、stdout/stderr、sub-LLM 调用
   7.3 实时流式 vs 离线日志
       - fast-rlm 是离线日志（subprocess 跑完 → 写 JSON 输出文件）
       - papers_qa 用线程 + 队列做到实时

## 8. 多语言 / 领域定制 (Bilingual & Domain Tailoring)
   8.1 fast-rlm: 通用 RLM，无特定语言假设；examples/ 多为英文 demo
   8.2 papers_qa: 中文问题 / 英文论文这一明确双语场景
       - 关键词翻译
       - 近重复 paper_id 去重（如 Qwen3 Technical Report 等）
       - 引用 paper_id（"据 X 所述"）
       - 表格 / 数字必须从 llm_query 实证，不得编造（含拒绝示例）
       - OpenAI 客户端 monkey-patch：temperature=0.2 防死锁；DeepSeek `thinking=disabled` 提速

## 9. 分发 / 依赖 / 集成 (Distribution & Integration)
   - 包：PyPI `fast-rlm` 0.1.14 vs 本地可编辑 `papers-qa`
   - 运行依赖：fast-rlm 强依赖 Deno 2+ (可选 Bun)；papers_qa 纯 Python 3.11+
   - 安装体积、首启冷启动（fast-rlm 要等 Pyodide loadPackage("micropip") + 安装 requests/httpx）
   - 测试：fast-rlm 无明显 pytest；papers_qa 有 11 个 test 文件

## 10. 优劣分析 (Pros & Cons)
   10.1 fast-rlm 的优势
       - 严格沙箱（Pyodide）保护宿主
       - 完整的 schema/Pydantic 一等支持
       - 工具继承规则严格、显式 → 子代理上下文洁净
       - 论文级 RLM 语义还原度高
       - 内置预算多维度硬截断
   10.2 fast-rlm 的代价
       - 必须装 Deno；冷启动慢；跨语言调试痛苦
       - WASM Python 缺包（需要 micropip 现装）
       - 工具源码必须可被 `inspect.getsource` 取到，闭包变量不能跨进程
       - 子代理工具必须显式 forward —— 写应用代码会绕
   10.3 papers_qa（+rlms）的优势
       - 纯 Python，启动快、易调试、易部署
       - 工具可以闭包共享应用状态（如 papers dict）
       - 直接 Gradio 流式 UI / 实时观测
       - 双语 + 领域适配（数值不许编造、必须引文）实战经验沉淀在 system prompt
       - OpenAI 客户端可被 monkey-patch（自定义 temperature / extra_body）
   10.4 papers_qa（+rlms）的代价
       - REPL 跑在宿主 Python，沙箱弱
       - schema/Pydantic 支持程度待 rlms 库验证（fast-rlm 已完备）
       - rlms 的 RLM 实现细节待审；可能在并行 subagent、深度递归、leaf 提示等方面不如 fast-rlm 成熟
       - 全局 monkey-patch + 模块级队列锁 + 后台线程，让并发模型复杂

## 11. 何时用哪个 (Decision Guide)
   - 想要拿来即用做"长文档问答 / 在线对话 / 流式 UI"→ papers_qa（或基于 rlms 自己写应用层）
   - 想要论文还原度高、严格 schema、跨进程沙箱、纯库形态嵌入到别的 Python 项目里 → fast-rlm
   - 中文双语场景 → papers_qa 的 prompt 是现成参考
   - 需要把工具源码塞给子代理跨递归层使用 → fast-rlm 的 `tools=[...]` 显式 forward 协议更安全
   - 需要在 GPU/无沙箱环境跑 RLM 调用本地模型 → rlms（papers_qa 路径）更直接

## 12. 关键代码引用索引
   - 主循环：`fast-rlm/src/subagents.ts:432-557`
   - 子代理派生：`fast-rlm/src/subagents.ts:172-219`
   - schema 校验反馈：`fast-rlm/src/subagents.ts:501-528`
   - leaf 提示词切换：`fast-rlm/src/subagents.ts:137`，`src/call_llm.ts:59`
   - 双语 addendum：`papers_qa/papers_qa/prompts.py:6-105`
   - 工具注册（papers_qa）：`papers_qa/papers_qa/search.py:23-78`，`runner.py:47-72`
   - OpenAI monkey-patch：`papers_qa/papers_qa/openai_patch.py:33-107`
   - 流式 logger 子类：`papers_qa/papers_qa/streaming.py:46-58`
   - Deno subprocess 桥：`fast-rlm/fast_rlm/_runner.py:136-281`

## 13. 待办 / 限制
   - 本报告基于读到的源码静态分析，未实际跑 benchmark
   - rlms 内部细节由 Task 2 决定深度；若用户选 Option A 则相关章节降级为"未在本仓库内"
```

### Task 5: Self-review pass

- [ ] **Step 1:** 通读，删冗余、合并重复、检查代码行号引用是否准确（重新打开源文件确认）
- [ ] **Step 2:** 删除任何"based on understanding"式的判断词；只陈述读到的事实，加注 "待 rlms 验证" 的地方明确标注
- [ ] **Step 3:** 检查所有表格栏数对齐、所有代码块语言标识正确
- [ ] **Step 4:** 字数与节奏：每章 1–3 屏，必要时拆子标题
- [ ] **Step 5:** 报告末尾附"参考文件清单"，让读者可顺源查证

### Task 6: Deliver

- [ ] **Step 1:** 报告文件落地：`docs/superpowers/specs/2026-05-22-fast-rlm-vs-papers-qa-comparison.md`
- [ ] **Step 2:** 在本会话中给出报告路径 + 一句话摘要

---

## 风险与注意事项

1. **Scope ambiguity** — 已通过 Task 1 强制让用户选；不主动假设 Option B。
2. **未读 rlms 库** — 若选 A 则跳过；若选 B/C 则 Task 2 必须完成，否则报告里大量"待 Task 2 确认"会变成空洞描述。
3. **中文行文** — 用户提问全程中文 + 仓库内 `中文文档.md` 表明中文为优先输出语言。
4. **不假装 benchmark** — 没跑过性能测试就不写性能数字；任何"快/慢"的判断都用结构性理由（冷启动、跨进程开销、并行能力）支撑。
5. **代码引用必须真实** — 行号在最后 self-review 时重新核对，prompt.ts、subagents.ts 行号上限分别为 322 / 672。
6. **不要把 fast-rlm 美化** — 它有真实缺点：Pyodide 包生态有限、Deno 强依赖、工具源码反射约束、冷启动；要写出来。
7. **不要把 papers_qa 矮化** — 它的 prompt 工程、流式 UI、monkey-patch 是真实工程价值；要列在优势里。
