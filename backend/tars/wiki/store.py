import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tars.memory.deduplicator import cosine_similarity


class WikiStore:
    def __init__(self, wiki_dir: Path, embedding_provider=None):
        self.wiki_dir = Path(wiki_dir)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self._embedding_provider = embedding_provider
        self._embeddings: Dict[str, List[float]] = {}
        index_path = self.wiki_dir / "index.md"
        if not index_path.exists():
            index_path.write_text("# Wiki Index\n\n", encoding="utf-8")

    @property
    def has_search(self) -> bool:
        return self._embedding_provider is not None

    def read_page(self, page_name: str) -> Optional[str]:
        path = self.wiki_dir / f"{page_name}.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def write_page(self, page_name: str, content: str) -> None:
        path = self.wiki_dir / f"{page_name}.md"
        path.write_text(content, encoding="utf-8")
        self._update_page_embedding(page_name, content)

    def delete_page(self, page_name: str) -> None:
        path = self.wiki_dir / f"{page_name}.md"
        if path.exists(): path.unlink()
        self._embeddings.pop(page_name, None)

    def list_pages(self) -> list[str]:
        return [p.stem for p in self.wiki_dir.glob("*.md") if p.stem != "index"]

    def read_index(self) -> str:
        return (self.wiki_dir / "index.md").read_text(encoding="utf-8")

    def update_index(self, summaries: dict[str, str]) -> None:
        lines = ["# Wiki Index\n"]
        for page_name, summary in sorted(summaries.items()):
            lines.append(f"- **[{page_name}]({page_name}.md)** — {summary}")
        (self.wiki_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        pages = self.list_pages()
        if not pages: return []
        if self._embedding_provider and self._embeddings:
            return self._vector_search(query, pages, top_k)
        return self._keyword_search(query, pages, top_k)

    def _vector_search(self, query: str, pages: List[str], top_k: int) -> List[Dict[str, Any]]:
        try:
            q_vec = self._embedding_provider.encode([query])[0]
        except Exception:
            return self._keyword_search(query, pages, top_k)
        ql = query.lower()
        tokens = [t for t in re.split(r"\s+", ql) if len(t) >= 2]
        scored = []
        for name in pages:
            vec = self._embeddings.get(name)
            if vec is None:
                c = self.read_page(name)
                if c and self._embedding_provider:
                    try:
                        vec = self._embedding_provider.encode([c])[0]
                        self._embeddings[name] = vec
                    except Exception: pass
            score = cosine_similarity(q_vec, vec) if vec else 0.0
            cl = (self.read_page(name) or "").lower()
            if ql in cl: score = max(score, 0.55)
            for t in tokens:
                if t in cl: score = max(score, 0.45)
            if score > 0: scored.append((score, name))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"page_name": n, "snippet": (self.read_page(n) or "")[:300], "score": round(s, 4), "content": self.read_page(n) or ""} for s, n in scored[:top_k]]

    def _keyword_search(self, query: str, pages: List[str], top_k: int) -> List[Dict[str, Any]]:
        ql = query.lower()
        tokens = [t for t in re.split(r"\s+", ql) if len(t) >= 2]
        scored = []
        for name in pages:
            cl = (self.read_page(name) or "").lower()
            score = 1.0 if ql in cl else (sum(1 for t in tokens if t in cl) / max(len(tokens), 1) * 0.8) if tokens else 0
            if score > 0: scored.append((score, name))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"page_name": n, "snippet": (self.read_page(n) or "")[:300], "score": round(s, 4), "content": self.read_page(n) or ""} for s, n in scored[:top_k]]

    def _update_page_embedding(self, page_name: str, content: str) -> None:
        if self._embedding_provider is None: return
        try:
            vecs = self._embedding_provider.encode([content])
            if vecs: self._embeddings[page_name] = vecs[0]
        except Exception: pass
