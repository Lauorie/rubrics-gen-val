"""Generate grounded answers from retrieved chunks with deepseek-v4-flash."""
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是 CAE / 工程仿真领域专家。请严格依据下面提供的资料回答用户问题。"
    "只能使用资料中的信息，不得编造；若资料不足以回答，请明确说明资料中没有相关内容。"
    "回答使用中文，准确、聚焦，保留关键公式、数值与对比。"
)


def build_prompt(question: str, chunks: list[dict]) -> tuple[str, str]:
    """Return (system, user). user embeds the retrieved context + the question."""
    blocks = []
    for i, c in enumerate(chunks, 1):
        blocks.append(f"【资料{i} | 来源:{c['doc']}】\n{c['text']}")
    context = "\n\n".join(blocks)
    user = f"以下是检索到的资料：\n\n{context}\n\n----\n问题：{question}\n\n请基于以上资料作答。"
    return SYSTEM_PROMPT, user


def generate_answer(client: Any, question: str, chunks: list[dict], model: str,
                    temperature: float = 0.0) -> str:
    """Call the generation model and return the stripped answer text."""
    system, user = build_prompt(question, chunks)
    resp = client.chat.completions.create(
        model=model, temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content.strip()


def generate_all(client: Any, items: list[dict], retriever: Any, model: str,
                 temperature: float = 0.0, max_workers: int = 8) -> list[dict]:
    """items: [{item_idx, question}]. Returns [{item_idx, answer, retrieved}] sorted by item_idx."""
    def _one(item: dict) -> dict:
        try:
            chunks = retriever.retrieve(item["question"])
            answer = generate_answer(client, item["question"], chunks, model, temperature)
            return {"item_idx": item["item_idx"], "answer": answer,
                    "retrieved": [c["chunk_id"] for c in chunks]}
        except Exception as e:  # noqa: BLE001 - record per-item failure, keep going
            logger.error("item %s failed: %s", item["item_idx"], e)
            return {"item_idx": item["item_idx"], "answer": "", "error": str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_one, items))
    results.sort(key=lambda r: r["item_idx"])
    return results
