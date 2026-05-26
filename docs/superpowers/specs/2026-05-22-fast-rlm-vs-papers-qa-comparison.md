# `fast-rlm` 与 `papers_qa`（+`rlms`）RLM 实现对比报告

> 撰写日期：2026-05-22
> 范围：`/home/juli/RLM/fast-rlm`（独立 RLM 库）vs `/home/juli/RLM/papers_qa`（领域应用）+ 其依赖的 `/home/juli/RLM/rlm` 库（rlms，发布名 `rlms`）
> 方法：静态源码阅读，未实跑性能基准

---

## 0. 摘要

`fast-rlm` 与 `papers_qa` 都是对 Recursive Language Models（RLM, arXiv:2512.24601）的工程化实现，但二者在体系上属于不同的"截面"：

- **`fast-rlm`** 是一个 **自洽的 RLM 库**：核心循环用 TypeScript 写在 Deno + Pyodide 上，Python 侧只是子进程薄壳；提供 `fast_rlm.run(query, output_schema=..., tools=..., env_variables=...)` 一个函数。
- **`papers_qa`** 不实现 RLM 内核，而是 **构建在 `rlms`（一个独立的、纯 Python 的 RLM 库）之上的中英双语论文问答应用**：它提供论文加载器、关键词搜索工具、双语 system prompt 增强、OpenAI 客户端 monkey-patch、Gradio 流式 UI 等。

因此，本报告**有效比较两个 RLM 内核**——`fast-rlm` 的 TS+Pyodide 引擎，与 `rlms` 的纯 Python 引擎——并把 `papers_qa` 单列为"应用层 best practice"。一句话结论：

> `fast-rlm` 用更严格的沙箱、更完整的 schema/Pydantic 一等公民、显式的工具下传契约，做出了高保真的论文复现；`rlms`（+`papers_qa`）用更轻的依赖、更丰富的 backend/environment 矩阵、双查询模式（`llm_query` 单发 / `rlm_query` 递归）、内置 compaction、可插拔的客户端与回调，把易用性和工程整合性做到了极致。两者不是替代关系，而是各自代表 "学术原型对齐" 与 "生产侧可塑性" 两种取向。

---

## 1. 项目定位

| 维度 | `fast-rlm` | `rlms`（papers_qa 的依赖） | `papers_qa` |
|---|---|---|---|
| 角色 | RLM 标准库 | RLM 标准库 | 领域应用 |
| 发布形式 | PyPI `fast-rlm==0.1.14` | 本地 editable，包名 `rlms` | 本地 editable，包名 `papers-qa` |
| License | MIT | MIT | 未声明 |
| 上游论文 | arXiv:2512.24601（pyproject 中显式声明） | 未在 README 声明 | 不适用 |
| 入口 API | `fast_rlm.run(query, ...) -> dict` | `RLM(...).completion(prompt, root_prompt) -> RLMChatCompletion` | `PapersQA(config).ask(question)` |
| 主依赖 | `pyyaml`；外部要求 Deno 2+ | `openai`, `anthropic`, `google-genai`, ... + 多个可选环境 SDK | `rlms`, `python-dotenv`, `gradio`(可选) |
| 代码量 | TS 约 1.5 K 行 + Python 384 行 | Python 约 8.9 K 行 | Python 约 1.9 K 行 |
| 测试 | 无 pytest 套件，靠 `examples/`+`benchmarks/` | 多个测试（在 `rlm/tests/` 下） | 11 个 pytest 文件 |
| UI | 终端 spinner + 可选 Bun TUI | rich verbose printer | Gradio Web UI |

---

## 2. 运行架构

### 2.1 `fast-rlm`：Python 薄壳 → Deno 子进程 → Pyodide WASM REPL

```
+----------------------+   subprocess.run(["deno", ..., "src/subagents.ts"])
|  Python: fast_rlm    | ----------------+
|  - inspect 工具源码  |                  |
|  - 序列化 query/tools|                  v
|  - 临时文件传递      |   +----------------------------+
+----------------------+   |  Deno (TypeScript)          |
                           |  - subagents.ts: 主循环      |
                           |  - call_llm.ts: OpenAI 客户端|
                           |  - logging.ts: Pino JSONL    |
                           |  - prompt.ts: 系统提示词     |
                           |    +----------------------+ |
                           |    |  Pyodide WASM        | |
                           |    |  Python REPL          | |
                           |    |   - context           | |
                           |    |   - FINAL()           | |
                           |    |   - llm_query()       | |
                           |    |   - 用户工具函数      | |
                           |    +----------------------+ |
                           +----------------------------+
```

- Python 侧（`fast_rlm/_runner.py:136-281`）只负责构造子进程命令、序列化输入到临时 JSON 文件、收回结果；不参与任何 RLM 循环。
- 实际循环在 `src/subagents.ts:125-557` 的 `async function subagent()`，每次递归子代理就**重新加载 Pyodide**并初始化新的 REPL（每个子代理一个全新的 Python 命名空间）。
- 网络访问：Pyodide 默认没有 `requests`/`httpx`，启动后用 `micropip.install` 在 WASM 内安装，再用 `pyodide_http.patch_all()` 路由到宿主 fetch（`src/subagents.ts:155-161`）。这意味着**每个子代理都要付出 micropip 安装的冷启动代价**（启动后会打印 `env setup took {ms}ms`）。

设计意图很明确：**通过 WASM + Deno 权限白名单（`--allow-read --allow-net --allow-env --allow-sys=hostname,osRelease --allow-write`）把 LLM 生成的 Python 代码与宿主彻底隔离**。

### 2.2 `rlms`：纯 Python，多 environment 后端

```
+----------------------------------------------------+
|  papers_qa.PapersQA                                |
|  - load_papers() -> dict[str, str]                 |
|  - build_search_tool() -> custom_tools             |
|  - build_bilingual_system_prompt(num_papers)       |
|  - apply_temperature_patch() ← monkey-patch        |
|  - RLM(...)  ← 来自 rlms                            |
+-------------------------|--------------------------+
                          |
                          v
+----------------------------------------------------+
|  rlm.RLM.completion(prompt, root_prompt)           |
|   for i in range(max_iterations):                  |
|       prompt → LMHandler.completion()              |
|       response → find_code_blocks(```repl ... ```) |
|       for each code: environment.execute_code()    |
|       检查 final_answer / 预算 / 超时 / 错误         |
+-------------------------|--------------------------+
                          | (socket bridge)
       +------------------+------------------+
       |                                     |
       v                                     v
+----------------+              +----------------------------+
| LMHandler      |              | get_environment("local") = |
| - host:port    | <----------- |   LocalREPL                |
| - OpenAIClient |  socket call |  - exec(code, globals,     |
|   /Anthropic/  |              |    locals) IN-PROCESS      |
|   /Gemini/...  |              |  - llm_query / rlm_query   |
+----------------+              |    socket → LMHandler      |
                                +----------------------------+
```

