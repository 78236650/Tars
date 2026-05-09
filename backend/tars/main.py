from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import uvicorn
import os
import asyncio
import json

# 导入 TARS 模块
from tars.channels import ConnectionManager
from tars.agent.agent import AgentV2
from tars.database import Database, UserStore
from tars.gateway.permission import PermissionManager, UserRole
from tars.evolution import EvolutionManager
from tars.scheduler import init_scheduler, shutdown_scheduler
from tars.models.config import router as model_config_router

# 新的工具/技能/SkillHub 系统
from tars.tools import registry as tool_registry
from tars.tools.builtin import (
    WeatherTool, FileTool, FileListTool, CommandTool, MemoryTool, CronJobTool,
    FileWriteTool, ShellTool, ProcessTool, NetworkTool,
)
from tars.tools.builtin.web_search import WebSearchTool
from tars.tools.builtin.web_fetch import WebFetchTool
from tars.tools.builtin.python_exec import PythonExecTool
from tars.memory.archival_insert_tool import ArchivalInsertTool
from tars.tools.sandbox import WorkspaceSandbox
from tars.skills import skill_registry, SkillLoader
from tars.skillhub import SkillHubClient, SkillInstaller
from tars.files import FileStorage, FileParser
from tars.orchestration import TaskPlannerTool, TaskExecutor
from tars.api.tools import router as tools_router
from tars.api.skills import router as skills_router
from tars.api.skillhub import router as skillhub_router, init_skillhub_api
from tars.api.files import router as files_router, init_file_storage
from tars.api.sessions import router as sessions_router, init_sessions_api
from tars.api.tasks import router as tasks_router, init_tasks_api

# 初始化应用
app = FastAPI(title="TARS Agent", version="2.2.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化组件
db = Database()
user_store = UserStore(db)
permission_manager = PermissionManager()
evolution_manager = EvolutionManager()

# 初始化自定义模型存储
from tars.database import CustomModelStore
custom_model_store = CustomModelStore(db)
from tars.models.config import init_custom_model_store
init_custom_model_store(custom_model_store)

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
tool_registry.register(CronJobTool(db=db))
tool_registry.register(WebSearchTool())
tool_registry.register(WebFetchTool())
tool_registry.register(PythonExecTool(workspace_dir=str(project_dir.parent)))
tool_registry.register(ArchivalInsertTool(db=db))

# 任务规划工具
task_planner_tool = TaskPlannerTool()
tool_registry.register(task_planner_tool)

# 任务执行器
task_executor = TaskExecutor(tool_registry=tool_registry)

# ========= 加载本地 Skill 包 =========
skills_dir = project_dir.parent / "skills"
skills_dir.mkdir(exist_ok=True)
skill_loader = SkillLoader(
    skills_dir=str(skills_dir),
    tool_registry=tool_registry,
    skill_registry=skill_registry,
)
skill_loader.load_all()

# ========= 初始化 SkillHub =========
skillhub_client = SkillHubClient()
skillhub_installer = SkillInstaller(
    skills_dir=str(skills_dir),
    client=skillhub_client,
    skill_loader=skill_loader,
)
init_skillhub_api(skillhub_client, skillhub_installer, skill_registry, str(project_dir / "data" / "skillhub_catalog.json"))

# ========= 初始化文件上传 =========
uploads_dir = project_dir / "uploads"
uploads_dir.mkdir(exist_ok=True)
file_storage = FileStorage(upload_dir=str(uploads_dir))
file_parser = FileParser()
init_file_storage(file_storage)

# ========= 初始化记忆系统（LLM 提取 + 语义搜索）=========
from tars.memory import MemoryManager, LocalEmbeddingProvider
try:
    embedding_provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-zh-v1.5")
    print("[Startup] 嵌入模型 bge-small-zh-v1.5 加载成功")
except Exception as e:
    embedding_provider = None
    print(f"[Startup] 嵌入模型加载失败（语义搜索不可用）: {e}")

memory_manager = MemoryManager(db=db, embedding_provider=embedding_provider)

# 注册 core memory 编辑工具（V3）
for tool in memory_manager.get_tools():
    tool_registry.register(tool)

# ========= 初始化 Agent =========
agent = AgentV2(
    db=db, tool_registry=tool_registry, skill_registry=skill_registry,
    file_storage=file_storage, file_parser=file_parser,
    memory_manager=memory_manager,
    task_executor=task_executor,
)
agent.skill_loader = skill_loader

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

# ========= 挂载路由 =========
app.include_router(model_config_router)
app.include_router(tools_router)
app.include_router(skills_router)
app.include_router(skillhub_router)
app.include_router(files_router)
app.include_router(sessions_router)
app.include_router(tasks_router)
init_sessions_api(db)
init_tasks_api(db, agent)

# ================ API 路由 ================

# ============ 模型相关 ============

class ModelSwitchRequest(BaseModel):
    model_name: str

class ModelSwitchResponse(BaseModel):
    success: bool
    message: str
    current_model: str

class ModelListResponse(BaseModel):
    models: List[str]
    current_model: str

@app.get("/api/models", response_model=ModelListResponse)
async def get_models():
    """获取可用模型列表"""
    models = await agent.get_available_models()
    return {"models": models, "current_model": agent.current_model}

@app.post("/api/models/switch", response_model=ModelSwitchResponse)
async def switch_model(request: ModelSwitchRequest):
    """热切换模型（无需重启服务）"""
    success = agent.switch_model(request.model_name)
    if success:
        return {
            "success": True,
            "message": f"已切换到模型: {request.model_name}",
            "current_model": agent.current_model
        }
    else:
        raise HTTPException(status_code=400, detail=f"无法切换到模型: {request.model_name}")

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
    role: Optional[str] = "user"

class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: str
    last_login: Optional[str] = None

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int

@app.get("/api/users", response_model=UserListResponse)
async def get_users():
    """获取所有用户（仅管理员）"""
    users = user_store.get_all_users()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role.value,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None
            }
            for u in users
        ],
        "total": len(users)
    }

