# TARS 生图 & 生视频能力设计方案

> 版本: v0.1 | 日期: 2026-06-11 | 状态: 方案阶段

## 1. 目标

在 TARS 聊天中支持：
- **图像生成**：用户输入提示词 → LLM 调用工具 → 返回图片（base64/URL）→ 聊天区渲染展示
- **视频生成**：同上
- **能力切换**：前端可切换当前使用哪个生成服务（例如 Stable Diffusion ↔ DALL·E；Runway ↔ Pika）
- **配置化**：通过环境变量/端点配置接入不同生成 API，不改代码即可换供应商

## 2. 设计原则

- **不走"换 LLM 模型"路线**：生图/生视频不是对话模型，LLM 仍然是文本推理引擎，通过 **Tool Calling** 调用生成服务
- **能力切换 = 切换工具背后的 API 端点**：类似于现在聊天的 Ollama ↔ OpenAI Compatible 切换，但用于生成工具
- **纯文本对话环境也能输出**：图片以 base64 data URL 嵌入 Markdown，视频返回公网 URL

## 3. 架构总览

```
用户输入 "画一只猫" 
    → LLM (文本推理) 决定调用 image_gen 工具
    → ImageGenTool 调用配置的 API (Stable Diffusion / DALL·E / ...)
    → 返回 { image_url, image_base64 }
    → 前端渲染 <img> 标签

用户输入 "生成一段5秒海浪视频"
    → LLM 决定调用 video_gen 工具  
    → VideoGenTool 调用 Runway / Pika / 可灵 API
    → 返回 { video_url, status } (异步任务)
    → 前端渲染 <video> 或轮询状态
```

## 4. 后端设计

### 4.1 新增配置: `backend/config/generation.yaml`

```yaml
# 生成模型配置 (image / video)
image:
  default_provider: "stability"
  providers:
    stability:
      type: stability
      api_key: "${STABILITY_API_KEY}"
      base_url: "https://api.stability.ai"
      default_model: "stable-diffusion-xl-1024-v1-0"
      display_name: "Stability AI"
    openai_dalle:
      type: openai_image
      api_key: "${OPENAI_API_KEY}"
      base_url: "https://api.openai.com/v1"
      default_model: "dall-e-3"
      display_name: "DALL·E 3"

video:
  default_provider: "runway"
  providers:
    runway:
      type: runway
      api_key: "${RUNWAY_API_KEY}"
      base_url: "https://api.runwayml.com/v1"
      display_name: "Runway"
    kling:
      type: kling
      api_key: "${KLING_API_KEY}"
      base_url: "https://api.klingai.com/v1"
      display_name: "可灵 Kling"
```

### 4.2 新增工具: `backend/tars/tools/builtin/image_gen.py`

```python
class ImageGenTool(BaseTool):
    name = "image_gen"
    description = "生成 AI 图片。根据文字描述调用配置的图像生成模型创建图片。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "图片描述（中文或英文）"},
            "negative_prompt": {"type": "string", "description": "负面提示词"},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "style": {"type": "string", "description": "风格：realistic/anime/oil-painting/3d-render"},
        },
        "required": ["prompt"],
    }
```

### 4.3 新增工具: `backend/tars/tools/builtin/video_gen.py`

```python
class VideoGenTool(BaseTool):
    name = "video_gen"
    description = "生成 AI 视频。根据文字描述调用配置的视频生成模型创建短视频。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "视频描述"},
            "duration": {"type": "integer", "default": 5, "description": "时长（秒）"},
            "style": {"type": "string", "description": "风格"},
        },
        "required": ["prompt"],
    }
```

### 4.4 Provider 适配器

```
backend/tars/generation/
  __init__.py
  base.py          # BaseGenProvider, GenResult
  config.py         # load_generation_config()
  providers/
    __init__.py
    stability.py     # Stability AI (REST API)
    openai_image.py  # DALL·E (OpenAI Images API)
    runway.py        # Runway Gen-3
    kling.py         # 可灵
```

