# RLM 教学型 Jupyter Notebook 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 superpowers:subagent-driven-development 或 superpowers:executing-plans 逐任务执行。
>
> **教学定位优先于工程完备性**——目标是让读者 "看一段、跑一段、懂一步"，而不是产出能拿去做生产的库。

**Goal:** 产出一份从零手写、可在本地实际跑通的 Jupyter Notebook，演示 RLM（Recursive Language Models）算法如何对 `/home/juli/RLM/CAE-MDs` 知识库做问答；读者读完能讲清 RLM 的核心机制。

**Architecture:** Notebook 单文件、零外部依赖框架（不使用 fast-rlm / rlms 库），自底向上手写六个核心组件：① REPL 沙箱、② FINAL 完成信号、③ 主循环、④ `llm_query` 单发子代理、⑤ `rlm_query` 递归子代理、⑥ `search_kb` 关键词工具。每加一个组件就跑一次端到端 demo，看效果与上一版的差距。

**Tech Stack:** Python 3.11+ 标准库 + `openai>=1.0` SDK + `python-dotenv`；通过 OpenAI-compatible 接口（base_url=`https://dubrify.com/v1`）调 `deepseek/deepseek-v4-flash`。

---

## 0. 重要前置事项（必读，不是 task）

### 0.1 安全提示

用户在 `/plan` 参数里以明文形式提供了 `api_key=sk-YgebwDQpNRXnULbc7XxQLfIMgxMTc7eC0ZH4uhVVOUncz4Qm`。

- **该 key 已出现在本次对话的对话日志中**——按习惯应立即轮换。
- 本计划与 notebook **均不允许把这个 key 写入任何被 git 追踪的文件**（参 `~/.claude/rules/security.md`）。
- 实施时，key 只存活于 `/home/juli/RLM/rlm-tutorial/.env`（同目录 `.gitignore` 排除）。

### 0.2 文件结构

```
/home/juli/RLM/rlm-tutorial/
├── rlm_tutorial.ipynb       # 主交付物
├── .env                     # api key（gitignored；脚本生成，提示用户校验后再 source）
├── .env.example             # 不含 key 的模板，可入库
├── .gitignore               # 排除 .env / .ipynb_checkpoints
└── README.md                # 一句话如何跑 + 故障排查
```

### 0.3 RLM 设计选择（**更新**：对齐用户提供的 fast-rlm 参考 system prompt）

用户提供了 fast-rlm 的 `SYSTEM_PROMPT` 作为参考，照此对齐设计。学习版 RLM 选取的最小特性集：

| 组件 | 取的 | 不取的 |
|---|---|---|
| 完成信号 | `FINAL(value)` 函数（与 fast-rlm 同语义） | rlms 的 `answer["ready"]=True`（同语义但更绕） |
| REPL | 同进程 + `ast.PyCF_ALLOW_TOP_LEVEL_AWAIT` 支持 `await`；持久 namespace dict | Pyodide / Docker / 子进程 |
| 代码块协议 | 单个 ```` ```repl ... ``` ```` 块（与 fast-rlm 同） | 多块 |
| 子代理 | **单一 `async llm_query(context, ...)` 即递归子代理**（fast-rlm 模型） | rlms 那种 llm_query/rlm_query 分裂 |
| 工具 | `search_kb(keywords)` 关键词子串搜索 | schema/Pydantic 校验 |
| 上下文截断 | 末尾 N 字符 | 历史压缩 |
| 预算 | 步数上限 + 深度上限 | 美元/token 限额 |
| 多模型 | 单一模型（user 指定的 deepseek-v4-flash） | 主/子代理分模型 |

**版本进展（更新）**：
- v1：REPL + FINAL + 主循环（无 llm_query 无工具）
- v2：加 **async 递归** `await llm_query(context, ...)`（深度限制；到 max_depth 时退化为直接 LLM 调用）
- v3：加 `search_kb(keywords)` 工具

> 这把原计划的 v2+v3 合并为 v2，更贴近 fast-rlm。系统提示词直接采用用户提供的 fast-rlm `SYSTEM_PROMPT`（去 JS 转义后），叶代理用类似的精简版。

### 0.4 模型注意事项

DeepSeek v4 系列是 **reasoning model**。`papers_qa/openai_patch.py` 的经验提示：在 RLM 这种迭代循环里 thinking 阶段会显著拖慢节奏。Task 1 末会做一次接口探测，根据返回情况决定是否在 `client.chat.completions.create(...)` 里加 `extra_body={"thinking": {"type": "disabled"}}`，并在 notebook 里用 markdown 解释为什么这么做。

---

## 1. 文件结构与责任分工

每个 cell 的责任在 Task 描述里写出，便于读者交叉跳读。Notebook 的逻辑章节：

| 章节 | 类型 | 责任 | 对应 Task |
|---|---|---|---|
| §0 Setup | markdown + code | 安装/加载/烟雾测试 | Task 1 |
| §1 RLM 是什么 | 纯 markdown | 论文核心 + 反例 | Task 2 |
| §2 加载 CAE-MDs | code | 读 markdown → dict + 统计 | Task 3 |
| §3 反例：直接塞进 LLM | code | 算 token、给 LLM、看截断/失败 | Task 4 |
| §4 RLM v1：REPL+FINAL+主循环 | markdown + code | 最小可跑 RLM | Task 5 |
| §5 RLM v2：加 llm_query | markdown + code | 单发子代理 | Task 6 |
| §6 RLM v3：加 rlm_query 递归 | markdown + code | 真正的"R" | Task 7 |
| §7 RLM v4：加 search_kb 工具 | markdown + code | 工具系统 | Task 8 |
| §8 端到端实战 Q&A | code | 跑两个真问题 | Task 9 |
| §9 思考题 + 局限 | markdown | 留给读者 | Task 10 |

