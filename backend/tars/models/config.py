# TARS Model Configuration API
# Layer 4: 模型层配置管理

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
import os
import logging

from tars.models import OllamaProvider, OpenRouterProvider, CustomProvider
from tars.agent import Agent
from tars.database import CustomModelStore, CustomModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["模型配置"])


class ProviderType(str, Enum):
    """支持的 Provider 类型"""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ProviderConfig(BaseModel):
    """Provider 配置"""
    type: ProviderType
    name: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    enabled: bool = True


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    provider: ProviderType
    description: Optional[str] = None


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[str]
    current_model: str
    current_provider: str


class ProviderListResponse(BaseModel):
    """Provider 列表响应"""
    providers: List[ProviderConfig]
    current_provider: str


class SwitchModelRequest(BaseModel):
    """切换模型请求"""
    model_name: str
    provider: Optional[ProviderType] = None
    api_key: Optional[str] = None


class SaveProviderRequest(BaseModel):
    """保存 Provider 配置请求"""
    provider: ProviderConfig


# 全局 Provider 配置存储（生产环境应持久化到数据库）
_provider_configs: Dict[str, ProviderConfig] = {
    "ollama": ProviderConfig(
        type=ProviderType.OLLAMA,
        name="Ollama (本地)",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        default_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        enabled=True
    ),
    "openrouter": ProviderConfig(
        type=ProviderType.OPENROUTER,
        name="OpenRouter",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        default_model="anthropic/claude-sonnet-4",
        enabled=False
    ),
    "anthropic": ProviderConfig(
        type=ProviderType.ANTHROPIC,
        name="Anthropic (Claude)",
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        default_model="claude-sonnet-4-20250514",
        enabled=False
    ),
    "openai": ProviderConfig(
        type=ProviderType.OPENAI,
        name="OpenAI (GPT)",
        api_key=os.getenv("OPENAI_API_KEY", ""),
        default_model="gpt-4o",
        enabled=False
    )
}

# 当前选中的 Provider
_current_provider = "ollama"


def get_agent() -> Agent:
    """获取全局 Agent 实例"""
    from tars.main import agent
    return agent


@router.get("/", response_model=ModelListResponse)
async def get_models():
    """获取可用模型列表"""
    agent = get_agent()
    try:
        models = await agent.get_available_models()
        return {
            "models": models,
            "current_model": agent.current_model,
            "current_provider": _current_provider
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/providers", response_model=ProviderListResponse)
async def get_providers():
    """获取所有 Provider 配置"""
    return {
        "providers": list(_provider_configs.values()),
        "current_provider": _current_provider
    }


@router.post("/providers/{provider_type}", response_model=ProviderListResponse)
async def save_provider(provider_type: str, config: SaveProviderRequest):
    """保存 Provider 配置"""
    global _provider_configs, _current_provider
    
    if provider_type not in _provider_configs:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_type}' 不存在")
    
    _provider_configs[provider_type] = config
    
    return {
        "providers": list(_provider_configs.values()),
        "current_provider": _current_provider
    }


@router.post("/switch", response_model=Dict[str, Any])
async def switch_model(request: SwitchModelRequest):
    """切换模型（支持热切换 Provider 和模型）"""
    global _current_provider
    
    agent = get_agent()
    
    # 如果指定了 Provider
    if request.provider:
        provider_type = request.provider.value
        
        if provider_type not in _provider_configs:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_type}' 不存在")
        
        config = _provider_configs[provider_type]
        
        # 检查 Provider 是否启用
        if not config.enabled and provider_type != "ollama":
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider_type}' 未启用，请先配置 API Key"
            )
        
        # 更新当前 Provider
        _current_provider = provider_type
        
        # 创建对应的 Provider 实例
        if provider_type == "ollama":
            base_url = config.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            provider = OllamaProvider(base_url=base_url, model=request.model_name)
        elif provider_type == "openrouter":
            if not config.api_key:
                raise HTTPException(status_code=400, detail="OpenRouter 需要配置 API Key")
            provider = OpenRouterProvider(api_key=config.api_key, model=request.model_name)
        else:
            raise HTTPException(status_code=400, detail=f"Provider '{provider_type}' 暂未实现")
        
        # 更新 Agent 的 Provider
        agent.provider = provider
        agent.current_model = request.model_name
        
        return {
            "success": True,
            "message": f"已切换到 {config.name}: {request.model_name}",
            "current_model": request.model_name,
            "current_provider": _current_provider
        }
    else:
        # 只切换模型
        success = agent.switch_model(request.model_name)
        if success:
            return {
                "success": True,
                "message": f"已切换到模型: {request.model_name}",
                "current_model": agent.current_model,
                "current_provider": _current_provider
            }
        else:
            raise HTTPException(status_code=400, detail=f"无法切换到模型: {request.model_name}")