@app.get("/api/users/me", response_model=UserResponse)
async def get_current_user(api_key: Optional[str] = None):
    """获取当前用户信息"""
    if not api_key:
        raise HTTPException(status_code=401, detail="未提供 API Key")
    
    user = user_store.get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None
    }

@app.post("/api/users", response_model=SkillResponse)
async def create_user(request: UserCreateRequest):
    """创建新用户"""
    try:
        role = UserRole(request.role) if request.role else UserRole.USER
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的角色类型")
    
    existing_user = user_store.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="该邮箱已被注册")
    
    user = user_store.create_user(request.username, request.email, role)
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
async def update_user(user_id: str, request: UserUpdateRequest):
    """更新用户信息"""
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
    
    success = user_store.update_user(user_id, **update_data)
    if success:
        user = user_store.get_user_by_id(user_id)
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
async def delete_user(user_id: str):
    """删除用户"""
    success = user_store.delete_user(user_id)
    if success:
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

@app.get("/api/cronjobs", response_model=CronJobResponse)
async def get_cronjobs(user_id: str = "default"):
    """获取用户的定时任务列表"""
    jobs = db.get_user_cronjobs(user_id)
    return {
        "success": True,
        "message": "success",
        "data": {
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "description": job.description,
                    "cron": job.cron_expression,
                    "task_type": job.task_type,
                    "enabled": job.enabled,
                    "created_at": job.created_at.isoformat(),
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "next_run": job.next_run.isoformat() if job.next_run else None
                }
                for job in jobs
            ],
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
        "data": {
            "id": job.id,
            "name": job.name,
            "description": job.description,
            "cron": job.cron_expression,
            "task_type": job.task_type,
            "task_config": json.loads(job.task_config),
            "enabled": job.enabled,
            "created_at": job.created_at.isoformat(),
            "last_run": job.last_run.isoformat() if job.last_run else None,
            "next_run": job.next_run.isoformat() if job.next_run else None
        }
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
    
    return {"success": True, "message": "定时任务更新成功"}

@app.put("/api/cronjobs/{job_id}/enable", response_model=CronJobResponse)
async def enable_cronjob(job_id: str, enabled: bool = True):
    """启用或禁用定时任务"""
    job = db.get_cronjob(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.update_cronjob(job_id, enabled=enabled)
    status = "启用" if enabled else "禁用"
    return {"success": True, "message": f"定时任务{status}成功"}

@app.delete("/api/cronjobs/{job_id}", response_model=CronJobResponse)
async def delete_cronjob(job_id: str):
    """删除定时任务"""
    job = db.get_cronjob(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    db.delete_cronjob(job_id)
    return {"success": True, "message": "定时任务删除成功"}

# ================ WebSocket 路由 ================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 生成唯一的连接 ID
    import uuid
    connection_id = str(uuid.uuid4())
    
    await connection_manager.connect(connection_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 通过 connection_manager 获取通道并处理消息
            channel = connection_manager.active_connections.get(connection_id)
            if channel:
                await channel.handle_message(data)
    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)

# ================ 启动 ================

def init_skills():
    """初始化技能系统（SkillLoader 已在启动时加载）"""
    pass

@app.on_event("startup")
async def startup_event():
    """启动事件"""
    await init_scheduler()
    # 遗忘清理
    stats = memory_manager.cleanup()
    if stats["decayed"] or stats["deleted"]:
        print(f"[Startup] 记忆遗忘: importance衰减={stats['decayed']} 删除={stats['deleted']}")
    # v2.2: 清理过期 Working Context + 启动迁移 worker
    try:
        db.cleanup_working_contexts()
    except Exception:
        pass
    try:
        memory_manager.start_migration_worker()
    except Exception:
        pass
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

if __name__ == "__main__":
    # 初始化技能系统
    init_skills()
    
    uvicorn.run(
        "tars.main:app",
        host=os.getenv("TARS_HOST", "0.0.0.0"),
        port=int(os.getenv("TARS_PORT", "8000")),
        reload=True
    )