---

## 2. 任务

### Task 1: 项目骨架与环境

**Files:**
- Create: `/home/juli/RLM/rlm-tutorial/.gitignore`
- Create: `/home/juli/RLM/rlm-tutorial/.env.example`
- Create: `/home/juli/RLM/rlm-tutorial/.env`（**禁止提交**）
- Create: `/home/juli/RLM/rlm-tutorial/README.md`

- [ ] **Step 1: 建立目录**

```bash
mkdir -p /home/juli/RLM/rlm-tutorial
```

- [ ] **Step 2: 写 `.gitignore`**

```
.env
.ipynb_checkpoints/
__pycache__/
*.pyc
```

- [ ] **Step 3: 写 `.env.example`**

```
# Copy this file to `.env` and fill in your real key.
OPENAI_BASE_URL=https://dubrify.com/v1
OPENAI_API_KEY=sk-REPLACE-ME
OPENAI_MODEL=deepseek/deepseek-v4-flash
```

- [ ] **Step 4: 写 `.env`（含真实 key）**

```
OPENAI_BASE_URL=https://dubrify.com/v1
OPENAI_API_KEY=sk-YgebwDQpNRXnULbc7XxQLfIMgxMTc7eC0ZH4uhVVOUncz4Qm
OPENAI_MODEL=deepseek/deepseek-v4-flash
```

- [ ] **Step 5: 写 `README.md`**

````markdown
# RLM Tutorial Notebook

A from-scratch, runnable tutorial that builds a Recursive Language Model (RLM)
step by step and uses it to answer questions about CAE simulation papers under
`/home/juli/RLM/CAE-MDs`.

## Run

```bash
cd /home/juli/RLM/rlm-tutorial
cp .env.example .env  # then edit .env to put your key
uv pip install --system openai>=1 python-dotenv jupyter nbformat
jupyter lab rlm_tutorial.ipynb
```

> ⚠️ The key in `.env` should never be committed. `.gitignore` excludes it.
````

- [ ] **Step 6: 安装 notebook 所需依赖到当前 Python 环境**

```bash
pip install --quiet "openai>=1" python-dotenv nbformat 2>&1 | tail -5
python3 -c "import openai, dotenv, nbformat; print('deps ok:', openai.__version__, nbformat.__version__)"
```
Expected: `deps ok: 2.x.x 5.x.x`

注：`jupyter` 不强制由本计划安装；用户已习惯用自己的 lab/notebook，让 README 指导即可。

- [ ] **Step 7: API 烟雾测试 + 决定是否禁用 reasoning**

```bash
python3 - <<'PY'
import os
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv("/home/juli/RLM/rlm-tutorial/.env")
client = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"])
# 试两次：一次 plain，一次带 thinking=disabled
for kwargs in [{}, {"extra_body": {"thinking": {"type": "disabled"}}}]:
    try:
        r = client.chat.completions.create(
            model=os.environ["OPENAI_MODEL"],
            messages=[{"role": "user", "content": "Reply with exactly: PONG"}],
            temperature=0.2,
            **kwargs,
        )
        print(f"OK kwargs={kwargs}: {r.choices[0].message.content!r}")
    except Exception as e:
        print(f"ERR kwargs={kwargs}: {type(e).__name__}: {e}")
PY
```

Expected: 至少一种调用返回 `OK ...: 'PONG'`。基于结果决定 notebook 里的 `LLM_KWARGS` 常量是否带 `extra_body`。

- [ ] **Step 8: 提交（不含 .env）**

```bash
cd /home/juli/RLM
git add rlm-tutorial/.gitignore rlm-tutorial/.env.example rlm-tutorial/README.md
git status  # 确认 .env 没被列出
git commit -m "feat(tutorial): scaffold rlm-tutorial directory"
```

---

### Task 2: Notebook 文件落地（空 notebook + 元数据）

**Files:**
- Create: `/home/juli/RLM/rlm-tutorial/rlm_tutorial.ipynb`

- [ ] **Step 1: 用 nbformat 生成空 notebook**

写一个一次性脚本 `/tmp/make_nb.py`：

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"name": "python3", "display_name": "Python 3"},
    "language_info": {"name": "python"},
}
nb["cells"] = []  # 后续 Task 用 nbformat 增量加 cell
with open("/home/juli/RLM/rlm-tutorial/rlm_tutorial.ipynb", "w") as f:
    nbf.write(nb, f)
print("notebook created")
```

```bash
python3 /tmp/make_nb.py
```

Expected: `notebook created`，文件大小 ~200B。

- [ ] **Step 2: 验证空 notebook 合法**

```bash
python3 -c "import nbformat; nb = nbformat.read('/home/juli/RLM/rlm-tutorial/rlm_tutorial.ipynb', as_version=4); print('cells:', len(nb.cells), 'kernel:', nb.metadata.kernelspec.name)"
```

Expected: `cells: 0 kernel: python3`

后续每个 Task 都在 notebook **末尾追加** cell；统一用以下小工具脚本：

```python
# /tmp/append_cell.py
import nbformat as nbf
import sys
nb_path = "/home/juli/RLM/rlm-tutorial/rlm_tutorial.ipynb"
nb = nbf.read(nb_path, as_version=4)
kind, body = sys.argv[1], sys.stdin.read()
if kind == "md":
    nb.cells.append(nbf.v4.new_markdown_cell(body))
elif kind == "code":
    nb.cells.append(nbf.v4.new_code_cell(body))
nbf.write(nb, nb_path)
print(f"appended {kind}; total cells: {len(nb.cells)}")
```

之后每追加一个 cell：`python3 /tmp/append_cell.py md < cell.md` 或 `code < cell.py`。

---

### Task 3: §0 Setup cells（导言 + 依赖加载）

加 3 个 cell。

- [ ] **Step 1: 加 markdown cell（标题 + 摘要）**

```markdown
# 从零实现 RLM：用递归语言模型回答 CAE 论文问题