- `RLM.__init__` 接收 `backend`（`openai`/`anthropic`/`gemini`/`portkey`/...）+ `environment`（`local`/`ipython`/`docker`/`modal`/`prime`/`daytona`/`e2b`），构造时按需 import（`rlm/environments/__init__.py:18-25` 用 `__getattr__` 懒加载 IPython）。
- papers_qa 实际跑的是 `LocalREPL`（`environment="local"`），代码**在同一个 Python 进程里 `exec(code, globals, locals)`**——globals 只放白名单内的 builtins（`_SAFE_BUILTINS`，`local_repl.py:55-144`），但同进程意味着仍能 `import os; os.system(...)` 等，**沙箱并不是真正的安全边界**。
- `LMHandler` 起一个 socket server（`rlm/core/lm_handler.py`），REPL 内部 `llm_query()/rlm_query()` 通过 `send_lm_request` 通信。好处是不同 environment（包括跑在容器/远端的 IsolatedEnv 派生类）都能用同一套桥。

### 2.3 关键架构差异

| 维度 | `fast-rlm` | `rlms` |
|---|---|---|
| 执行隔离 | Pyodide WASM 沙箱 + Deno 权限白名单 | 同进程 `exec()` + builtins 白名单 |
| 子代理派生 | 重新 `loadPyodide()`，**全新 REPL** | 在父进程内新建 `LocalREPL` 实例（或同种 env） |
| 跨进程通信 | 子进程参数 + 临时文件 + stdout JSON_RESULT | 进程内 socket + Python 对象引用 |
| 多 backend | 只支持 OpenAI-compatible（统一走 `OpenAI` SDK，凭 `RLM_MODEL_BASE_URL` 切换） | 一等公民支持 OpenAI/Anthropic/Gemini/Azure OpenAI/Portkey/Vercel/vLLM/Prime |
| 多 environment | 一种（Deno+Pyodide） | 七种（local/ipython/docker/modal/prime/daytona/e2b） |
| 冷启动 | 每个子代理都要等 Pyodide + micropip | 几乎为零（同进程） |

---

## 3. RLM 核心循环

### 3.1 主循环结构

**`fast-rlm`（`src/subagents.ts:432-557`）**：

```ts
for (let i = 0; i < MAX_CALLS; i++) {
    const { code, success, message, usage } = await generate_code(messages, model_name, is_leaf_agent, {maxRetries, timeout});
    trackUsage(usage);                                           // 累计 token / cost
    if (totalUsage.cost > MAX_MONEY_SPENT) throw new Error(...);
    if (!success) { /* 没拿到 ```repl``` 块，把错误塞回 messages 继续 */ }
    stdoutBuffer = "";
    try { await pyodide.runPythonAsync(code); }
    catch (error) { stdoutBuffer += `\nError: ${error.message}`; }
    const truncatedText = truncateText(stdoutBuffer);            // 末尾 TRUNCATE_LEN 字符
    if (pyodide.globals.get("__final_result_set__")) {
        const result = pyodide.globals.get("__final_result__");
        if (validate && !validate(result)) {                     // Ajv schema 校验
            // 把错误反馈给模型，重置 flag，循环继续
            continue;
        }
        return result;
    }
    messages.push({ role: "user", content: `${budgetBanner(i, MAX_CALLS)}Output: \n${truncatedText}` });
}
throw new Error("Did not finish the function stack before subagent died");
```

要点：
- 一次循环 = 一次 LLM 调用 + 一次 Pyodide 执行；模型必须把所有代码塞进**单个** `` ```repl ... ``` `` 块（`call_llm.ts:66-67` 用 `replMatches.map(m => m[1].trim()).join("\n")` 合并；`prompt.ts:225` 强调 "Do not output multiple code blocks"）。
- 完成信号是 Python 侧把 `__final_result__` 赋值后将 `__final_result_set__` 置 `True`，由 `pyodide.globals.get()` 跨语言读出。
- 步数过半（`stepJustFinished+1 > MAX_CALLS/2`）后，REPL 输出前面会自动追加 `[Steps remaining after this one: N / MAX]` 横幅，提示模型用子代理分而治之（`subagents.ts:111-120`）。

**`rlms`（`rlm/core/rlm.py:282-437`）**：

```python
for i in range(self.max_iterations):
    self._check_timeout(i, time_start)
    if self.compaction and current_tokens >= threshold_tokens:
        message_history = self._compact_history(...)            # 主动压缩历史
    current_prompt = message_history + [build_user_prompt(root_prompt, i, ...)]
    iteration = self._completion_turn(prompt=current_prompt, ...)
    self._check_iteration_limits(iteration, i, lm_handler)      # 错误/预算/token 检查
    final_answer = None
    for block in iteration.code_blocks:
        if block.result.final_answer is not None:
            final_answer = block.result.final_answer
            break
    iteration.final_answer = final_answer
    if iteration.response.strip():
        self._best_partial_answer = iteration.response          # 备援快照
    if self.logger:
        self.logger.log(iteration)
    if final_answer is not None:
        return RLMChatCompletion(..., response=final_answer, ...)
    new_messages = format_iteration(iteration)                  # 多块 ```repl``` 都拼进去
    message_history.extend(new_messages)
# 超 iteration 仍未结束 → 强制收尾 _default_answer
```

要点：
- 一次迭代可以包含**多个** `` ```repl``` `` 块，由 `find_code_blocks()` 用正则 `r"```repl\s*\n(.*?)\n```"` 把它们一一抽出后顺序 `environment.execute_code()`（`rlm/core/rlm.py:605-610`，`rlm/utils/parsing.py:10-22`）。
- 完成信号不是返回值，而是 REPL 里的 `answer["ready"] = True`，由 `_AnswerDict` 子类自动捕获（`rlm/environments/local_repl.py:26-47`、`208-245`）。
- 即便循环耗尽也不会抛错——`_default_answer()` 用现有历史再调一次 LM 拿一个**回退答案**（`rlm.py:620-643`）。同时 `_best_partial_answer` 在过程中持续刷新，配合 `TimeoutExceededError(partial_answer=...)` 等异常携带"半成品"。

