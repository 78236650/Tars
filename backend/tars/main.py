from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import uvicorn
import os
import asyncio
import json
import traceback
import yaml

# 导入 TARS 模块
from tars.channels import ConnectionManager
from tars.agent.agent import AgentV2
from tars.database import Database, UserStore
from tars.gateway.permission import PermissionManager, UserRole
from tars.evolution import EvolutionManager
from tars.scheduler import init_scheduler, shutdown_scheduler, get_scheduler
from tars.models.config import router as model_config_router
from tars.models import load_providers_from_config

# v4.0.0: Module Registry & Skill Curator
from tars.modules.registry import module_registry
from tars.skills.curator import init_skill_curator

# 新的工具/技能/SkillHub 系统
from tars.tools import registry as tool_registry
from tars.tools.builtin import (
    WeatherTool, FileTool, FileListTool, CommandTool, MemoryTool, CronJobTool,
    FileWriteTool, ShellTool, ProcessTool, NetworkTool, MeetingRecognizerTool,
)
from tars.tools.builtin.web_search import WebSearchTool
from tars.tools.builtin.web_fetch import WebFetchTool
from tars.tools.builtin.python_exec import PythonExecTool
from tars.memory.archival_insert_tool import ArchivalInsertTool
from tars.tools.sandbox import WorkspaceSandbox
from tars.skills import skill_registry, SkillLoader, PipelineLoader, SkillPipelineEngine, SkillPipelineRegistry
from tars.skillhub import SkillHubClient, SkillInstaller, LocalSkillCatalog, SkillsShClient
from tars.config.skills import skills_config
from tars.files import FileStorage, FileParser
from tars.orchestration import TaskPlannerTool, TaskExecutor
from tars.api.tools import router as tools_router
from tars.api.skills import router as skills_router, init_skills_api
from tars.api.skillhub import router as skillhub_router, init_skillhub_api
from tars.api.files import router as files_router, init_file_storage
from tars.api.sessions import router as sessions_router, init_sessions_api
from tars.api.tasks import router as tasks_router, init_tasks_api
from tars.api.invoke import router as invoke_router, init_invoke_api
from tars.api.bi import router as bi_router, init_bi_api
from tars.api.knowledge import router as knowledge_router, init_knowledge_api
from tars.api.meeting import router as meeting_router, init_meeting_api
from tars.api.memory import router as memory_router, init_memory_api
from tars.api.audit import router as audit_router, init_audit_api
from tars.api.admin import router as admin_router, init_admin_api
from tars.api.roles import router as roles_router, init_roles_api
from tars.memory.scheduler import MemoryScheduler
from tars.tenant import TenantContextCache
from tars.cron import CronRuntime