本 notebook 自底向上手写一个最小可跑的 **Recursive Language Model (RLM)**
（参考 arXiv:2512.24601），并用它回答 `/home/juli/RLM/CAE-MDs` 里
8 篇关于流固耦合 / 水下爆炸 / LS-DYNA 的 CAE 论文的问题。

每一节加一个组件、跑一次 demo，对比上一节的差距。

> 阅读路径：§1 → §4（看核心循环） → §5 → §6 → §7 → §8（真问答）。
> 想直接看效果可跳到 §8。
```

- [ ] **Step 2: 加 markdown cell（运行前提）**

```markdown
## §0 运行前提

1. 在本 notebook 同目录放 `.env`，含：
   ```
   OPENAI_BASE_URL=https://dubrify.com/v1
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=deepseek/deepseek-v4-flash
   ```
2. 安装 `openai>=1`、`python-dotenv`。
3. 知识库目录 `/home/juli/RLM/CAE-MDs` 已包含 8 个 `.md` 文件。
```

- [ ] **Step 3: 加 code cell（导入 + 客户端构造）**

```python
import os, re, json, textwrap, pathlib, time
from dataclasses import dataclass, field
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(pathlib.Path(__file__).parent.joinpath(".env") if False else ".env")

BASE_URL = os.environ["OPENAI_BASE_URL"]
API_KEY = os.environ["OPENAI_API_KEY"]
MODEL = os.environ["OPENAI_MODEL"]

# Reasoning model 默认会想很久；在迭代循环里这种延迟是致命的。
# Task 1 的探测决定是否打开 disable thinking。
LLM_KWARGS = {"temperature": 0.2}  # 若 Task 1 step 7 的探测显示需要禁用 thinking，则改为
# LLM_KWARGS = {"temperature": 0.2, "extra_body": {"thinking": {"type": "disabled"}}}

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

def chat(messages: list[dict], **kw) -> tuple[str, dict]:
    """单次 LM 调用。返回 (content, usage_dict)。"""
    resp = client.chat.completions.create(
        model=MODEL, messages=messages, **{**LLM_KWARGS, **kw}
    )
    u = resp.usage
    return resp.choices[0].message.content or "", {
        "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens, "total_tokens": u.total_tokens
    }

# 烟雾测试：调一次确保链路通
content, usage = chat([{"role": "user", "content": "Reply with: PONG"}])
print(content[:80], "|", usage)
```

> 执行该 cell 时实际要决定 `LLM_KWARGS` 形态：基于 Task 1 step 7 的输出。
> 写入 notebook 前，Plan 执行者要把那行注释 / 启用版本调整为实际可工作的形态，不要让读者运行时遇到错误。

---

### Task 4: §1 RLM 是什么 + §2 加载 CAE-MDs

加 4 个 cell。

- [ ] **Step 1: §1 markdown（核心思想）**

```markdown
## §1 RLM 是什么

RLM 的核心观察：

- 一个普通 LLM 看不到的"远比上下文窗口大"的提示，可以让 LLM 通过一个 REPL
  与之**交互**——它写 Python 代码去 grep、切片、调用子 LLM，最后调用一个
  `FINAL(x)` 把答案交回。
- 子 LLM 调用的结果**不会自动塞进父 LLM 的对话历史**——它只是 REPL 里一个
  Python 变量，父 LLM 想看才 `print(...)`。这就把上下文与中间状态彻底解耦。

因此 RLM ≈ "一个 LLM + 一个 Python 解释器 + 一个能递归 spawn 自己的子例程"。

我们在这个 notebook 里要手写的就是这三个东西。
```

- [ ] **Step 2: §2 markdown**

```markdown
## §2 加载 CAE-MDs 知识库

知识库路径 `/home/juli/RLM/CAE-MDs`，包含 8 篇 markdown：
- 1 本英文专著（Benson 的 ALE/FSI，约 100k 字符）
- 1 篇 thyssenkrupp 的 FRP 水下冲击会议论文（英文）
- 6 篇中文论文/学位论文（水下爆炸、加筋结构破损、LS-DYNA 应用等）

我们把它们读进一个 `dict[paper_id, full_text]`，`paper_id` 就是 stem。
```

- [ ] **Step 3: code cell（加载 + 统计）**

```python
KB_DIR = pathlib.Path("/home/juli/RLM/CAE-MDs")
papers: dict[str, str] = {p.stem: p.read_text(encoding="utf-8") for p in sorted(KB_DIR.glob("*.md"))}

print(f"Loaded {len(papers)} papers:")
for pid, text in papers.items():
    print(f"  - {pid[:70]:70s}  {len(text):>8,} chars")
print(f"\nTotal: {sum(len(t) for t in papers.values()):,} chars")
```

Expected output（实际跑后会拿到 7 个左右非空文件，总约 95 万字符）。

- [ ] **Step 4: code cell（粗略 token 估算）**

```python
def rough_tokens(s: str) -> int:
    """很粗的估算：中文 1 char ≈ 1 token，英文按 4 char/token。"""
    cn = sum(1 for c in s if '一' <= c <= '鿿')
    en = len(s) - cn
    return cn + en // 4

for pid, text in papers.items():
    print(f"  ~{rough_tokens(text):>7,} tok  {pid[:60]}")
print(f"\nTotal ~{sum(rough_tokens(t) for t in papers.values()):,} tokens")
```

读者一眼看到"全语料约 ~30 万 token，单 LLM 一次塞不下"，为下一节做铺垫。

---

### Task 5: §3 反例（直接塞 LLM 会失败）

加 2 个 cell。**故意展示失败/截断**，让读者直观感受 RLM 解决的痛点。

- [ ] **Step 1: markdown**

```markdown
## §3 反例：直接把整个语料塞进 LLM