### 3.2 完成（"FINAL"）语义对比

| | `fast-rlm` | `rlms` |
|---|---|---|
| API 形态 | `FINAL(value)`（函数调用） | `answer["content"] = ...; answer["ready"] = True`（字典赋值） |
| 触发机制 | Python 闭包里改写 `__final_result__` + `__final_result_set__` 两个全局 flag，TS 侧用 `pyodide.globals.get()` 读出 | 自定义 `dict` 子类 `_AnswerDict`，覆写 `__setitem__`，`ready=True` 时回调 `_capture_answer` 把内容保存到 `REPLResult.final_answer` |
| 验证 | Ajv 校验 schema；失败把 path+message 反馈给模型并 reset flag，继续循环（`subagents.ts:501-528`） | 无内置 schema 校验，应用层自己保证 |
| 错误回收 | "代码里没 ```repl``` 块" 也算一步，把"请用 repl 块"作为 user message push 回去（`subagents.ts:458-469`） | 解析阶段不抛错，stderr 进 `REPLResult.stderr`；连续 `max_errors` 次失败抛 `ErrorThresholdExceededError` |

### 3.3 子代理递归

**`fast-rlm`** 只有一种：`await llm_query(context, schema=None, tools=[...])`

- 实际是 TS 函数 `js_llm_query`（`subagents.ts:172-219`），它**重新调用 `subagent(context, subagent_depth+1, ...)`**，即子代理拿到的是一个**全新的 Pyodide REPL**，可继续递归。
- 子代理用模型名 `SUB_AGENT`（默认 `minimax/minimax-m2.5`），根代理用 `PRIMARY_AGENT`（默认 `z-ai/glm-5`）。
- 到 `MAX_DEPTH` 那一层走 `LEAF_AGENT_SYSTEM_PROMPT`（剥掉 `llm_query` 相关段落，告诉模型"自力解决"），`call_llm.ts:59` 按 `is_leaf_agent` flag 二选一。

**`rlms`** 提供**两种**：
- `llm_query(prompt, model=None)`：单次 LM 完成（**不开 REPL，不递归**），快速、用于"抽取/总结/Q&A 一个 chunk"。在 `LocalREPL._llm_query` 里直接发 `send_lm_request` 走 socket（`local_repl.py:258-280`）。
- `rlm_query(prompt, model=None)`：派生**新的子 RLM**，子代理拥有自己的 REPL，能继续迭代。在 `LocalREPL._rlm_query` 内调用 `self.subcall_fn`（即 `RLM._subcall`，`rlm.py:653-817`）。
- 还有批量版 `llm_query_batched(prompts)` / `rlm_query_batched(prompts)`，后者用 `ThreadPoolExecutor(max_workers=max_concurrent_subcalls)` 并行（`local_repl.py:381-394`）。
- `rlm_query` 在 `subcall_fn is None`（即 `max_depth <= 1`）时**回退**为 `llm_query`（`local_repl.py:324-333`）。

> **判别要点**：`fast-rlm` 的 `llm_query` 永远是递归 RLM（除非已到 max_depth）；`rlms` 把"单次 LM"和"递归 RLM"做成两个**显式分开的函数**，模型在 prompt 里被教导"何时用 `llm_query` 何时用 `rlm_query`"。

### 3.4 模型选择策略

| | `fast-rlm` | `rlms` |
|---|---|---|
| 根模型 | `PRIMARY_AGENT`（config 默认 `z-ai/glm-5`） | `backend_kwargs["model_name"]`（papers_qa 默认 `deepseek/deepseek-v4-flash`） |
| 子代理模型 | `SUB_AGENT`（默认 `minimax/minimax-m2.5`），全局统一 | 默认继承父；模型可在 `llm_query(prompt, model="...")` 现场指定；也可通过 `other_backends` 注册多个备选模型，按 model name 路由 |
| 叶节点（max_depth）特殊处理 | 切到 `LEAF_AGENT_SYSTEM_PROMPT`，模型不再被告知 llm_query | 走 `_fallback_answer` 直接 LM 单次完成（`rlm.py:645-651`），跳过 REPL 循环 |

---

## 4. 提示词工程

### 4.1 `fast-rlm` 的两套 system prompt

`src/prompt.ts` 一文件提供两份，按 `is_leaf_agent` flag 互斥使用：

- **`SYSTEM_PROMPT`**（226 行）：完整描述 REPL 玩法，包括：
  - `context` 是 string 还是 dict 的两种 probe（动态根据传入决定）
  - `await llm_query(context_or_dict, schema=None, tools=[...])` 的完整用法（输入可为 dict！）
  - 工具下传协议："**Sub-agents do NOT automatically inherit your tools.**"
  - 输出 schema 在 step 0 印给模型，并解释失败后 REPL state 保留可重试
  - 显式鼓励 `asyncio.gather(*tasks)` 并行子代理（`prompt.ts:159-181`）
  - 多种 chunking 示例：按段落、按 markdown header、按 chunk_size 整除
  - "不要 print() 一行行拼输出"、"不要 FINAL("variable_name") 错误地把字符串当变量返回" 等反模式
- **`LEAF_AGENT_SYSTEM_PROMPT`**（91 行）：剥掉所有 `llm_query` 段落 + 工具下传段落，告诉叶代理"自力解决"。

> 设计哲学：把"如何使用 REPL"和"何时调子代理"作为**显式可教**的知识写进系统提示，模型按部就班学。

### 4.2 `rlms` 的基底 prompt + `papers_qa` 的双语增强

`rlms` 的 `RLM_SYSTEM_PROMPT`（`rlm/utils/prompts.py:7-114`）：
- 描述七大 REPL 内置：`context`、`llm_query`、`llm_query_batched`、`rlm_query`、`rlm_query_batched`、`SHOW_VARS`、`answer` dict
- 通过 `{custom_tools_section}` 占位符插入用户自定义工具描述（占位符在 `build_rlm_system_prompt` 里 `.format()` 时填入，`utils/prompts.py:154`）
- 给出"何时用 `llm_query` 何时用 `rlm_query`"的判别指南
- 完成时 `answer["content"] = ...; answer["ready"] = True`

`papers_qa.prompts.build_bilingual_system_prompt`（`papers_qa/prompts.py:108-124`）的做法：