每个 provider 实现统一接口：
```python
class BaseGenProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> GenResult: ...

@dataclass
class GenResult:
    success: bool
    url: Optional[str] = None        # 公网 URL
    base64: Optional[str] = None     # base64 data URL (图片)
    task_id: Optional[str] = None    # 异步任务 ID (视频)
    error: Optional[str] = None
```

### 4.5 API 端点（配置/切换）

新增路由 `backend/tars/api/generation.py`：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/generation/config` | 获取当前生成配置（所有可用 provider 和当前选择） |
| POST | `/api/generation/switch` | 切换 image/video 的 provider 和 model |
| POST | `/api/generation/image/test` | 测试图像生成（生成一张测试图） |

### 4.6 工具注册（main.py）

```python
from tars.generation import load_generation_config, ImageGenTool, VideoGenTool

gen_config = load_generation_config()
image_gen_tool = ImageGenTool(config=gen_config)
video_gen_tool = VideoGenTool(config=gen_config)
tool_registry.register(image_gen_tool)
tool_registry.register(video_gen_tool)
```

## 5. 前端设计

### 5.1 能力切换 UI

在现有的模型选择器（LeftPanel/Sidebar）旁边增加一个「能力」切换：

```
[ ▼ 文本对话: llama3.2  ]  [ ▼ 图片: SD XL  ]  [ ▼ 视频: 可灵  ]
```

或者在 ChatView header 中增加 capability tabs：

```
[ 💬 对话 ] [ 🎨 生图 ] [ 🎬 生视频 ]
```

选择「生图」时，系统提示词自动注入，引导 LLM 优先使用 `image_gen` 工具。

### 5.2 图片渲染

ChatPanel 的消息渲染中，检测 `tool_result` 里包含 `image_base64` / `image_url`：

```vue
<!-- 在消息气泡中 -->
<div v-if="msg.images?.length" class="generated-images">
  <img v-for="img in msg.images" :src="img.url || img.base64" class="gen-image" />
</div>
```

### 5.3 视频渲染

```vue
<div v-if="msg.video_url" class="generated-video">
  <video :src="msg.video_url" controls />
  <span v-if="msg.video_status === 'processing'">生成中...</span>
</div>
```

### 5.4 Store 扩展

`frontend/src/stores/settings.ts` 增加：

```typescript
const imageProvider = ref('stability')
const imageModel = ref('stable-diffusion-xl-1024-v1-0')
const videoProvider = ref('runway')
const videoModel = ref('gen3')

const activeCapability = ref<'chat' | 'image' | 'video'>('chat')
```

## 6. 实施路径

### Phase 1: 最小可用（工具 + Stability AI）
- [ ] 创建 `backend/tars/generation/` 模块（base + config + stability provider）
- [ ] 创建 `ImageGenTool`，硬编码对接 Stability AI REST API
- [ ] `main.py` 注册工具
- [ ] 编写 `SKILL.md` 引导 LLM 使用 `image_gen` 工具
- [ ] 前端 ChatPanel 支持渲染返回的图片

### Phase 2: 配置化 + 切换
- [ ] `generation.yaml` 配置加载
- [ ] API 端点 `/api/generation/config` + `/switch`
- [ ] 前端能力切换 UI（chat/image/video tabs）
- [ ] 前端 settings store 扩展

### Phase 3: 视频生成
- [ ] `VideoGenTool` + Runway/可灵 provider
- [ ] 异步任务轮询
- [ ] 前端视频播放渲染

### Phase 4: 多 Provider
- [ ] DALL·E provider
- [ ] Pika / Sora provider（如有 API）
- [ ] 前端 provider 下拉切换

## 7. 关键风险

| 风险 | 对策 |
|------|------|
| 视频生成是异步的（几分钟），HTTP 同步请求会超时 | 返回 task_id + 轮询端点，前端定时查状态 |
| 图片 base64 太大撑爆上下文 | 返回缩略图 + 公网 URL；或写文件后用 file 工具读 |
| LLM 不主动调用 image_gen 工具 | 写 SKILL.md + 系统提示词注入 |
| 生图 API 需要外币信用卡 | 优先接国内可用的：硅基流动(Stable Diffusion)、通义万相、可灵 |