最 naive 的做法："把所有论文连接起来，问一个问题，让 LLM 一次回答"。

我们故意试一下，看会发生什么——通常是：
- API 提示 `context_length_exceeded`，或
- 调用成功但 LLM 答非所问 / 漏掉细节 / 数字乱编。
```

- [ ] **Step 2: code cell**

```python
question = "在 Benson 关于 ALE/FSI 的论文中，作者主张 fully Lagrangian 与 fully Eulerian 各自的优缺点是什么？"

big_blob = "\n\n=== PAPER ===\n\n".join(f"[{pid}]\n{text}" for pid, text in papers.items())
print(f"Naive prompt size: ~{rough_tokens(big_blob):,} tokens")

try:
    content, usage = chat([
        {"role": "system", "content": "你是 CAE 文献助手，根据下方语料用中文作答。"},
        {"role": "user", "content": question + "\n\n语料：\n" + big_blob},
    ])
    print("--- LLM RESPONSE ---")
    print(content[:1200])
    print(f"\n--- USAGE: {usage}")
except Exception as e:
    print(f"--- FAILED: {type(e).__name__}: {e}")
```

> 预期：要么报 context length 错误，要么模型答得很差/编造。无论哪种都为 §4 的 RLM 价值做开场白。

---

### Task 6: §4 RLM v1（REPL + FINAL + 主循环）

最关键的一节。本任务一次落 5 个 cell：原理 markdown、REPL 类、SystemPrompt、主循环、第一个 demo。

- [ ] **Step 1: markdown（原理详解）**

````markdown
## §4 RLM v1：最小可跑

我们先实现一个**单代理、无递归、无工具**的 RLM。三件事：

### 4.1 REPL

一个能在持久命名空间里 `exec(code, ns, ns)` 的小盒子。我们额外暴露一个
`FINAL(value)` 函数：模型一调它，就把结果存到 `ns["__final__"]`、把
`ns["__done__"]` 置 True，主循环看到就 return。

> 教学版**不做沙箱**——同进程 exec，能 import os。生产里要换 Pyodide / Docker / E2B。

### 4.2 系统提示

告诉模型：你有一个 `context` 变量，它是 `dict[paper_id, full_text]`；
你写 ```` ```repl ... ``` ```` 代码块；写好了用 `FINAL(answer)` 提交。

### 4.3 主循环

```
loop until done or max_steps:
    response = LLM(history)
    code = extract_repl_block(response)
    stdout = repl.exec(code)
    if repl.done: return repl.final
    history.append(model_response)
    history.append(truncated_stdout)
```

就这么三件事。
````

- [ ] **Step 2: code cell（REPL 类）**

```python
@dataclass
class REPL:
    """In-process Python REPL with a persistent namespace and a FINAL() hook."""
    ns: dict = field(default_factory=dict)
    done: bool = False
    final: Any = None
    truncate_len: int = 2000

    def __post_init__(self):
        def FINAL(value):
            self.final = value
            self.done = True
        self.ns["FINAL"] = FINAL

    def execute(self, code: str) -> str:
        """Run code, return captured stdout (truncated to last `truncate_len` chars)."""
        import io, contextlib, traceback
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(code, self.ns, self.ns)
        except Exception:
            buf.write("\n" + traceback.format_exc())
        out = buf.getvalue()
        if len(out) > self.truncate_len:
            out = f"[TRUNCATED: last {self.truncate_len} chars shown]\n...{out[-self.truncate_len:]}"
        elif not out:
            out = "[EMPTY OUTPUT — remember to print() what you want to see]"
        return out