```python
def build_bilingual_system_prompt(num_papers: int) -> str:
    addendum = BILINGUAL_ADDENDUM.replace("{num_papers}", str(num_papers))
    # 关键：BILINGUAL_ADDENDUM 里有大量字面量花括号（f-string 范例、{paper_id} 占位符），
    # 而 rlms 后续会对最终拼接做一次 .format(custom_tools_section=...)。
    # 所以这里必须把 addendum 中所有 { } 翻倍转义。
    addendum = addendum.replace("{", "{{").replace("}", "}}")
    return RLM_SYSTEM_PROMPT + addendum
```

`BILINGUAL_ADDENDUM` 是 papers_qa 双语领域最值钱的工程沉淀，主要规则（`papers_qa/prompts.py:6-105`）：

1. **关键词扩展**（5–15 个英文变体）：直接翻译 + 缩写 + 同义词 + 子概念。例：`"GKD 跟 SeqKD 在损失函数上的区别" → ["GKD","Generalized Knowledge Distillation","SeqKD","Sequence-Level KD","loss function","JSD","KL divergence","forward KL","reverse KL"]`
2. **近重复论文去重**：同一篇论文常以多种 paper_id 存在（如 `Qwen3 Technical Report` / `Qwen3_Technical_Report` / `Yang_2025_2505.09388`），用首 200 字符对比，**保留一份**再交给 `llm_query`。
3. **使用 paper_ids 白名单缩窄搜索**："Qwen 3" / "DeepSeek-R1" 这类被点名的模型，先做 `[pid for pid in context if "qwen" in pid.lower()]` 再传 `paper_ids=` 给 `search_papers`。
4. **批量并行**：`llm_query_batched([...])` 一次扫多篇候选。
5. **最终中文输出**：若 `llm_query` 返回了英文，必须再用 `llm_query` 翻译；不许直接交付。
6. **数字反幻觉**：`NEVER GUESS NUMBERS FROM YOUR OWN TRAINING DATA. ... Adding a disclaimer like "假设性示例" or "仅供参考" does NOT make a guessed number acceptable.`
7. **强制引用 paper_id**：`"（据 Agarwal_2024_2306.13649 / Qwen3_Technical_Report 所述）"`

### 4.3 提示设计差异对照

| 维度 | `fast-rlm` | `rlms` 基底 | `papers_qa` 增强 |
|---|---|---|---|
| 完成机制描述 | `FINAL(value)` 函数 | `answer["content"]/`["ready"]` 字典 | 同 rlms |
| 并行子代理 | 鼓励 `asyncio.gather` | 鼓励 `llm_query_batched` / `rlm_query_batched` | 强调 `llm_query_batched` |
| 工具描述位置 | step 0 REPL 输出里 `Available tools (...)` 部分（`subagents.ts:370-394`） | system prompt 的 `{custom_tools_section}` 占位符 | 跟随 rlms，但应用层并未额外说明工具 |
| 反模式提醒 | "不要 print() 一行行构造输出"、"不要多个 ```repl``` 块" | 较少 | 大量领域反模式（不许编数字、不许英文交付） |
| 输出 schema | 一等公民（步 0 印 JSON Schema、失败反馈错误） | 未提供 | 未使用 |

---

## 5. 工具系统

### 5.1 `fast-rlm`：源码反射 + 跨进程 + 显式下传

工具流程（`fast_rlm/_runner.py:120-133`、`219-223`，`src/subagents.ts:290-302`、`303-326`）：

1. Python 侧 `inspect.getsource(tool)` 抽出函数源码 → `textwrap.dedent` → 写入临时 JSON 文件
2. Deno 读这个文件，转给 `subagent(toolSources=[...])`
3. Pyodide 内的 `__register_tool__(src)` 用 `exec(src, globals(), _ns)` 在子 namespace 里运行源码，挑出第一个 callable，挂上 `__fast_rlm_source__` 属性，注入 `globals()` 和 `__tools__` 列表
4. 模型在 step 0 的初始 probe 里只看到工具的 **签名 + docstring**（不看源码），并被标记 `[sync]` / `[async — needs await]`

**子代理工具下传协议**（这是 `fast-rlm` 最特别的一点）：
- 父代理的工具**不会自动**传给子代理。
- 父代理必须显式写 `await llm_query(context, tools=[my_fn])`；Python 层 `llm_query` 实现里又会 `inspect.getsource(_t)` 再次抽源码塞给 JS 桥（`subagents.ts:303-326`）。
- 工具**必须自包含**：`import` 写在函数体里，不能闭包外部变量——因为子代理是全新 Pyodide REPL，外层状态根本不存在。

> 这套机制把"何处可用什么工具"约束成**词法可见**：读父代理代码就知道哪些工具会传下去。代价是工程上较繁琐——你必须为每个想用的工具显式书写 `tools=[...]`。

### 5.2 `rlms`：注册即可用 + 自动继承 + 可关闭

工具流程（`papers_qa/runner.py:46-72`，`papers_qa/search.py:23-78`，`rlm/environments/local_repl.py:234-242`）：

1. 应用层构造工具描述：
   ```python
   custom_tools = {
       "search_papers": {"tool": search_papers, "description": SEARCH_DESCRIPTION}
   }
   ```
   `tool` 是 Python 闭包，可以捕获 `papers` 字典等应用状态。
2. `RLM(custom_tools=..., custom_sub_tools=None)` 构造时：
   - `custom_tools` 用于根代理 REPL
   - `custom_sub_tools` 给子代理；`None` 表示**继承** `custom_tools`，传 `{}` 即子代理无工具（`rlm/core/rlm.py:131-133`）
3. `LocalREPL.setup()` 把工具按 callable / 非 callable 分别放进 `globals` 或 `locals`（`local_repl.py:236-242`），并禁止覆盖保留名（`base_env.py:13-24`：`llm_query, llm_query_batched, rlm_query, rlm_query_batched, SHOW_VARS, answer, context, history`）。
4. 工具描述通过 `format_tools_for_prompt()` 拼进 system prompt 的 `{custom_tools_section}` 占位（`base_env.py:96-127`）。

**与 fast-rlm 的关键差异**：

| 维度 | `fast-rlm` | `rlms` |
|---|---|---|
| 工具捕获形式 | 函数源码（`inspect.getsource`） | 函数对象本身（Python 引用） |
| 闭包变量 | 不允许（跨进程） | 允许（同进程） |
| 子代理继承 | 默认不继承，必须显式 `tools=[...]` | 默认继承（除非 `custom_sub_tools={}`） |
| 保留名校验 | 无（理论上模型可被诱导覆写 `FINAL`） | `RESERVED_TOOL_NAMES` 强校验 |
| 非 callable 工具 | 不直接支持（要写成函数） | 支持："API_KEY": "sk-..." 之类直接作为 REPL 变量 |
| 描述呈现 | 只在 step 0 REPL 输出里出现一次 | 持久写在 system prompt 里 |

### 5.3 papers_qa 的 search_papers 工具

```python
# papers_qa/search.py:30-71
def search_papers(keywords, top_k=30, snippet_chars=400, paper_ids=None):
    # 不区分大小写的子串匹配 OR；按 hit 总数排序，返回 [{paper_id, score, hits, snippet}, ...]
