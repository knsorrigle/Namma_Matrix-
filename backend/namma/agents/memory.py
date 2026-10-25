"""Memory stream in the style of Generative Agents (Park et al., 2023).

Retrieval scores each memory by recency, importance and word overlap with the
current situation. No embeddings yet: keyword overlap is cheap and explainable.
Swap in a vector store later if retrieval quality needs it.
"""

from __future__ import annotations

import re

from ..contracts import MemoryItem

_WORD = re.compile(r"[a-z]+")
_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "my", "is", "it", "i", "for", "at", "by", "this", "that"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


class MemoryStream:
    def __init__(self, decay: float = 0.95):
        self.items: list[MemoryItem] = []
        self.decay = decay
        self.importance_since_reflection = 0

    def add(self, tick: int, kind: str, text: str, importance: int) -> MemoryItem:
        item = MemoryItem(tick=tick, kind=kind, text=text, importance=max(1, min(10, importance)))
        self.items.append(item)
        if kind != "reflection":
            self.importance_since_reflection += item.importance
        return item

    def retrieve(self, query: str, now: int, k: int = 5) -> list[MemoryItem]:
        q = _words(query)

        def score(m: MemoryItem) -> float:
            recency = self.decay ** max(0, now - m.tick)
            relevance = len(q & _words(m.text)) / (len(q) or 1)
            return recency + m.importance / 10 + relevance

        best = sorted(self.items, key=score, reverse=True)[:k]
        return sorted(best, key=lambda m: m.tick)

    def recent(self, n: int = 20) -> list[MemoryItem]:
        return self.items[-n:]