# 初始化应用
app = FastAPI(title="TARS Agent", version="4.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 提升文件上传限制到 50MB（Starlette 默认 1MB）
from starlette.requests import Request as _StarletteRequest
_original_form = _StarletteRequest.form
async def _patched_form(self, *, max_files=1000, max_fields=1000, max_part_size=50*1024*1024, **kwargs):
    return await _original_form(self, max_files=max_files, max_fields=max_fields, max_part_size=max_part_size, **kwargs)
_StarletteRequest.form = _patched_form

# 初始化组件
db = Database()
user_store = UserStore(db)
permission_manager = PermissionManager()
evolution_manager = EvolutionManager()

from tars.database import EndpointStore
from tars.models.config import init_endpoint_store

endpoint_store = EndpointStore(db)
init_endpoint_store(endpoint_store)

# v4.0.0: Module switch loading & skill curator
module_registry.load()
init_skill_curator(db)

# v4.0.1: Per-tenant workspace 隔离
from tars.tools.tenant_workspace import init_tenant_workspace
init_tenant_workspace()

# ========= 注册内置工具到全局 tool_registry =========
project_dir = Path(__file__).parent.parent
workspace_sandbox = WorkspaceSandbox(workspace_dir=str(project_dir.parent))

tool_registry.register(WeatherTool())
tool_registry.register(FileTool(allowed_dirs=[str(project_dir.parent)]))
tool_registry.register(FileListTool())
tool_registry.register(FileWriteTool(sandbox=workspace_sandbox))
tool_registry.register(ShellTool(sandbox=workspace_sandbox))
tool_registry.register(ProcessTool())
tool_registry.register(NetworkTool())
tool_registry.register(MemoryTool(db=db))
cronjob_tool = CronJobTool(db=db)
tool_registry.register(cronjob_tool)
tool_registry.register(WebSearchTool())
tool_registry.register(WebFetchTool())
tool_registry.register(PythonExecTool(workspace_dir=str(project_dir.parent)))
tool_registry.register(ArchivalInsertTool(db=db))

# 会议语音识别工具（provider 在 agent 初始化后注入）
meeting_tool = MeetingRecognizerTool(model_size="base")
tool_registry.register(meeting_tool)

# 任务规划工具
task_planner_tool = TaskPlannerTool()
tool_registry.register(task_planner_tool)

# 任务执行器
task_executor = TaskExecutor(tool_registry=tool_registry)

# ========= 加载本地 Skill 包 =========
skills_dir = project_dir.parent / "skills"
skills_dir.mkdir(exist_ok=True)
from tars.skills.tenant_paths import TenantSkillPaths
_tenant_skill_paths = TenantSkillPaths(str(skills_dir))
_migrated = _tenant_skill_paths.migrate_flat_to_global()
if _migrated:
    print(f"[Skills] 已迁移 {_migrated} 个技能到 skills/_global/")
skill_loader = SkillLoader(
    skills_dir=str(skills_dir),
    tool_registry=tool_registry,
    skill_registry=skill_registry,
)
skill_loader._db = db  # v2.5: 权限数据写入 skills_v3
skill_loader.load_all()

pipelines_dir = project_dir.parent / "pipelines"
pipelines_dir.mkdir(exist_ok=True)
pipeline_registry = SkillPipelineRegistry()
PipelineLoader(str(pipelines_dir), pipeline_registry).load_all()

# ========= 初始化 SkillHub =========
skillhub_client = SkillHubClient()
_global_skills_dir = str(_tenant_skill_paths.global_dir) if _tenant_skill_paths.uses_v41_layout else str(skills_dir)
skillhub_local_catalog = LocalSkillCatalog(
    catalog_path=str(project_dir / "data" / "skillhub_catalog.json"),
    bundle_dir=str(project_dir / "data" / "skillhub" / "skills"),
    package_dir=_global_skills_dir,
)
skillhub_skills_sh = SkillsShClient(
    cache_path=str(project_dir / "data" / "skillhub" / "skills_sh_index.json"),
    cache_ttl=skills_config.skills_sh_cache_ttl,
    enabled=skills_config.skills_sh_enabled,
)
skillhub_installer = SkillInstaller(
    skills_dir=str(skills_dir),
    client=skillhub_client,
    skill_loader=skill_loader,
    skill_registry=skill_registry,
    local_catalog=skillhub_local_catalog,
)
init_skillhub_api(
    skillhub_client,
    skillhub_installer,
    skill_registry,
    str(project_dir / "data" / "skillhub_catalog.json"),
    local_catalog=skillhub_local_catalog,
    skills_sh_client=skillhub_skills_sh,
    user_store=user_store,
)
init_skills_api(skill_loader=skill_loader, tool_registry=tool_registry)

# ========= 初始化文件上传 =========
uploads_dir = project_dir / "uploads"
uploads_dir.mkdir(exist_ok=True)
file_storage = FileStorage(upload_dir=str(uploads_dir))
file_parser = FileParser()
init_file_storage(file_storage)

# ========= 初始化记忆系统（LLM 提取 + 语义搜索）=========
from tars.memory import MemoryManager, LocalEmbeddingProvider
# 模型已缓存到本地，禁止 HuggingFace Hub 网络请求（否则网络不通时会无限挂起）
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "10")
try:
    embedding_provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")
    print("[Startup] 嵌入模型 bge-small-zh-v1.5 加载成功")
except Exception as e:
    embedding_provider = None
    print(f"[Startup] 嵌入模型加载失败（语义搜索不可用）: {e}")

from tars.vectorstore import ChromaVectorStore

vector_store = ChromaVectorStore(
    persist_directory=str(project_dir / "data" / "vectorstore"),
    embedding_provider=embedding_provider,
)
if vector_store.is_available:
    print("[Startup] Chroma 向量数据库初始化成功")
else:
    print("[Startup] Chroma 向量数据库不可用，将使用 SQLite BLOB 回退")

memory_manager = MemoryManager(db=db, embedding_provider=embedding_provider, vector_store=vector_store)
tenant_context_cache = TenantContextCache(max_size=100)

# 注册 core memory 编辑工具（V3）
for tool in memory_manager.get_tools():
    tool_registry.register(tool)

# 注册知识库搜索工具
from tars.tools.builtin.knowledge_search import KnowledgeSearchTool
from tars.knowledge.retriever import KnowledgeRetriever
knowledge_retriever = KnowledgeRetriever(vector_store, embedding_provider)
tool_registry.register(KnowledgeSearchTool(retriever=knowledge_retriever, db=db))

# ========= 初始化 Agent =========
# v4.0.0: 从配置加载所有 provider，获取默认实例
from tars.config.providers_config import load_providers_config
from tars.models.fallback import wrap_provider_with_fallback

providers = load_providers_from_config()
_providers_cfg = load_providers_config()
_default_name = _providers_cfg.get("default_provider", "ollama-local")
default_provider = providers.get("_default")

# v4.0.0: 加载模块配置 + 技能 Curator
from tars.modules.registry import module_registry  # noqa: E402
module_registry.load()

from tars.skills.curator import init_skill_curator  # noqa: E402
_skill_curator = init_skill_curator(db)