```

这是一个**典型的"应用层捷径"**：
- 用 Python 闭包捕获 `papers` 字典和它的小写副本 `lowered`，搜索时不必把全文反复递交给 LLM。
- snippet 是以首个命中位置为中心切 ±200 字符，让 LLM 一眼看到上下文。
- 这个工具在 fast-rlm 里也能写，但要么把整个 `papers` dict 序列化进函数源码（不可行），要么把工具改写成无闭包形式（每次自己读盘），要么改用 `dict` 形式的 `context` 直接传给 LLM。

---

## 6. 数据平面与安全控制

### 6.1 上下文注入

| | `fast-rlm` | `rlms`/papers_qa |
|---|---|---|
| 字符串 context | 嵌入 Python 字面量字符串：`context = "..."`（`subagents.ts:224`） | 写临时 txt 文件，REPL 内 `with open(...) as f: context_0 = f.read()`（`local_repl.py:421-425`） |
| dict/list context | `context = __import__('json').loads("...")`（`subagents.ts:225-226`），保证拿到真正的 Python dict 而非 JsProxy | 写临时 JSON 文件，`json.load(f)` 注入 `context_0`（`local_repl.py:427-431`） |
| 初始 probe | step 0 自动打印类型、长度、首末 500 字符（或 dict 的 keys + 200 字符预览），见 `subagents.ts:345-368` | system prompt 第二条消息里告知 `context_type` 和 `context_lengths`（`rlm/utils/prompts.py:156-160`） |
| 多上下文 | 不支持 | `add_context()` 自动版本化 `context_0/1/...`，`context` 别名指向 `context_0`（`local_repl.py:399-438`） |

> 用临时文件加载 context 看似多此一举，实际目的是**避免 context 本身被序列化进每次的 REPL 代码片段**——否则一旦 LM 不小心 `print(context)`，几十万字符的上下文会立刻塞爆下一步的 message history。

### 6.2 输出截断与历史压缩

| | `fast-rlm` | `rlms` |
|---|---|---|
| 单步 stdout 截断 | `truncate_len`（默认 2000），保留末尾 N 字符，前缀 "[TRUNCATED: Last N chars shown].." 或 "[FULL OUTPUT SHOWN].."（`subagents.ts:89-103`） | `format_iteration(max_character_length=20000)` 拼 history 时截断（`rlm/utils/parsing.py:42-50`） |
| 历史压缩 | 无 | `compaction=True` + `compaction_threshold_pct=0.85`：根历史达到模型上下文 85% 时，让模型自总结，把摘要塞进 `history` REPL 变量并重置历史（`rlm/core/rlm.py:534-591`） |
| 预算横幅 | "剩余步数 <50% 时" 在每步输出前缀 `[Steps remaining after this one: N / MAX] [建议用 llm_query 分而治之]`（`subagents.ts:111-120`） | 无类似机制 |

### 6.3 预算与超时

| 控制项 | `fast-rlm` | `rlms` |
|---|---|---|
| 金额预算 | `max_money_spent` (USD)，从 OpenAI/OpenRouter `usage.cost` 累计 | `max_budget` (USD)，由 backend client 自报 `usage.cost`（OpenRouter）累计 |
| 总 prompt token | `max_prompt_tokens` | 无单独项，但 `max_tokens` = 输入+输出之和 |
| 总 completion token | `max_completion_tokens` | 同上合并 |
| 超时 | 在 LLM 客户端层 `timeout_ms`（默认 600 s）；无整体 wall-clock 超时 | `max_timeout` (s) 跑前检查；子代理派生时计算 `remaining_timeout = max_timeout - elapsed`（`rlm.py:728-739`） |
| 错误阈值 | 无显式上限（只算每步是否抓到 ```repl```） | `max_errors` 连续错误后抛 `ErrorThresholdExceededError`（`rlm.py:480-496`） |
| 超限语义 | 直接 `throw new Error`，run 失败 | 抛带 `partial_answer` 的自定义异常（`BudgetExceededError`/`TimeoutExceededError`/...），允许调用方拿到半成品 |

### 6.4 输出 schema

| | `fast-rlm` | `rlms`/papers_qa |
|---|---|---|
| 是否支持 | **是**，一等公民 | 否（无内置） |
| 输入形式 | Pydantic 类、`list[...]` 泛型、Python 原始类型、JSON Schema dict（`fast_rlm/_runner.py:25-48`） | 不适用 |
| 校验时机 | 每次 `FINAL()` 后调 Ajv 校验；失败把"schema + 错误路径 + 信息"以 user message push 回去，REPL state 保留可重试（`subagents.ts:501-528`） | 不适用 |
| 子代理 schema | `llm_query(context, schema={"type":"array","items":{...}}, tools=[...])`，子代理在 step 0 看到 schema 并被同样校验（`subagents.ts:186-198`） | 不适用 |

> 这是 fast-rlm 最有"工业感"的设计之一。`rlms`+papers_qa 的应用层为了拿到结构化结果，只能在 prompt 里规定 markdown 表格规则，无机器校验。

### 6.5 环境变量与凭据注入

| | `fast-rlm` | `rlms`/papers_qa |
|---|---|---|
| 注入路径 | `env_variables=dict[str,str]` → 临时文件 → Deno 读 → Pyodide 内 `os.environ.update(...)`（`subagents.ts:227-230`） | papers_qa 直接从宿主 `os.environ` 读取（`config.py:31-56`） |
| 范围 | 仅在 Pyodide 内可见；**Deno 宿主进程拿不到**；不会出现在 prompt/log 中 | 宿主进程全局可见 |
| 用途场景 | 给工具用：例如 Tavily/Exa 的 API key 通过 `env_variables` 注入，工具体里 `os.environ["TAVILY_API_KEY"]` 取（README:175-204） | 直接读环境变量；`.env` via `python-dotenv` |

### 6.6 沙箱安全模型

| | `fast-rlm` | `rlms`/papers_qa |
|---|---|---|
| 隔离层 | WebAssembly + Deno `--allow-*` 白名单 | 同进程 Python，依赖 `_SAFE_BUILTINS` 白名单（屏蔽 `eval/exec/input/compile/globals/locals`） |
| 文件系统 | Pyodide 虚拟 FS；通过 fetch 走宿主网络但不能 `open` 宿主文件 | 完全访问宿主文件系统（papers_qa README 警告 `--share` 暴露 `PAPERS_QA_PAPERS_DIR`） |
| 网络 | 受 Deno `--allow-net` 控制（fast-rlm 默认全开） | 完全访问宿主网络 |
| 进程/系统调用 | Deno `--allow-sys=hostname,osRelease` 极小白名单 | LLM 生成的 Python 代码理论上可以 `import os; os.system(...)` 等危险操作 |

> `rlms` 的安全模型适用于"完全可信"的应用场景（自己跑自己写的 prompt）；当 LLM 生成的代码可能含有恶意意图（例如 prompt-injection 试图通过 RLM 自身越权）时，rlms 的同进程沙箱是不够的。Daytona/Modal/Docker/E2B 这些 environment 才是 rlms 给"不可信代码"准备的隔离方案。

---

## 7. 可观测性

### 7.1 fast-rlm 的日志体系

- **持久化**：Pino → JSONL（`src/logging.ts:36-57`），每条记录含 `run_id / parent_run_id / depth / step / event_type / code / output / hasError / reasoning / usage / timestamps / totalUsage`。事件类型：`agent_start / code_generated / execution_result / final_result / agent_end`。
- **终端**：spinner + 步级别 `printStep` + 全局用量摘要（`ui.ts`、`usage.ts`）。
- **离线查看**：`fast-rlm-log run_xxx.jsonl --stats` 简单统计；`--tui` 启动 Bun + React 的 TUI viewer（`fast_rlm/_cli.py:49-91`）。
- **流式**：**没有**（fast-rlm 是 subprocess 离线模式——run 完才能从 output JSON 拿结果）。

### 7.2 rlms 的日志体系

- `RLMLogger`（`rlm/logger/rlm_logger.py`）：每次 `completion()` 写一个 `{file_name}_{ts}_{run_id}.jsonl`，事件类型 `metadata` + `iteration`。每条 `iteration` 含完整 `prompt / response / code_blocks (含 stdout/stderr/locals/llm_calls) / final_answer / iteration_time`。
- 在内存里保留 trajectory，结束时挂到 `RLMChatCompletion.metadata`。
- `VerbosePrinter`（`rlm/logger/verbose.py`，538 行）：rich 终端打印，含 metadata、迭代、final answer、限额超出等。
- **流式**：**有可用钩子**——`on_subcall_start / on_subcall_complete / on_iteration_start / on_iteration_complete` 回调（`rlm.py:73-76, 745-781`），父代理把 callback 传给子代理实现嵌套追踪。

### 7.3 papers_qa 的流式实现

`papers_qa/streaming.py` 用了一个非常巧妙的桥接：

```python
class _QueueLogger(RLMLogger):
    def log(self, iteration: RLMIteration) -> None:
        super().log(iteration)                              # 仍然写盘
        self._events.put(_iteration_to_event(iteration))    # 同时推队列
