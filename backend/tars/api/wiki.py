from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from tars.wiki.store import WikiStore
from tars.api._auth import require_authenticated_user, Principal


class PageUpdateRequest(BaseModel):
    content: str


def create_wiki_router(store: WikiStore, db=None) -> APIRouter:
    router = APIRouter(tags=["wiki"])

    @router.get("/")
    def list_pages():
        pages = store.list_pages()
        return {"pages": [{"name": p, "url": f"/api/wiki/{p}"} for p in sorted(pages)]}

    @router.get("/search")
    def search_pages(q: str = Query(...), top_k: int = Query(5, ge=1, le=20)):
        results = store.search(q, top_k=top_k)
        return {"query": q, "results": results}

    @router.get("/{page_name}/sources")
    def get_page_sources(page_name: str):
        """反向链接：返回该 wiki 页升格自哪些源记忆。"""
        if db is None:
            raise HTTPException(status_code=501, detail="wiki source links not available")
        meta = db.get_wiki_page_meta(page_name)
        if meta is None:
            return {"page_name": page_name, "source_memory_ids": [], "sources": []}
        sources = []
        for mid in meta.get("source_memory_ids", []):
            mem = None
            try:
                mem = db.get_memory(mid)
            except Exception:
                mem = None
            sources.append({
                "memory_id": mid,
                "exists": mem is not None,
                "category": getattr(mem, "category", None) if mem else None,
                "content": getattr(mem, "content", None) if mem else None,
            })
        return {
            "page_name": page_name,
            "title": meta.get("title"),
            "source_type": meta.get("source_type"),
            "source_memory_ids": meta.get("source_memory_ids", []),
            "sources": sources,
        }

    @router.get("/{page_name}")
    def get_page(page_name: str):
        if page_name == "index":
            return {"content": store.read_index()}
        content = store.read_page(page_name)
        if content is None:
            raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")
        return {"name": page_name, "content": content}

    @router.put("/{page_name}")
    def update_page(page_name: str, req: PageUpdateRequest, principal: Principal = Depends(require_authenticated_user)):
        store.write_page(page_name, req.content)
        return {"success": True, "name": page_name}

    @router.delete("/{page_name}")
    def delete_page(page_name: str, principal: Principal = Depends(require_authenticated_user)):
        if store.read_page(page_name) is None:
            raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")
        store.delete_page(page_name)
        return {"success": True}

    return router