agent = AgentV2(
    db=db, tool_registry=tool_registry, skill_registry=skill_registry,
    file_storage=file_storage, file_parser=file_parser,
    memory_manager=memory_manager,
    task_executor=task_executor,
    knowledge_retriever=knowledge_retriever,
)
agent.skill_loader = skill_loader

if default_provider:
    wrapped = wrap_provider_with_fallback(
        default_provider,
        providers,
        _providers_cfg.get("fallback", {}),
        primary_name=_default_name,
        db=db,
    )
    agent.provider = wrapped
    agent.dispatcher.set_provider(wrapped)
    memory_manager.set_provider(wrapped)

# v2.5: 初始化权限引擎
from tars.skills.permission_engine import permission_engine
permission_engine.db = db
# 默认授予已声明权限（local 技能信任）
for skill in skill_registry.list_all():
    try:
        declared = permission_engine.get_declared_permissions(skill.id)
        dangerous = {"shell", "network", "file_write"}
        if len(declared & dangerous) >= 3:
            print(f"[Startup] ⚠️ 技能 {skill.id} 声明了危险组合权限: {declared & dangerous}")
        permission_engine.grant_all(skill.id)
    except Exception:
        pass

memory_manager.set_provider(agent.provider)
connection_manager = ConnectionManager()
connection_manager.set_agent(agent)
cron_runtime = CronRuntime(db=db, scheduler=get_scheduler(), connection_manager=connection_manager)
cronjob_tool.set_runtime(cron_runtime)
memory_scheduler = MemoryScheduler(memory_manager.compressor, get_scheduler())
memory_scheduler.ensure_started()

# 注入 LLM provider 到会议识别工具（用于摘要生成）
meeting_tool.provider = agent.provider

# ========= 挂载路由 =========
app.include_router(model_config_router)
app.include_router(tools_router)
app.include_router(skills_router)
app.include_router(files_router)
app.include_router(sessions_router)
app.include_router(tasks_router)
app.include_router(invoke_router)
app.include_router(memory_router)
app.include_router(audit_router)
app.include_router(admin_router)
app.include_router(roles_router)

# 条件注册可选模块路由
if module_registry.is_enabled("skillhub"):
    app.include_router(skillhub_router)
if module_registry.is_enabled("bi"):
    app.include_router(bi_router)
if module_registry.is_enabled("knowledge"):
    app.include_router(knowledge_router)
if module_registry.is_enabled("meeting"):
    app.include_router(meeting_router)

init_sessions_api(db)
init_tasks_api(db, agent)
if module_registry.is_enabled("bi"):
    init_bi_api(db)
else:
    print("[Startup] BI 分析台模块已禁用 (config/modules.yaml → bi.enabled)")
if module_registry.is_enabled("knowledge"):
    init_knowledge_api(db, vector_store, embedding_provider)
if module_registry.is_enabled("meeting"):
    init_meeting_api(db, meeting_tool, vector_store, embedding_provider)
else:
    print("[Startup] 会议助手模块已禁用 (config/modules.yaml → meeting.enabled)")
init_memory_api(db, memory_manager)
init_audit_api(db)
init_admin_api(db)

# v4.0.2: 角色模板管理
from tars.gateway.role_template import init_role_template_manager
init_role_template_manager(db)
init_roles_api(user_store)

# v4.0.0: 初始化记忆权限引擎
from tars.security.memory_permission import init_memory_permission  # noqa: E402
init_memory_permission(db)

# v4.0.0: 初始化 Prompt Cache 和 Rate Limiter
from tars.cache.prompt_cache import init_prompt_cache  # noqa: E402
init_prompt_cache(ttl_seconds=300)

from tars.concurrency.limiter import init_rate_limiter  # noqa: E402

# Load concurrency settings from YAML config
_conc_config = {}
_conc_path = Path(__file__).parent.parent / "config" / "concurrency.yaml"
if _conc_path.exists():
    try:
        with open(_conc_path) as f:
            _conc_config = yaml.safe_load(f) or {}
    except Exception:
        pass

_ollama_cfg = _conc_config.get("providers", {}).get("ollama", {})
init_rate_limiter(
    max_concurrent=_ollama_cfg.get("max_concurrent", 2),
    per_user_max=_ollama_cfg.get("per_user_max", 1),
    queue_timeout=_ollama_cfg.get("queue_timeout", 60),
)

init_invoke_api(
    agent=agent,
    tenant_cache=tenant_context_cache,
    memory_manager=memory_manager,
    user_store=user_store,
    pipeline_engine=SkillPipelineEngine(
        pipeline_registry=pipeline_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
        provider=agent.provider,
    ),
)

# ================ API 路由 ================

# 模型列表与切换见 tars.models.config（/api/models/*），勿在此重复注册同路径以免覆盖带 provider 的切换逻辑。

# ============ 技能相关（已迁移到 api/skills.py 和 api/skillhub.py）============

