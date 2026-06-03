from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from tars.wiki.store import WikiStore
from tars.api._auth import require_authenticated_user, Principal


class PageUpdateRequest(BaseModel):
    content: str


def create_wiki_router(store: WikiStore) -> APIRouter:
    router = APIRouter(tags=["wiki"])

    @router.get("/")
    def list_pages(principal: Principal = Depends(require_authenticated_user)):
        pages = store.list_pages()
        return {
            "pages": [
                {"name": p, "url": f"/api/wiki/{p}"}
                for p in sorted(pages)
            ]
        }

    @router.get("/{page_name}")
    def get_page(page_name: str, principal: Principal = Depends(require_authenticated_user)):
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
