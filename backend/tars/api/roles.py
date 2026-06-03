"""角色模板 REST API — v4.0.2."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..gateway import role_template as _rt_module
from ..gateway.role_template import RoleTemplate as RoleTemplateModel
from ..security.audit import safe_audit, client_ip_from_request
from ._auth import Principal, require_admin

router = APIRouter(prefix="/api/roles", tags=["roles"])


def _mgr():
    m = _rt_module.role_template_manager
    if not m:
        raise HTTPException(status_code=503, detail="Role template manager not initialized")
    return m


def _template_to_dict(t: RoleTemplateModel) -> dict:
    return {
        "id": t.id, "name": t.name, "description": t.description,
        "is_builtin": t.is_builtin, "allowed_tools": t.allowed_tools,
        "denied_tools": t.denied_tools, "allowed_modules": t.allowed_modules,
        "workspace_restriction": t.workspace_restriction,
        "max_concurrent": t.max_concurrent,
        "created_at": t.created_at, "updated_at": t.updated_at,
    }


@router.get("")
def list_roles():
    return [_template_to_dict(t) for t in _mgr().list_templates()]


@router.get("/{role_id}")
def get_role(role_id: str):
    t = _mgr().get_template(role_id)
    if not t:
        raise HTTPException(status_code=404, detail="角色模板不存在")
    return _template_to_dict(t)


class CreateRoleRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    allowed_tools: list[str] = []
    denied_tools: list[str] = []
    allowed_modules: list[str] = []
    max_concurrent: int = 1
    workspace_restriction: bool = True


@router.post("")
def create_role(
    body: CreateRoleRequest,
    http_request: Request,
    principal: Principal = Depends(require_admin),
):
    if _mgr().get_template(body.id):
        raise HTTPException(status_code=409, detail="角色 ID 已存在")
    t = _mgr().create_template(
        id=body.id, name=body.name, description=body.description,
        allowed_tools=body.allowed_tools, denied_tools=body.denied_tools,
        allowed_modules=body.allowed_modules, max_concurrent=body.max_concurrent,
        workspace_restriction=body.workspace_restriction,
    )
    from ..org import ORG_ID

    safe_audit(
        lambda lg: lg.log_config_change(
            resource_id=f"role:{body.id}",
            tenant_id=ORG_ID,
            user_id=principal.user_id,
            detail=f"action=role_create,name={body.name}",
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True, "template": _template_to_dict(t)}


@router.put("/{role_id}")
def update_role(
    role_id: str,
    body: dict,
    http_request: Request,
    principal: Principal = Depends(require_admin),
):
    ok = _mgr().update_template(role_id, **body)
    if not ok:
        raise HTTPException(status_code=400, detail="更新失败（预置模板不可修改或模板不存在）")
    from ..org import ORG_ID

    safe_audit(
        lambda lg: lg.log_config_change(
            resource_id=f"role:{role_id}",
            tenant_id=ORG_ID,
            user_id=principal.user_id,
            detail="action=role_update",
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True, "template": _template_to_dict(_mgr().get_template(role_id))}


@router.delete("/{role_id}")
def delete_role(
    role_id: str,
    http_request: Request,
    principal: Principal = Depends(require_admin),
):
    ok = _mgr().delete_template(role_id)
    if not ok:
        raise HTTPException(status_code=400, detail="删除失败（预置模板不可删除或模板不存在）")
    from ..org import ORG_ID

    safe_audit(
        lambda lg: lg.log_config_change(
            resource_id=f"role:{role_id}",
            tenant_id=ORG_ID,
            user_id=principal.user_id,
            detail="action=role_delete",
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True}


# ── 用户角色分配 ──────────────────────────────────────────

_user_store = None


def init_roles_api(user_store):
    global _user_store
    _user_store = user_store


class AssignRoleRequest(BaseModel):
    role_template_id: str


@router.post("/users/{user_id}/role")
def assign_user_role(
    user_id: str,
    body: AssignRoleRequest,
    http_request: Request,
    principal: Principal = Depends(require_admin),
):
    if not _user_store:
        raise HTTPException(status_code=503)
    t = _mgr().get_template(body.role_template_id)
    if not t:
        raise HTTPException(status_code=404, detail="角色模板不存在")
    from ..gateway.permission import UserRole
    role_map = {"admin": UserRole.ADMIN, "readonly": UserRole.GUEST, "presales_manager": UserRole.USER}
    user_role = role_map.get(body.role_template_id, UserRole.USER)
    _user_store.update_user(user_id, role=user_role, role_template_id=body.role_template_id)
    from ..org import ORG_ID

    safe_audit(
        lambda lg: lg.log_user_event(
            action="user_update",
            target_user_id=user_id,
            actor_id=principal.user_id,
            tenant_id=ORG_ID,
            detail=f"role_template_id={body.role_template_id}",
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {"success": True, "user_id": user_id, "role_template_id": body.role_template_id}


@router.get("/users/{user_id}/permissions")
def get_user_permissions(user_id: str):
    if not _user_store:
        raise HTTPException(status_code=503)
    user = _user_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    template_id = getattr(user, "role_template_id", None) or _role_to_template(getattr(user, "role", None))
    return _mgr().get_user_permissions(template_id)


def _role_to_template(role) -> str:
    if role is None:
        return "standard"
    role_val = role.value if hasattr(role, "value") else str(role)
    return {"admin": "admin", "user": "standard", "guest": "readonly", "presales_manager": "presales_manager"}.get(role_val, "standard")