class SkillResponse(BaseModel):
    """用户管理、人格等接口的通用响应（保留兼容）"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

# ============ 用户管理 ============

class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "user"

class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None


class AuthLoginRequest(BaseModel):
    identifier: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    role_template_id: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@tars.local"
DEFAULT_ADMIN_PASSWORD = "Admin123!"


def _serialize_user(user) -> Dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "role_template_id": getattr(user, "role_template_id", None),
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _get_user_by_identifier(identifier: str):
    user = user_store.get_user_by_email(identifier)
    if user:
        return user

    for candidate in user_store.get_all_users():
        if candidate.username == identifier:
            return candidate
    return None


def _validate_initial_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="初始密码至少 8 位")


def ensure_default_admin():
    """在系统没有管理员时创建默认管理员，保证首次可登录。"""
    users = user_store.get_all_users()
    if any(user.role == UserRole.ADMIN for user in users):
        return None

    email_conflict = any(user.email == DEFAULT_ADMIN_EMAIL for user in users)
    username_conflict = any(user.username == DEFAULT_ADMIN_USERNAME for user in users)
    if email_conflict or username_conflict:
        print(
            "[Startup] 跳过默认管理员创建：默认用户名或邮箱已被非管理员占用 "
            f"(username={DEFAULT_ADMIN_USERNAME}, email={DEFAULT_ADMIN_EMAIL})"
        )
        return None

    created_user = user_store.create_user(
        DEFAULT_ADMIN_USERNAME,
        DEFAULT_ADMIN_EMAIL,
        UserRole.ADMIN,
        password=DEFAULT_ADMIN_PASSWORD,
    )
    print(
        "[Startup] 已创建默认管理员账号 "
        f"(username={DEFAULT_ADMIN_USERNAME}, email={DEFAULT_ADMIN_EMAIL})"
    )
    return created_user

@app.get("/api/users", response_model=UserListResponse)
async def get_users():
    """获取所有用户（仅管理员）"""
    users = user_store.get_all_users()
    return {
        "users": [_serialize_user(u) for u in users],
        "total": len(users),
    }

@app.get("/api/users/me", response_model=UserResponse)
async def get_current_user(api_key: Optional[str] = None):
    """获取当前用户信息"""
    if not api_key:
        raise HTTPException(status_code=401, detail="未提供 API Key")
    
    user = user_store.get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    
    return _serialize_user(user)


@app.post("/api/auth/login", response_model=SkillResponse)
async def login(body: AuthLoginRequest, http_request: Request):
    """使用账号密码登录并返回现有 API Key"""
    from tars.security.audit import safe_audit, client_ip_from_request

    identifier = body.identifier.strip()
    user = _get_user_by_identifier(identifier)
    client_ip = client_ip_from_request(http_request)
    if not user or not user_store.verify_password(user.id, body.password):
        safe_audit(
            lambda lg: lg.log_login(
                user_id=user.id if user else "unknown",
                tenant_id=user.id if user else "default",
                success=False,
                detail=f"identifier={identifier}",
                client_ip=client_ip,
            )
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user_store.update_last_login(user.id)
    fresh_user = user_store.get_user_by_id(user.id)
    safe_audit(
        lambda lg: lg.log_login(
            user_id=fresh_user.id,
            tenant_id=fresh_user.id,
            success=True,
            detail=fresh_user.username,
            client_ip=client_ip,
        )
    )
    return {
        "success": True,
        "message": "登录成功",
        "data": {
            "api_key": fresh_user.api_key,
            "user": _serialize_user(fresh_user),
        },
    }

@app.post("/api/users", response_model=SkillResponse)
async def create_user(
    request: UserCreateRequest,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """创建新用户"""
    from tars.security.audit import safe_audit, client_ip_from_request

    try:
        role = UserRole(request.role) if request.role else UserRole.USER
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的角色类型")
    
    existing_user = user_store.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")

    _validate_initial_password(request.password)

    user = user_store.create_user(
        request.username,
        request.email,
        role,
        password=request.password,
    )
    actor_id = x_tenant_id or "default"
    safe_audit(
        lambda lg: lg.log_user_event(
            action="user_create",
            target_user_id=user.id,
            actor_id=actor_id,
            tenant_id=actor_id,
            detail=f"username={user.username}, role={user.role.value}",
            client_ip=client_ip_from_request(http_request),
        )
    )
    return {
        "success": True,
        "message": "用户创建成功",
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "api_key": user.api_key
        }
    }

@app.put("/api/users/{user_id}", response_model=SkillResponse)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """更新用户信息"""
    from tars.security.audit import safe_audit, client_ip_from_request

    update_data = {}
    if request.username:
        update_data['username'] = request.username
    if request.email:
        update_data['email'] = request.email
    if request.role:
        try:
            update_data['role'] = UserRole(request.role)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的角色类型")
    if request.password:
        _validate_initial_password(request.password)
        password_hash = user_store._hash_password(request.password)
        update_data['password_hash'] = password_hash
    
    success = user_store.update_user(user_id, **update_data)
    if success:
        user = user_store.get_user_by_id(user_id)
        actor_id = x_tenant_id or "default"
        changed_fields = ",".join(sorted(update_data.keys()))
        safe_audit(
            lambda lg: lg.log_user_event(
                action="user_update",
                target_user_id=user_id,
                actor_id=actor_id,
                tenant_id=actor_id,
                detail=f"fields={changed_fields}, role={user.role.value}",
                client_ip=client_ip_from_request(http_request),
            )
        )
        return {
            "success": True,
            "message": "用户信息已更新",
            "data": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value
            }
        }
    else:
        raise HTTPException(status_code=404, detail="用户不存在")

@app.delete("/api/users/{user_id}", response_model=SkillResponse)
async def delete_user(
    user_id: str,
    http_request: Request,
    x_tenant_id: Optional[str] = Header(default="default"),
):
    """删除用户"""
    from tars.security.audit import safe_audit, client_ip_from_request

    success = user_store.delete_user(user_id)
    if success:
        actor_id = x_tenant_id or "default"
        safe_audit(
            lambda lg: lg.log_user_event(
                action="user_delete",
                target_user_id=user_id,
                actor_id=actor_id,
                tenant_id=actor_id,
                client_ip=client_ip_from_request(http_request),
            )
        )
        return {"success": True, "message": "用户已删除"}
    else:
        raise HTTPException(status_code=404, detail="用户不存在")

# ============ 子代理配置 ============

class SubAgentConfigRequest(BaseModel):
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None
    temperature: Optional[float] = None
    personality_weight: Optional[float] = None
    enabled: Optional[bool] = None

class SubAgentListResponse(BaseModel):
    subagents: Dict[str, Any]

class SubAgentInvokeRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None

@app.get("/api/subagents", response_model=SubAgentListResponse)
async def get_subagents():
    """获取所有子代理配置"""
    return {"subagents": agent.get_subagent_info()}

@app.get("/api/subagents/{agent_type}", response_model=SkillResponse)
async def get_subagent(agent_type: str):
    """获取单个子代理配置"""
    subagents = agent.get_subagent_info()
    if agent_type in subagents:
        return {"success": True, "message": "success", "data": subagents[agent_type]}
    else:
        raise HTTPException(status_code=404, detail=f"子代理 {agent_type} 不存在")

@app.put("/api/subagents/{agent_type}", response_model=SkillResponse)
async def update_subagent(agent_type: str, request: SubAgentConfigRequest):
    """更新子代理配置"""
    config = {}
    if request.llm_model is not None:
        config['llm_model'] = request.llm_model
    if request.llm_provider is not None:
        config['llm_provider'] = request.llm_provider
    if request.temperature is not None:
        config['temperature'] = request.temperature
    if request.personality_weight is not None:
        config['personality_weight'] = request.personality_weight
    if request.enabled is not None:
        config['enabled'] = request.enabled
    
    success = agent.update_subagent_config(agent_type, config)
    if success:
        subagents = agent.get_subagent_info()
        return {
            "success": True,
            "message": f"子代理 {agent_type} 配置已更新",
            "data": subagents.get(agent_type)
        }
    else:
        raise HTTPException(status_code=404, detail=f"子代理 {agent_type} 不存在")

@app.post("/api/subagents/{agent_type}/invoke", response_model=SkillResponse)
async def invoke_subagent(agent_type: str, request: SubAgentInvokeRequest):
    """调用子代理执行任务"""
    result = await agent.subagent_manager.invoke_subagent(
        agent_type,
        request.task,
        request.context
    )
    return {"success": True, "message": "任务执行完成", "data": {"result": result}}

# ============ 人格设置 ============

class PersonalityParameters(BaseModel):
    honesty: Optional[float] = None
    humor: Optional[float] = None
    initiative: Optional[float] = None
    empathy: Optional[float] = None
    formality: Optional[float] = None
    creativity: Optional[float] = None
    conciseness: Optional[float] = None
    technical_depth: Optional[float] = None
    curiosity: Optional[float] = None
    skepticism: Optional[float] = None

class PersonalityUpdateRequest(BaseModel):
    parameters: Optional[PersonalityParameters] = None
    communication_style: Optional[str] = None
    behavior_rules: Optional[List[str]] = None

class PersonalityResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@app.get("/api/personality", response_model=PersonalityResponse)
async def get_personality():
    """获取当前人格设置"""
    if hasattr(agent.workspace, 'soul') and agent.workspace.soul:
        soul = agent.workspace.soul
        return {
            "success": True,
            "message": "success",
            "data": {
                "identity": {
                    "name": soul.identity.name,
                    "role": soul.identity.role,
                    "creator": soul.identity.creator
                },
                "parameters": {
                    "honesty": soul.parameters.honesty,
                    "humor": soul.parameters.humor,
                    "initiative": soul.parameters.initiative,
                    "empathy": soul.parameters.empathy,
                    "formality": soul.parameters.formality,
                    "creativity": soul.parameters.creativity,
                    "conciseness": soul.parameters.conciseness,
                    "technical_depth": soul.parameters.technical_depth,
                    "curiosity": soul.parameters.curiosity,
                    "skepticism": soul.parameters.skepticism
                },
                "communication_style": soul.communication_style,
                "behavior_rules": soul.behavior_rules
            }
        }
    else:
        return {"success": False, "message": "人格设置未初始化"}

@app.put("/api/personality", response_model=PersonalityResponse)
async def update_personality(request: PersonalityUpdateRequest):
    """更新人格设置"""
    if not hasattr(agent.workspace, 'soul') or not agent.workspace.soul:
        return {"success": False, "message": "人格设置未初始化"}
    
    soul = agent.workspace.soul
    
    if request.parameters:
        params = request.parameters.dict(exclude_unset=True)
        for key, value in params.items():
            if hasattr(soul.parameters, key):
                setattr(soul.parameters, key, value)
    
    if request.communication_style is not None:
        soul.communication_style = request.communication_style
    
    if request.behavior_rules is not None:
        soul.behavior_rules = request.behavior_rules
    
    return {"success": True, "message": "人格设置已更新", "data": {
        "parameters": {
            "honesty": soul.parameters.honesty,
            "humor": soul.parameters.humor,
            "initiative": soul.parameters.initiative,
            "empathy": soul.parameters.empathy,
            "formality": soul.parameters.formality,
            "creativity": soul.parameters.creativity,
            "conciseness": soul.parameters.conciseness,
            "technical_depth": soul.parameters.technical_depth,
            "curiosity": soul.parameters.curiosity,
            "skepticism": soul.parameters.skepticism
        },
        "communication_style": soul.communication_style,
        "behavior_rules": soul.behavior_rules
    }}

# ============ 自进化系统 ============

class EvolutionSettings(BaseModel):
    enabled: Optional[bool] = None
    auto_optimize: Optional[bool] = None

class EvolutionFeedbackRequest(BaseModel):
    conversation_id: str
    query: str
    response: str
    feedback: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class EvolutionStatsResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@app.get("/api/evolution/stats", response_model=EvolutionStatsResponse)
async def get_evolution_stats():
    """获取自进化系统统计信息"""
    stats = evolution_manager.get_stats()
    return {"success": True, "message": "success", "data": stats}

@app.get("/api/evolution/suggestions", response_model=EvolutionStatsResponse)
async def get_evolution_suggestions():
    """获取自进化系统优化建议"""
    suggestions = evolution_manager.get_personality_suggestions()
    return {"success": True, "message": "success", "data": {"personality": suggestions}}

@app.post("/api/evolution/optimize", response_model=EvolutionStatsResponse)
async def trigger_evolution():
    """手动触发一次优化"""
    results = evolution_manager.optimize()
    return {"success": True, "message": "优化完成", "data": results}

@app.post("/api/evolution/feedback", response_model=EvolutionStatsResponse)
async def submit_feedback(request: EvolutionFeedbackRequest):
    """提交对话反馈用于自进化"""
    evaluation = evolution_manager.record_conversation(
        conversation_id=request.conversation_id,
        query=request.query,
        response=request.response,
        explicit_feedback=request.feedback,
        context=request.context
    )
    
    return {"success": True, "message": "反馈已记录", "data": {
        "overall_score": evaluation.overall_score,
        "relevance": evaluation.relevance,
        "completeness": evaluation.completeness,
        "accuracy": evaluation.accuracy,
        "style_match": evaluation.style_match
    }}

@app.put("/api/evolution/settings", response_model=EvolutionStatsResponse)
async def update_evolution_settings(request: EvolutionSettings):
    """更新自进化系统设置"""
    if request.enabled is not None:
        evolution_manager.enabled = request.enabled
    if request.auto_optimize is not None:
        evolution_manager.auto_optimize = request.auto_optimize
    
    return {"success": True, "message": "设置已更新", "data": {
        "enabled": evolution_manager.enabled,
        "auto_optimize": evolution_manager.auto_optimize
    }}

# ============ 定时任务 ============

class CronJobCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    cron: str
    task_type: str = "reminder"
    task_config: Optional[Dict[str, Any]] = None

class CronJobUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cron: Optional[str] = None
    task_type: Optional[str] = None
    task_config: Optional[Dict[str, Any]] = None

class CronJobResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


def _serialize_reminder_notification(notification, include_logs: bool = True) -> Dict[str, Any]:
    data = {
        "id": notification.id,
        "job_id": notification.job_id,
        "session_id": notification.session_id,
        "task_name": notification.task_name,
        "message": notification.message,
        "delivery_status": notification.delivery_status,
        "error_message": notification.error_message,
        "is_read": notification.is_read,
        "triggered_at": notification.triggered_at.isoformat() if notification.triggered_at else None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
        "updated_at": notification.updated_at.isoformat() if notification.updated_at else None,
    }
    if include_logs:
        data["summary_logs"] = notification.summary_logs
    return data


def _serialize_cronjob(job, include_config: bool = False) -> Dict[str, Any]:
    data = {
        "id": job.id,
        "name": job.name,
        "description": job.description,
        "cron": job.cron_expression,
        "task_type": job.task_type,
        "enabled": job.enabled,
        "created_at": job.created_at.isoformat(),
        "last_run": job.last_run.isoformat() if job.last_run else None,
        "next_run": job.next_run.isoformat() if job.next_run else None,
        "latest_notification": None,
    }
    if include_config:
        data["task_config"] = json.loads(job.task_config)

    latest_notification = db.get_latest_reminder_notification_for_job(job.id)
    if latest_notification:
        data["latest_notification"] = _serialize_reminder_notification(
            latest_notification,
            include_logs=False,
        )
    return data

@app.get("/api/cronjobs", response_model=CronJobResponse)
async def get_cronjobs(user_id: str = "default"):
    """获取用户的定时任务列表"""
    jobs = db.get_user_cronjobs(user_id)
    return {
        "success": True,
        "message": "success",
        "data": {
            "jobs": [_serialize_cronjob(job) for job in jobs],
            "total": len(jobs)
        }
    }

@app.get("/api/cronjobs/{job_id}", response_model=CronJobResponse)
async def get_cronjob(job_id: str):
    """获取单个定时任务"""
    job = db.get_cronjob(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "success": True,
        "message": "success",
        "data": _serialize_cronjob(job, include_config=True)
    }


@app.get("/api/reminder-notifications", response_model=CronJobResponse)
async def list_reminder_notifications(
    user_id: str = "default",
    limit: int = 20,
    offset: int = 0,
):
    notifications = db.list_reminder_notifications(user_id, limit=limit, offset=offset)
    return {
        "success": True,
        "message": "success",
        "data": {
            "notifications": [
                _serialize_reminder_notification(notification, include_logs=False)
                for notification in notifications
            ],
            "total": db.count_reminder_notifications(user_id),
            "unread_total": db.count_unread_reminder_notifications(user_id),
            "limit": limit,
            "offset": offset,
        },
    }


@app.get("/api/reminder-notifications/{notification_id}", response_model=CronJobResponse)
async def get_reminder_notification(notification_id: str):
    notification = db.get_reminder_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {
        "success": True,
        "message": "success",
        "data": _serialize_reminder_notification(notification, include_logs=True),
    }


@app.post("/api/reminder-notifications/{notification_id}/read", response_model=CronJobResponse)
async def mark_reminder_notification_read(notification_id: str):
    notification = db.mark_reminder_notification_read(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {
        "success": True,
        "message": "提醒通知已标记已读",
        "data": _serialize_reminder_notification(notification, include_logs=True),
    }

@app.post("/api/cronjobs", response_model=CronJobResponse)
async def create_cronjob(request: CronJobCreateRequest, user_id: str = "default"):
    """创建定时任务"""
    job = db.create_cronjob(
        user_id=user_id,
        name=request.name,
        cron_expression=request.cron,
        task_type=request.task_type,
        task_config=json.dumps(request.task_config or {}),
        description=request.description
    )
    await cron_runtime.sync_job(job.id)
    
    return {
        "success": True,
        "message": "定时任务创建成功",
        "data": {
            "id": job.id,
            "name": job.name,
            "cron": job.cron_expression
        }
    }

@app.put("/api/cronjobs/{job_id}", response_model=CronJobResponse)
async def update_cronjob(job_id: str, request: CronJobUpdateRequest):
    """更新定时任务"""
    job = db.get_cronjob(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.description is not None:
        update_data["description"] = request.description
    if request.cron is not None:
        update_data["cron_expression"] = request.cron
    if request.task_type is not None:
        update_data["task_type"] = request.task_type
    if request.task_config is not None:
        update_data["task_config"] = json.dumps(request.task_config)
    
    db.update_cronjob(job_id, **update_data)
    await cron_runtime.sync_job(job_id)
    
    return {"success": True, "message": "定时任务更新成功"}

@app.put("/api/cronjobs/{job_id}/enable", response_model=CronJobResponse)
async def enable_cronjob(job_id: str, enabled: bool = True):
    """启用或禁用定时任务"""
    job = db.get_cronjob(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.update_cronjob(job_id, enabled=enabled)
    if enabled:
        await cron_runtime.sync_job(job_id)
    else:
        cron_runtime.unschedule_job(job_id)
    status = "启用" if enabled else "禁用"
    return {"success": True, "message": f"定时任务{status}成功"}

@app.delete("/api/cronjobs/{job_id}", response_model=CronJobResponse)
async def delete_cronjob(job_id: str):
    """删除定时任务"""
    job = db.get_cronjob(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.delete_cronjob(job_id)
    cron_runtime.unschedule_job(job_id)
    return {"success": True, "message": "定时任务删除成功"}

# ================ WebSocket 路由 ================

async def _serve_websocket(websocket: WebSocket, tenant_id: str):
    # v4.0.1: 验证 WebSocket 连接的 tenant 归属
    api_key = websocket.query_params.get("api_key", "")
    ws_user = None
    if api_key and user_store:
        ws_user = user_store.get_user_by_api_key(api_key)
        if ws_user and tenant_id != "default":
            if getattr(ws_user, "role", "user") != "admin" and ws_user.id != tenant_id:
                await websocket.close(code=4003, reason="无权访问该租户空间")
                return

    # v4.0.2: 构建 request_context 传递用户角色
    ws_request_context = {"transport": "websocket"}
    if ws_user:
        role_val = ws_user.role.value if hasattr(ws_user.role, "value") else str(ws_user.role)
        ws_request_context["user_id"] = ws_user.id
        ws_request_context["user_role"] = role_val

    import uuid
    connection_id = str(uuid.uuid4())
    tenant_context = tenant_context_cache.get_or_create(
        tenant_id or "default",
        lambda current_tenant: memory_manager.for_tenant(current_tenant),
    )

    await connection_manager.connect(connection_id, websocket, tenant_context=tenant_context, request_context=ws_request_context)
    try:
        while True:
            data = await websocket.receive_text()
            channel = connection_manager.active_connections.get(connection_id)
            if channel:
                try:
                    await channel.handle_message(data)
                except Exception as e:
                    print(f"[WebSocket] 连接 {connection_id[:8]}… 处理异常: {type(e).__name__}: {e}")
                    traceback.print_exc()
                    connection_manager.disconnect(connection_id)
                    break
    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)


@app.websocket("/ws")
async def websocket_endpoint_default(websocket: WebSocket):
    await _serve_websocket(websocket, "default")


@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint_tenant(websocket: WebSocket, tenant_id: str):
    await _serve_websocket(websocket, tenant_id)

# ================ v4.0.0: Provider + Module API ================

@app.get("/api/providers/usage")
async def get_provider_usage(
    tenant_id: str = "",
    provider: str = "",
    limit: int = 100,
):
    """Provider token usage stats (v4.1.0)."""
    rows, total = db.list_provider_usage(tenant_id=tenant_id, provider=provider, limit=limit)
    return {"items": rows, "total": total}


@app.get("/api/providers")
async def list_providers():
    """List registered provider types."""
    from tars.models import provider_registry
    return provider_registry.list_providers()

@app.get("/api/modules")
async def list_modules():
    """List module status (core + optional)."""
    return module_registry.list_modules()

@app.post("/api/providers/{name}/test")
async def test_provider(name: str):
    """Quick test: check if a configured provider is reachable."""
    try:
        instance = providers.get(name)
        if not instance:
            return {"status": "error", "message": f"Provider {name} not configured"}
        ok, msg = await instance.test_connection()
        return {"status": "ok" if ok else "error", "message": msg}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ================ 启动 ================

def init_skills():
    """初始化技能系统（SkillLoader 已在启动时加载）"""
    pass

@app.on_event("startup")
async def startup_event():
    """启动事件"""
    await init_scheduler()
    await cron_runtime.load_from_db()
    ensure_default_admin()
    # 遗忘清理
    stats = memory_manager.cleanup()
    if stats["decayed"] or stats["deleted"]:
        print(f"[Startup] 记忆遗忘: importance衰减={stats['decayed']} 删除={stats['deleted']}")
    # v2.2: 清理过期 Working Context
    try:
        db.cleanup_working_contexts()
    except Exception:
        pass
    # migration worker 已禁用（与主线程共享 SQLite 连接导致死锁）
    # v2.4: 崩溃恢复 — 扫描未完成任务，置为 paused
    try:
        conn = db._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM tasks WHERE status IN ('running','pending')")
        stale = cur.fetchall()
        if stale:
            cur.execute("UPDATE tasks SET status = 'paused' WHERE status IN ('running','pending')")
            conn.commit()
            print(f"[Startup] 崩溃恢复: {len(stale)} 个未完成任务已置为 paused: {[s[1][:20] for s in stale]}")
    except Exception as e:
        print(f"[Startup] 崩溃恢复扫描失败: {e}")

    print(f"[Startup] 已注册 {len(tool_registry.list_all())} 个工具: {tool_registry.list_names()}")
    print(f"[Startup] 已加载 {len(skill_registry.list_all())} 个技能")

@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    await shutdown_scheduler()
    from tars.tools.builtin.meeting_recognizer import shutdown_whisper_pool
    shutdown_whisper_pool()
    # v4.0.0: close shared connection pool
    from tars.models.connection_pool import close_connection_pool
    await close_connection_pool()

if __name__ == "__main__":
    # 初始化技能系统
    init_skills()
    
    uvicorn.run(
        "tars.main:app",
        host=os.getenv("TARS_HOST", "0.0.0.0"),
        port=int(os.getenv("TARS_PORT", "8000")),
        reload=True
    )