```

- [ ] **Step 3: code cell（System prompt v1）**

```python
SYSTEM_V1 = """\
你是一个有 Python REPL 的助手。

REPL 里已经存在变量：
  - context: dict[paper_id, full_text]    # 知识库
  - FINAL(value)                          # 提交最终答案的函数

写代码时，必须**只用一个**这样的代码块：
```repl
# 你的 Python 代码
print(...)        # print 的内容会回传给你
# 完成时调 FINAL(answer)
```

REPL 输出会被截断到末尾若干字符，所以不要 print 太长内容。
一次轮次只写一个 ```repl``` 块。回答完用 FINAL(...) 提交。
"""
```

- [ ] **Step 4: code cell（主循环 + 抽块工具）**

```python
def extract_repl(text: str) -> str | None:
    m = re.search(r"```repl\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else None

def run_rlm_v1(question: str, context: dict, max_steps: int = 8, verbose: bool = True) -> dict:
    repl = REPL(ns={"context": context})
    # 初始 probe：让 LLM 看到 context 的形态
    probe = (
        f"context type: dict\n"
        f"keys ({len(context)}): {list(context.keys())}\n"
        f"value sizes: {{pid: len for pid, text in context.items()}} → " 
        + str({pid: len(t) for pid, t in context.items()})
    )
    history = [
        {"role": "system", "content": SYSTEM_V1},
        {"role": "user", "content": f"任务：{question}\n\nREPL 初始 probe:\n{probe}"},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for step in range(max_steps):
        content, usage = chat(history)
        for k in total_usage: total_usage[k] += usage[k]
        if verbose: print(f"\n=== Step {step} model says ===\n{content}\n")
        code = extract_repl(content)
        if code is None:
            history.append({"role": "assistant", "content": content})
            history.append({"role": "user", "content": "你没有写 ```repl``` 块。请重写一次完整的代码。"})
            continue
        stdout = repl.execute(code)
        if verbose: print(f"--- Step {step} REPL output ---\n{stdout}\n")
        if repl.done:
            return {"answer": repl.final, "steps": step + 1, "usage": total_usage}
        history.append({"role": "assistant", "content": content})
        history.append({"role": "user", "content": f"REPL output:\n{stdout}"})
    return {"answer": None, "steps": max_steps, "usage": total_usage, "error": "max_steps exceeded"}
```

- [ ] **Step 5: code cell（v1 demo）**

```python
# 用 v1 跑一个"轻量"问题：只问一个文档的事实
q1 = "列出 /home/juli/RLM/CAE-MDs 里所有论文的 paper_id（按字典序）。"
result = run_rlm_v1(q1, papers, max_steps=5, verbose=True)
print("\n=========== FINAL ===========")
print(result["answer"])
print(f"\nsteps={result['steps']}  usage={result['usage']}")
```

> 期望：v1 已经能让模型写 `print(sorted(context.keys()))` → `FINAL(...)` 完成。

---

### Task 7: §5 RLM v2（加 llm_query 单发子代理）

加 4 个 cell。

- [ ] **Step 1: markdown**

````markdown
## §5 RLM v2：加 `llm_query`

v1 只能让模型自己 grep。但语料里有几十万字符，模型自己一行一行截下来读
很慢且容易遗漏——它需要一个能"吃掉一大块文本然后给我抽取结果"的副手。

我们加一个 REPL 函数 `llm_query(prompt) -> str`：**单次 LM 调用，没有 REPL，
没有递归**。模型在 REPL 里像调本地函数一样调它。

```repl
fragment = context["xxx.md"][:30000]
ans = llm_query(f"从下面的论文片段里抽取作者主张的两种方法的优缺点：\n\n{fragment}")
print(ans)
```

注意 `llm_query` 不会自动看到外层 REPL 的变量——它是一个完全独立的 LM 调用。
````

- [ ] **Step 2: code cell（扩展 REPL）**

```python
@dataclass
class REPLv2(REPL):
    """v2: add llm_query into the REPL namespace."""
    def __post_init__(self):
        super().__post_init__()
        def llm_query(prompt: str) -> str:
            content, _ = chat([{"role": "user", "content": prompt}])
            return content
        self.ns["llm_query"] = llm_query
```

- [ ] **Step 3: code cell（v2 system prompt + 主循环）**

```python
SYSTEM_V2 = SYSTEM_V1 + """\

新增工具：
  - llm_query(prompt: str) -> str
        单次 LM 调用（无 REPL、无递归）。用法：把"一段文本 + 一个问题"塞给它，
        拿回字符串答案。适合从一大段文本里抽事实、做总结、做翻译。
        它看不到外层 REPL 的变量；你必须把要给它看的内容直接拼进 prompt。
"""

def run_rlm_v2(question, context, max_steps=10, verbose=True):
    repl = REPLv2(ns={"context": context})
    probe = f"context: dict, keys={list(context.keys())}, sizes={{pid: len(t) for pid,t in context.items()}}"
    history = [
        {"role": "system", "content": SYSTEM_V2},
        {"role": "user", "content": f"任务：{question}\n\n初始 probe:\n{probe}"},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for step in range(max_steps):
        content, usage = chat(history)
        for k in total_usage: total_usage[k] += usage[k]
        if verbose: print(f"\n=== v2 Step {step} ===\n{content}\n")
        code = extract_repl(content)
        if code is None:
            history += [{"role": "assistant", "content": content},
                        {"role": "user", "content": "请写一个 ```repl``` 块。"}]
            continue
        stdout = repl.execute(code)
        if verbose: print(f"--- REPL ---\n{stdout}\n")
        if repl.done:
            return {"answer": repl.final, "steps": step + 1, "usage": total_usage}
        history += [{"role": "assistant", "content": content},
                    {"role": "user", "content": f"REPL output:\n{stdout}"}]
    return {"answer": None, "steps": max_steps, "usage": total_usage, "error": "max_steps"}
```

- [ ] **Step 4: code cell（v2 demo——做真实抽取）**

```python
q2 = "oezarmut 那篇关于 FRP 水下冲击的会议论文里，作者用了什么仿真软件？哪一节给出仿真设置？"
result = run_rlm_v2(q2, papers, max_steps=8, verbose=True)
print("\n=========== FINAL ===========")
print(result["answer"])
print(f"steps={result['steps']}  usage={result['usage']}")
```

> 期望：v2 先 `len(context['oezarmut...'])` 看大小、再 `llm_query` 喂全文，
> 拿回结构化抽取后 `FINAL(...)`。

---

### Task 8: §6 RLM v3（加 rlm_query 递归子代理）

加 4 个 cell。这是"R"in RLM 的关键。

- [ ] **Step 1: markdown**

````markdown
## §6 RLM v3：加 `rlm_query` —— 真正的"R"

`llm_query` 是**单发**的：你给它一个 prompt，它给你一个答案，无中间步骤。
有时候子问题本身又是个"需要 REPL+迭代才能解决"的小 RLM 任务。比如：

> "从这两篇 100k 字符的论文里，比较它们在数值方法和实验对比节的差异"

子问题太复杂、单发回答不行——这时父代理需要 **派生一个有自己 REPL 的子 RLM**。
我们加 `rlm_query(prompt) -> str`，它就是**递归调用自己**，但深度受 `MAX_DEPTH`
约束（避免无限递归）。

到达最大深度时，`rlm_query` 退化为 `llm_query`。
````

- [ ] **Step 2: code cell（实现 v3 — 重构 run_rlm 接收 depth）**

```python
MAX_DEPTH = 2  # depth=0 是根，depth=1 是第一层子代理，到 MAX_DEPTH 这层禁止再递归

SYSTEM_V3 = SYSTEM_V2 + """\

新增工具：
  - rlm_query(prompt: str) -> str
        派生一个**有自己 REPL 的子 RLM**来解决子任务。比 llm_query 更慢但更强。
        子 RLM 不会自动看到你的 REPL 变量；要给它的内容直接写进 prompt。
        到达最大递归深度时此函数会自动退化为 llm_query。

何时用哪个：
  - llm_query：抽事实、总结、翻译、判断、单步分类
  - rlm_query：子任务本身需要多步推理、需要 REPL、需要再次分而治之
"""

def run_rlm(question, context, depth=0, max_steps=10, max_depth=MAX_DEPTH, verbose=True):
    """RLM v3: 支持递归 rlm_query。"""
    # depth==max_depth 时还是允许跑一轮 REPL（不是直接退化为 llm），只是禁止再 rlm_query
    is_leaf = depth >= max_depth

    repl = REPLv2(ns={"context": context})
    def llm_query_in_repl(prompt: str) -> str:
        content, _ = chat([{"role": "user", "content": prompt}])
        return content
    repl.ns["llm_query"] = llm_query_in_repl

    def rlm_query_in_repl(prompt: str) -> str:
        if is_leaf:
            # 到达最大深度，退化
            return llm_query_in_repl(prompt)
        sub_result = run_rlm(
            question=prompt, context=context, depth=depth + 1,
            max_steps=max_steps, max_depth=max_depth, verbose=False,
        )
        return str(sub_result.get("answer") or sub_result.get("error", "<no answer>"))
    repl.ns["rlm_query"] = rlm_query_in_repl

    probe = f"context: dict, keys={list(context.keys())}, depth={depth}/{max_depth}"
    sys_prompt = SYSTEM_V3 if not is_leaf else SYSTEM_V2  # 叶节点不告诉它 rlm_query
    history = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"任务：{question}\n\n初始 probe:\n{probe}"},
    ]
    indent = "  " * depth
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for step in range(max_steps):
        content, usage = chat(history)
        for k in total_usage: total_usage[k] += usage[k]
        if verbose: print(f"\n{indent}=== depth={depth} step={step} ===\n{textwrap.indent(content, indent)}\n")
        code = extract_repl(content)
        if code is None:
            history += [{"role": "assistant", "content": content},
                        {"role": "user", "content": "请写一个 ```repl``` 块。"}]
            continue
        stdout = repl.execute(code)
        if verbose: print(f"{indent}--- REPL ---\n{textwrap.indent(stdout, indent)}\n")
        if repl.done:
            return {"answer": repl.final, "steps": step + 1, "usage": total_usage, "depth": depth}
        history += [{"role": "assistant", "content": content},
                    {"role": "user", "content": f"REPL output:\n{stdout}"}]
    return {"answer": None, "steps": max_steps, "usage": total_usage, "depth": depth, "error": "max_steps"}
```

- [ ] **Step 3: code cell（v3 demo——递归比较两篇论文）**

```python
q3 = "比较 Benson 的 ALE/FSI 综述和 oezarmut 关于 FRP 水下冲击的论文：它们各自的研究问题是什么、用了什么仿真方法？"
result = run_rlm(q3, papers, max_steps=10, max_depth=2, verbose=True)
print("\n=========== FINAL ===========")
print(result["answer"])
print(f"steps={result['steps']}  usage={result['usage']}")
```

> 期望：根代理会 `rlm_query` 一次问 Benson、再 `rlm_query` 一次问 oezarmut，
> 子代理各自跑一遍 REPL 抽出信息，根代理拼出对比。

- [ ] **Step 4: markdown（思考：为什么不让父代理自己看子代理结果？）**

```markdown
### 一个关键设计决定

注意：`rlm_query` 的返回值是子代理的**最终字符串答案**，
而不是子代理 REPL 里的中间状态。父代理只看到一个字符串。

这个"信息瓶颈"是 RLM 论文的核心 insight：子代理可能读了 50k 字符才得出
3 句话的结论；如果把那 50k 字符全塞回父代理的 history，父代理上下文窗口就
炸了。**用变量隔离上下文**是 RLM 能处理超大语料的根本原因。

如果你想要更精细的协议（比如让父代理拿到子代理的中间变量），那就开始走向
"agent framework"了，不再是教科书的 RLM。
```

---

### Task 9: §7 RLM v4（加 search_kb 工具）

加 4 个 cell。

- [ ] **Step 1: markdown**

````markdown
## §7 RLM v4：加 `search_kb` 关键词工具

模型当前只能 `context["..."][:30000]` 这样硬切。对 CAE 知识库来说，
更聪明的是先关键词搜索，定位到哪些论文/哪些片段相关，再去精读。

我们暴露 `search_kb(keywords: list[str], top_k=5) -> list[dict]`：
对所有论文做不区分大小写的子串匹配，按命中次数排序，返回片段。
````

- [ ] **Step 2: code cell（search_kb 实现）**

```python
def build_search_kb(papers: dict[str, str]):
    lowered = {pid: text.lower() for pid, text in papers.items()}

    def search_kb(keywords: list[str], top_k: int = 5, snippet_chars: int = 400) -> list[dict]:
        """关键词子串搜索。返回 [{paper_id, score, hits, snippet}]。"""
        kws = [k.lower() for k in keywords if k]
        if not kws: return []
        scored = []
        for pid, low in lowered.items():
            hits, first = {}, None
            for kw in kws:
                c = low.count(kw)
                if c > 0:
                    hits[kw] = c
                    pos = low.find(kw)
                    if first is None or pos < first: first = pos
            if hits:
                start = max(0, (first or 0) - snippet_chars // 2)
                end = min(len(papers[pid]), (first or 0) + snippet_chars // 2)
                snippet = papers[pid][start:end].replace("\n", " ")
                scored.append({"paper_id": pid, "score": sum(hits.values()), "hits": hits, "snippet": snippet})
        scored.sort(key=lambda r: -r["score"])
        return scored[:top_k]

    return search_kb

search_kb = build_search_kb(papers)
# 自测
print(json.dumps(search_kb(["LS-DYNA", "ALE"], top_k=3), ensure_ascii=False, indent=2)[:500])
```

- [ ] **Step 3: code cell（v4 主循环 + system prompt 注入工具）**

```python
SYSTEM_V4 = SYSTEM_V3 + """\

新增工具：
  - search_kb(keywords: list[str], top_k=5) -> list[dict]
        在所有论文里做关键词子串搜索，返回 [{paper_id, score, hits, snippet}]。
        在喂全文给 llm_query 之前先用 search_kb 缩小范围，可以省大量 token。
        多语言知识库时多给些英文 + 中文同义词。
"""

def run_rlm_v4(question, context, depth=0, max_steps=10, max_depth=2, verbose=True):
    is_leaf = depth >= max_depth
    repl = REPLv2(ns={"context": context})
    repl.ns["llm_query"] = lambda p: chat([{"role": "user", "content": p}])[0]
    def rlm_query_in_repl(prompt: str) -> str:
        if is_leaf: return repl.ns["llm_query"](prompt)
        sub = run_rlm_v4(prompt, context, depth+1, max_steps, max_depth, verbose=False)
        return str(sub.get("answer") or sub.get("error", "<no answer>"))
    repl.ns["rlm_query"] = rlm_query_in_repl
    repl.ns["search_kb"] = search_kb  # 共享同一个闭包

    probe = f"context: dict, keys={list(context.keys())}, depth={depth}/{max_depth}"
    sys_prompt = SYSTEM_V4 if not is_leaf else SYSTEM_V2
    history = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"任务：{question}\n\n初始 probe:\n{probe}"},
    ]
    indent = "  " * depth
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for step in range(max_steps):
        content, usage = chat(history)
        for k in total_usage: total_usage[k] += usage[k]
        if verbose: print(f"\n{indent}=== d={depth} s={step} ===\n{textwrap.indent(content, indent)}\n")
        code = extract_repl(content)
        if code is None:
            history += [{"role":"assistant","content":content},{"role":"user","content":"请写 ```repl``` 块。"}]
            continue
        stdout = repl.execute(code)
        if verbose: print(f"{indent}--- REPL ---\n{textwrap.indent(stdout, indent)}\n")
        if repl.done:
            return {"answer": repl.final, "steps": step+1, "usage": total_usage, "depth": depth}
        history += [{"role":"assistant","content":content},{"role":"user","content":f"REPL output:\n{stdout}"}]
    return {"answer": None, "steps": max_steps, "usage": total_usage, "depth": depth, "error": "max_steps"}
```

- [ ] **Step 4: code cell（v4 demo）**

```python
q4 = "知识库里有几篇论文涉及 LS-DYNA？分别是关于什么的？"
result = run_rlm_v4(q4, papers, max_steps=8, max_depth=2, verbose=True)
print("\n=========== FINAL ===========")
print(result["answer"])
print(f"steps={result['steps']}  usage={result['usage']}")
```

> 期望：模型第一步就 `search_kb(["LS-DYNA","ls-dyna"])`，根据 hits 决定哪几篇值得看。

---

### Task 10: §8 端到端实战 + §9 思考题 + 局限

加 3 个 cell。

- [ ] **Step 1: markdown**

````markdown
## §8 端到端实战 Q&A

下面跑两个"非平凡"的问题，观察 RLM 是怎么用 search_kb + llm_query + rlm_query
组合出答案的。
````

- [ ] **Step 2: code cell（两个实战问题）**

```python
real_questions = [
    "比较 Benson 的 ALE/FSI 综述和'PhD 基于通用程序的水下爆炸及其对结构作用的数值模拟研究'两篇文献：它们对'流固耦合'的处理思路有何异同？请用中文作答，并标出 paper_id。",
    "知识库里关于'加筋结构在水中接触爆炸'的研究，作者主要关注哪几个参数？这些参数对破口面积/形状的影响是什么？",
]

for q in real_questions:
    print("\n" + "="*80)
    print(f"Q: {q}")
    print("="*80)
    t0 = time.time()
    result = run_rlm_v4(q, papers, max_steps=12, max_depth=2, verbose=True)
    dt = time.time() - t0
    print(f"\n>>> 答案：\n{result['answer']}\n")
    print(f">>> steps={result['steps']}  usage={result['usage']}  time={dt:.1f}s")
```

- [ ] **Step 3: markdown（局限 + 思考题）**

````markdown
## §9 这个教学版 RLM 的局限 & 思考题

### 当前局限（按"如果你想做生产"排序）

1. **同进程 `exec()`** — LLM 写的 Python 没有任何沙箱。生产里换 Pyodide(fast-rlm) / Docker / E2B。
2. **无预算硬截断** — 只有 `max_steps`/`max_depth`。生产里要按 token / 美元封顶。
3. **`llm_query` / `rlm_query` 同步阻塞** — 实战会想 batched + 并行（`asyncio.gather` / ThreadPool）。
4. **无 schema 校验** — `FINAL("英文")` 也会通过。生产里加 Pydantic / JSON Schema。
5. **无历史压缩** — 长任务会越跑 history 越长。生产里加 compaction（参 rlms.RLM `compaction=True`）。
6. **search_kb 太弱** — 只是子串。换成 BM25 / embedding 检索会更强。

### 思考题

1. 在 §6 v3 demo 里观察根代理是否真的用了 `rlm_query`？如果它直接用 `llm_query` 就完成了任务，说明你给的问题"不够深"——尝试设计一个一定需要递归才能答出来的问题。
2. 把 `MAX_DEPTH=1` 改为 `MAX_DEPTH=3`，对同一个问题观察 token 使用量和回答质量的变化。
3. 试着替换 `search_kb` 为 embedding 检索（用 `text-embedding-3-small` 或同等模型），观察工具变强后模型行为如何变化。
4. 给主循环加 `max_money_spent` 美元预算（每次 chat 估一个 cost，超就抛错），体验 fast-rlm 的"多维硬限"是怎么用的。

至此，你应当：
- 能解释 RLM = LLM + REPL + 递归子代理 的具体含义
- 能看着 fast-rlm 或 rlms 的源码找到本 notebook 的每个对应位置
- 知道在自己的问题上需要往哪些方向扩展
````

---

### Task 11: 端到端 smoke test（执行者必须跑过）

**Files:** 不修改，只验证已写好的 notebook 能跑通。

- [ ] **Step 1: 用 nbformat 检查结构**

```bash
python3 - <<'PY'
import nbformat
nb = nbformat.read("/home/juli/RLM/rlm-tutorial/rlm_tutorial.ipynb", as_version=4)
print("cells:", len(nb.cells))
for i, c in enumerate(nb.cells):
    head = (c.source.splitlines()[0] if c.source else "")[:80]
    print(f"  [{i:2d}] {c.cell_type:8s}  {head}")
PY
```

Expected: 输出约 22 个 cell（markdown + code 交替），首 cell 是 `# 从零实现 RLM` 标题。

- [ ] **Step 2: 跑 §0 + §2 + §3 + §4 demo（快速烟雾，跳过 reasoning 长任务）**

转成 .py 后 exec，或用 `jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=120` 跑前 N 个 cell：

```bash
python3 - <<'PY'
import nbformat
from nbclient import NotebookClient
nb = nbformat.read("/home/juli/RLM/rlm-tutorial/rlm_tutorial.ipynb", as_version=4)
# 只跑前 8 个 cell（§0-§4 主体）做快速烟雾
nb.cells = nb.cells[:8]
client = NotebookClient(nb, timeout=180, kernel_name="python3")
client.execute()
print("OK: first 8 cells ran")
PY
```

> 这一步需要 `pip install nbclient ipykernel`，且 `python3 -m ipykernel install --user --name python3` 注册 kernel；如果 lab 已经能用，应该已就绪。
>
> 不要跑全部 cell——v3/v4 demo 会真的递归调 LLM，单次可能几十秒到几分钟，烟雾测试不该 block。
>
> 期望：无 exception 抛出；最后一句 `OK: first 8 cells ran`。

- [ ] **Step 3: 提交**

```bash
cd /home/juli/RLM
git add rlm-tutorial/rlm_tutorial.ipynb
git status
git commit -m "feat(tutorial): write runnable RLM tutorial notebook (v1→v4)"
```

---

## 3. 风险

1. **API 兼容性**：dubrify.com 是 OpenRouter / 自建代理之类的中转。它对 `extra_body`、`temperature`、`max_tokens` 的处理可能与 OpenAI native 不一致。Task 1 step 7 的探测**必须执行**并据此决定 `LLM_KWARGS`，否则后续 cell 都会爆。
2. **DeepSeek-v4-flash 是 reasoning model**：默认会想很久——RLM 的迭代循环里如果每步等 30 秒，5 步就 150 秒。需要 `extra_body={"thinking":{"type":"disabled"}}`；如果 dubrify 不识别，可以试 `reasoning_effort=` 或干脆换非 reasoning 模型。
3. **同进程 `exec()` 的安全**：模型如果开始 `import shutil; shutil.rmtree(...)` 就会真的删文件。Notebook 在 §4 markdown 已警告，但执行者还是要在自己机器上跑、不要让别人远程跑这个 notebook。
4. **极长论文（Benson, 100k+ chars）单次 `llm_query` 喂全文**：dubrify 后端的实际 context window 未知；如果 `llm_query` 抛 context length error，模型会拿到错误字符串，可能不会自我修正。烟雾测试无法捕获这个，留作真问答时观察。
5. **`max_depth=2`** 在 v3 demo 里如果模型选择不调 `rlm_query`，演示效果会差。准备一个"一定需要递归"的备用问题（"两两对比 8 篇论文的方法"之类）放在 §8 思考题里。

---

## 4. Self-Review

- 规格覆盖：用户要求"jupyter notebook + RLM 算法 + CAE-MDs 问答 + 可实际运行" → 全部映射到 Task 3-10；Task 11 烟雾测试保证"可运行"。✅
- 占位符扫描：无 TBD/TODO；每个 step 都有具体代码或具体命令。✅
- 类型一致：`REPL` → `REPLv2` 继承；`run_rlm_v1/v2/v4` 命名一致；`run_rlm` 在 v3 这个版本里改名为 `run_rlm`（无版本号）然后 v4 又叫 `run_rlm_v4`——**这是潜在混乱**。修正：所有版本统一带后缀 `_v{N}`，§6 那个改为 `run_rlm_v3`。在 Task 8 step 2 已用 `run_rlm_v4`，Task 8 step 3 demo 也用 `run_rlm_v4`。Task 8 step 2 函数名"`run_rlm`"→ 应改回 "`run_rlm_v3`" 保持后缀一致。
- 引用了上一份对比报告 §0.3，作为设计选择的依据，便于读者交叉跳读。
- 没有把 API key 写进任何 git 追踪文件。✅

> **修正记录**：Task 8 step 2 的函数定义改为 `def run_rlm_v3(...)`；step 3 demo 改为 `run_rlm_v3(q3, ...)`；这样 v1 → v2 → v3 → v4 命名一致。执行时请按此校正。