@router.post("/providers/{provider_type}/test", response_model=Dict[str, Any])
async def test_provider(provider_type: str):
    """测试 Provider 连接"""
    if provider_type not in _provider_configs:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_type}' 不存在")
    
    config = _provider_configs[provider_type]
    
    try:
        if provider_type == "ollama":
            from tars.models import OllamaProvider
            provider = OllamaProvider(base_url=config.base_url)
            models = await provider.list_models()
            
            if models:
                return {
                    "success": True,
                    "message": f"连接成功，发现 {len(models)} 个模型",
                    "models": models[:5]  # 只返回前5个
                }
            else:
                return {
                    "success": False,
                    "message": "连接成功但未发现模型，请确保 Ollama 服务正在运行"
                }
        else:
            return {
                "success": False,
                "message": f"Provider '{provider_type}' 连接测试暂未实现"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}"
        }


@router.get("/ollama/models", response_model=Dict[str, Any])
async def get_ollama_models():
    """从 Ollama 获取模型列表（带详细描述）"""
    try:
        from tars.models import OllamaProvider
        provider = OllamaProvider()
        models = await provider.list_models()
        
        # 转换为 ModelInfo 格式
        model_infos = []
        for model in models:
            model_infos.append({
                "id": model,
                "name": model,
                "provider": "ollama",
                "description": f"Ollama 本地模型: {model}"
            })
        
        return {
            "models": model_infos,
            "count": len(model_infos)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Ollama 模型失败: {str(e)}")


_custom_model_store: Optional[CustomModelStore] = None


def init_custom_model_store(store: CustomModelStore):
    global _custom_model_store
    _custom_model_store = store


def get_custom_model_store() -> CustomModelStore:
    global _custom_model_store
    if _custom_model_store is None:
        from tars.database import Database, CustomModelStore as CMS
        db = Database()
        _custom_model_store = CMS(db)
    return _custom_model_store


class CustomModelCreate(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: Optional[str] = None
    description: Optional[str] = None


class CustomModelUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


@router.get("/custom", response_model=List[Dict[str, Any]])
async def get_custom_models():
    store = get_custom_model_store()
    models = store.get_all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "base_url": m.base_url,
            "model": m.model,
            "api_key": m.api_key,
            "description": m.description,
            "is_enabled": m.is_enabled,
            "created_at": m.created_at,
            "updated_at": m.updated_at
        }
        for m in models
    ]


@router.post("/custom", response_model=Dict[str, Any])
async def create_custom_model(config: CustomModelCreate):
    store = get_custom_model_store()
    model = store.create(
        name=config.name,
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        description=config.description
    )
    return {
        "id": model.id,
        "name": model.name,
        "base_url": model.base_url,
        "model": model.model,
        "api_key": model.api_key,
        "description": model.description,
        "is_enabled": model.is_enabled,
        "created_at": model.created_at,
        "updated_at": model.updated_at
    }


@router.put("/custom/{model_id}", response_model=Dict[str, Any])
async def update_custom_model(model_id: str, config: CustomModelUpdate):
    store = get_custom_model_store()
    existing = store.get_by_id(model_id)
    if not existing:
        raise HTTPException(status_code=404, detail="模型不存在")

    update_data = config.model_dump(exclude_unset=True)
    model = store.update(model_id, **update_data)
    return {
        "id": model.id,
        "name": model.name,
        "base_url": model.base_url,
        "model": model.model,
        "api_key": model.api_key,
        "description": model.description,
        "is_enabled": model.is_enabled,
        "created_at": model.created_at,
        "updated_at": model.updated_at
    }


@router.delete("/custom/{model_id}")
async def delete_custom_model(model_id: str):
    store = get_custom_model_store()
    existing = store.get_by_id(model_id)
    if not existing:
        raise HTTPException(status_code=404, detail="模型不存在")

    success = store.delete(model_id)
    return {"success": success, "message": "删除成功"}


@router.post("/custom/{model_id}/test", response_model=Dict[str, Any])
async def test_custom_model(model_id: str):
    store = get_custom_model_store()
    model = store.get_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    provider = CustomProvider(
        base_url=model.base_url,
        model=model.model,
        api_key=model.api_key
    )
    success, message = await provider.test_connection()
    return {"success": success, "message": message}


@router.post("/switch-custom/{model_id}", response_model=Dict[str, Any])
async def switch_to_custom_model(model_id: str):
    store = get_custom_model_store()
    model = store.get_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    if not model.is_enabled:
        raise HTTPException(status_code=400, detail="模型已禁用")

    logger.info(f"开始切换到自定义模型: id={model_id}, name={model.name}, model={model.model}, base_url={model.base_url}")

    agent = get_agent()
    try:
        success = agent.switch_to_custom_model(
            model_id=model.id,
            base_url=model.base_url,
            model=model.model,
            api_key=model.api_key
        )

        if success:
            global _current_provider
            _current_provider = f"custom:{model_id}"
            logger.info(f"模型切换成功: current_model={agent.current_model}, provider={_current_provider}")
            return {
                "success": True,
                "message": f"已切换到自定义模型: {model.name}",
                "current_model": agent.current_model,
                "current_provider": _current_provider
            }
        else:
            logger.error(f"模型切换失败: agent.switch_to_custom_model 返回 False")
            raise HTTPException(status_code=500, detail="切换失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"模型切换异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"切换异常: {str(e)}")