```

`stream_ask(qa, question, history_text)` 生成器：
1. 给 `qa.rlm.logger` 临时换上 `_QueueLogger`（用模块级 `_STREAM_LOCK` 序列化并发，因为 `rlm.completion` 会写 `qa.rlm.logger`）
2. 在 daemon 线程里跑 `qa.rlm.completion(prompt=qa.papers, root_prompt=root_prompt)`
3. 主线程 `events.get(timeout=600)` 阻塞，每收到一个 iteration 事件就 `yield` 给 Gradio
4. 接收到 `_DONE_SENTINEL` 时根据 `result_holder["error"]` 决定 `yield {"type": "final"}` 或 `{"type": "error"}`

这套设计的代价：
- 应用层必须自己加锁防并发污染 logger（`_STREAM_LOCK`）
- daemon 线程不能从外部安全打断；用户提前关 Gradio tab，后台线程仍会跑到完——继续烧 API 预算
- 超时（600 s）后只是 `yield {"type":"timeout"}`，后台线程仍在跑

> 把"线程 + 队列"嫁接到 `rlms` 的同步 API 上，是因为 rlms 没有原生 async/streaming 接口。如果 fast-rlm 也想做实时 UI，由于它是 subprocess 模式，需要解析子进程的 stdout/JSONL 增量——目前并未实现。

---

## 8. 双语 / 领域定制

### 8.1 fast-rlm

无特定语言假设；`examples/` 全部为英文场景（book_rec_with_exa、podcast、tools_market_scanner、structured_io、parallel_r_count……）。中文不是设计目标，但模型层支持 OpenAI-compatible 后任意中文模型。

### 8.2 papers_qa 的领域工程价值

papers_qa 的领域适配集中在三块：

1. **system prompt 增强**（`BILINGUAL_ADDENDUM`，见 §4.2）——可以直接 copy 到任何其他"中文问题 / 英文语料"项目使用，无关于 rlms 实现细节。
2. **OpenAI 客户端 monkey-patch**（`openai_patch.py`）——`rlms.clients.openai.OpenAIClient.completion` 不允许设置 `temperature`/`max_tokens`/`extra_body`（除 Prime Intellect 特殊路径外，见 `rlm/clients/openai.py:69-89`）。papers_qa 整体 monkey-patch 把这两个能力补回来：
   - `temperature=0.2`（防止默认 1.0 在 Q&A 场景幻觉数字）
   - `extra_body={"thinking":{"type":"disabled"}}`（DeepSeek-v4 native API 用于关闭思考阶段；aiberm 代理静默无效但参数仍透传）
   patch 是幂等的（`_PATCH_FLAG` 标志位），且在 papers_qa 导入时立即执行（`runner.py:24-27`）。
3. **数值反幻觉与引用 paper_id**——见 §4.2 项 6、7。

> 这部分是 papers_qa 最能"独立带走"的工程资产：它不依赖 `rlms` 的特定版本，把"在 LLM Q&A 中如何不让模型瞎编数字"这个跨产品共性问题落到了系统提示和 OpenAI 客户端两个层面。

---

## 9. 分发、依赖与集成

| 维度 | `fast-rlm` | `rlms` | `papers_qa` |
|---|---|---|---|
| Python 版本 | 3.10+ | 推断 3.10+（pyproject 未读全） | 3.11+ |
| 安装 | `pip install fast-rlm`，需先装 Deno 2+ | 在 papers_qa 里通过 `uv pip install -e ".[dev]"` 拉本地 editable | 同上 |
| 第三方运行时 | **必需** Deno；可选 Bun（TUI） | 无 | 无 |
| Backend 矩阵 | 任意 OpenAI-compatible | OpenAI / Anthropic / Gemini / Azure OpenAI / Portkey / Vercel / vLLM / Prime | 通过 rlms 全部继承 |
| Environment 矩阵 | 一种（Pyodide） | 七种（local/ipython/docker/modal/prime/daytona/e2b） | 用 local |
| UI | TUI（Bun） | rich verbose | Gradio Web UI |
| 测试 | `examples/` + `benchmarks/`（无 pytest） | 自带 tests/ | 11 个 pytest 模块 |
| 冷启动 | 慢（每个 subagent 都要 loadPyodide + micropip install requests/httpx） | 接近零 | 接近零 |

---

## 10. 优劣分析

### 10.1 `fast-rlm` 的优势

1. **沙箱真隔离**：Pyodide WASM + Deno 权限白名单使 LLM 生成的代码无法读取宿主文件、不能任意发起系统调用。
2. **Schema 一等公民**：Pydantic 类、`list[T]`、原始类型、JSON Schema dict 任选；失败有结构化反馈给模型，**REPL state 保留**可重试。这是把"工业级合同"塞进了 RLM。
3. **工具下传契约严格**：子代理默认不继承父工具，必须显式 `tools=[...]` 转发；工具必须 self-contained。这种"显式即文档"的设计便于审计哪些工具能跑在哪一层。
4. **论文还原度高**：FINAL 函数、单一 ```repl``` 块、leaf 系统提示词、子代理 = 全新 REPL，这些和 RLM 原文最接近。
5. **多维度硬截断**：金额、completion tokens、prompt tokens 三路并行，违反即抛。
6. **凭据隔离**：`env_variables` 只活在 Pyodide 里，不污染宿主、不进 prompt/log。

### 10.2 `fast-rlm` 的代价

1. **跨语言、冷启动重**：每个 subagent 都要 loadPyodide + `micropip install requests httpx`，对短任务损耗严重；分布式调用难做（每次都要拉新 Deno 进程）。
2. **包生态受限**：Pyodide 的 pure-Python wheel 才能装；C 扩展（如 lxml、pandas-C 分量）部分不可用。
3. **工具必须可反射源码**：lambda、闭包、REPL 定义函数、内建函数都不行。tools 引用外部变量也会在子代理 REPL 失败。
4. **子代理工具转发繁琐**：每层都要 `await llm_query(..., tools=[fn1, fn2, ...])`；多个工具时容易遗忘。
5. **离线日志、无实时流**：UI 体验弱于 Web 应用场景。
6. **只支持 OpenAI-compatible**：要走 Anthropic native、Gemini native、Bedrock 等接口得自己加层。

### 10.3 `rlms`（+`papers_qa`）的优势

1. **纯 Python + 多 backend / multi-environment**：一行配置切换 LLM 厂商或 REPL 后端；从本机调试到远端 Modal/E2B 沙箱一脉相承。
2. **双查询模式**：`llm_query`（单次 LM）和 `rlm_query`（递归 RLM）分开，模型在 prompt 里被教导何时用哪个，比 fast-rlm 单一 `llm_query` 表达力更强。
3. **批量并行**：`llm_query_batched` / `rlm_query_batched` 一等公民，后者用 `ThreadPoolExecutor(max_concurrent_subcalls)`。
4. **历史压缩**：`compaction=True` 在根代理 history 接近模型上下文上限时自动总结，并把摘要塞进 REPL 的 `history` 变量。fast-rlm 没有这一项，长任务超过单 step truncate 后就只能靠模型自管。
5. **半成品答案与软超限**：`max_timeout / max_tokens / max_budget / max_errors` 超限时抛带 `partial_answer` 的异常，调用方仍可拿到当前最好答复——而 fast-rlm 直接失败。
6. **可插拔回调与 logger**：父代理可以注入 `on_subcall_start / complete / on_iteration_*` 回调实现实时 UI（papers_qa 正是基于这点做 Gradio 流式）；可以子类化 `RLMLogger`。
7. **工具更灵活**：闭包合法；callable 和数据一视同仁；保留名校验；默认子代理继承。
8. **持久化 environment**：`persistent=True` + LocalREPL 支持跨 completion 复用 REPL 命名空间（多轮 chat 场景），fast-rlm 没有等价机制。

### 10.4 `rlms`（+`papers_qa`）的代价

1. **沙箱弱**：LocalREPL 是同进程 `exec()`，只能屏蔽 builtin 级别的危险函数，无法对抗能拿到 import 的恶意代码。对不可信代码场景必须切到 Docker/Modal/E2B environment（papers_qa 没用）。
2. **没有 schema 校验**：所有"返回 JSON / 表格"的合同都靠 prompt 约束，模型走偏只能靠应用层手工解析。
3. **OpenAIClient 接口缺位**：默认不支持 `temperature`/`extra_body` 等常用参数，papers_qa 不得不全局 monkey-patch（`apply_temperature_patch`）——这意味着同进程跑多个 `RLM` 时这些参数被强行统一。
4. **多线程 + 全局 logger 状态**：papers_qa 的流式实现要 `_STREAM_LOCK` 序列化并发、要 daemon 线程跑 `completion`、要在 logger 上做 swap，结构复杂；用户提前关页面线程不会停。
5. **rlms 接口体量大**：`RLM.__init__` 20+ 参数（max_iterations, max_depth, max_budget, max_timeout, max_tokens, max_errors, persistent, compaction, max_concurrent_subcalls, on_*_start/complete, ...）；学习曲线比 fast-rlm 的 7 参数 `run()` 陡。
6. **subagent 模型选择不够正交**：fast-rlm 通过两个全局配置 `PRIMARY_AGENT`/`SUB_AGENT` 把"根模型用强、子代理用便宜"做成默认；rlms 的 `other_backends` 还有 "we currently only support one additional backend"（`rlm.py:120-125`）的硬限制。

---

## 11. 何时用哪个

| 场景 | 推荐 |
|---|---|
| 需要把 RLM 嵌入到已有 Python 项目，且不想引入 Node/Deno | `rlms` |
| 需要论文还原度（FINAL、叶提示词、显式工具下传、单 repl 块） | `fast-rlm` |
| 需要硬性结构化输出（Pydantic/JSON Schema 校验） | `fast-rlm` |
| 需要做"中文问题 / 英文语料"问答 | papers_qa 的 prompt 是现成参考 |
| 需要实时 Web UI 流式 | papers_qa 模式（rlms + 自建 streaming） |
| 需要并行子代理（batched） | `rlms` 的 `rlm_query_batched` 现成；fast-rlm 用 `asyncio.gather` |
| 需要本机 + 远端隔离 environment 一套代码搞定 | `rlms` |
| LLM 生成的代码可能不可信 | `fast-rlm`（Pyodide+Deno）或 `rlms` 切到 Docker/Modal/E2B |
| 长任务、需要历史压缩 | `rlms` 的 `compaction=True` |
| 多轮对话复用 REPL state | `rlms` 的 `persistent=True` |

---

## 12. 关键代码引用索引

### fast-rlm
| 关注点 | 位置 |
|---|---|
| Python 子进程桥 | `fast_rlm/_runner.py:136-281` |
| RLMConfig 默认 + 合并 | `fast_rlm/_runner.py:51-78` |
| 工具源码反射 | `fast_rlm/_runner.py:120-133` |
| 主循环 | `src/subagents.ts:432-557` |
| 子代理派生 | `src/subagents.ts:172-219` |
| Pyodide 初始化 + REPL 设置 | `src/subagents.ts:141-327` |
| 工具注册（Pyodide 内） | `src/subagents.ts:290-302` |
| Ajv schema 校验反馈 | `src/subagents.ts:501-528` |
| 步预算横幅 | `src/subagents.ts:111-120` |
| 输出截断 | `src/subagents.ts:89-103` |
| 模型按深度切换 + leaf prompt | `src/subagents.ts:137`, `src/call_llm.ts:59` |
| 系统提示词（非 leaf） | `src/prompt.ts:1-226` |
| 系统提示词（leaf） | `src/prompt.ts:230-322` |
| 用量 + 预算硬限 | `src/subagents.ts:443-454`, `src/usage.ts` |
| Pino 日志事件 | `src/logging.ts:65-156` |
| CLI 工具（fast-rlm-log） | `fast_rlm/_cli.py:49-95` |

### rlms
| 关注点 | 位置 |
|---|---|
| `RLM` 构造（20+ 参数） | `rlm/core/rlm.py:49-189` |
| 主循环 | `rlm/core/rlm.py:282-437` |
| 单步完成 + 多 repl 块 | `rlm/core/rlm.py:593-618` |
| `_subcall`（递归 RLM） | `rlm/core/rlm.py:653-817` |
| 错误/预算/token 限制 | `rlm/core/rlm.py:459-532` |
| Compaction 主总结循环 | `rlm/core/rlm.py:534-591` |
| Fallback（max_depth 到顶） | `rlm/core/rlm.py:645-651` |
| 默认收尾 answer | `rlm/core/rlm.py:620-643` |
| 系统提示词（基底） | `rlm/utils/prompts.py:7-114` |
| `build_user_prompt`（每轮） | `rlm/utils/prompts.py:168-195` |
| Code-block 抽取（正则） | `rlm/utils/parsing.py:10-22` |
| `format_iteration`（含截断） | `rlm/utils/parsing.py:25-57` |
| `_AnswerDict`（FINAL 等价） | `rlm/environments/local_repl.py:26-47` |
| LocalREPL setup + 工具注入 | `rlm/environments/local_repl.py:208-242` |
| `llm_query` 单发 | `rlm/environments/local_repl.py:258-280` |
| `rlm_query` 递归 | `rlm/environments/local_repl.py:313-333` |
| `rlm_query_batched` 并行 | `rlm/environments/local_repl.py:335-397` |
| Context 临时文件注入 | `rlm/environments/local_repl.py:399-438` |
| `RESERVED_TOOL_NAMES` | `rlm/environments/base_env.py:13-24` |
| 工具描述格式化 | `rlm/environments/base_env.py:96-127` |
| OpenAIClient（patch 目标） | `rlm/clients/openai.py:69-113` |
| RLMLogger 接口 | `rlm/logger/rlm_logger.py:16-91` |

### papers_qa
| 关注点 | 位置 |
|---|---|
| 配置（frozen dataclass + env） | `papers_qa/config.py:11-57` |
| 论文加载 | `papers_qa/loader.py:10-34` |
| 搜索工具 | `papers_qa/search.py:23-78` |
| 双语 prompt 增强 + 转义技巧 | `papers_qa/prompts.py:108-124` |
| 反幻觉/中文/引用规则 | `papers_qa/prompts.py:64-103` |
| OpenAI client monkey-patch | `papers_qa/openai_patch.py:33-107` |
| Runner（构造 RLM） | `papers_qa/runner.py:41-94` |
| 流式 logger 子类 | `papers_qa/streaming.py:46-58` |
| `stream_ask` 生成器 | `papers_qa/streaming.py:93-177` |

---

## 13. 限制与未覆盖

- 本报告基于静态源码审阅，没有跑过任何基准。性能描述（如冷启动慢、并行更快）都来源于结构而非测量。
- `rlms` 的非 local environment（docker/modal/e2b/...）共约 2 K 行未细读，仅基于 `__init__.py` 的路由与 `base_env.py` 的抽象推断；他们与 LocalREPL 的具体差异未展开。
- `rlms.clients` 中 OpenAI 之外的 client（anthropic, gemini, azure_openai, portkey）未展开比较。
- `fast-rlm` 的 TUI viewer（Bun + React）只看了入口约束，未审阅其交互细节。
- 未审阅 `rlm/logger/verbose.py`（538 行 rich 美化日志）、`rlm/core/comms_utils.py`（socket 协议细节）、`rlm/utils/token_utils.py`（context_limit 表）。这些都对运行行为有影响，但与"RLM 实现"主线对比关系小。
- 未抓两侧的 README/docs 完整文档生态；fast-rlm 有 mkdocs 站点，papers_qa 有 `中文文档.md`，各自的"声明的设计意图"可能比代码更细。

---

## 14. 一句话定位

> **`fast-rlm` 是"学术 RLM 论文工程化的小而紧的实现"；`rlms`（+`papers_qa`）是"在 Python 生态里把 RLM 做成可塑产品的复杂实现"。** 二者侧重正交：前者拼对齐和约束、后者拼集成和易用。读懂它们的差异，关键是看你的下一个项目更需要哪一侧。
