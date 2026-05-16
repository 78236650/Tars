# 会议语音识别与总结系统设计文档

**项目名称**: TARS 会议助手  
**版本**: v1.0  
**日期**: 2026-05-15  
**状态**: 设计阶段  

---

## 1. 项目概述

### 1.1 背景与目标

TARS Agent 系统已具备完善的能力体系，包括记忆管理、技能系统、工具调用和多通道交互。为了进一步扩展其实用价值，新增会议语音识别与总结功能，使 Agent 能够：

- **自动转录会议录音**：将音频转换为可搜索、可编辑的文本
- **智能生成摘要**：提取关键讨论点、决策和待办事项
- **自然语言交互**：用户可通过对话触发和管理会议记录

### 1.2 核心功能范围

**MVP 阶段（v1.0）**：
- ✅ 支持文件上传（mp3/wav/m4a/mp4/webm）
- ✅ 支持实时录音（页面操作）
- ✅ Whisper 本地语音识别
- ✅ LLM 生成结构化摘要
- ✅ 通过 TARS Skill 集成（文件转录）

**后续版本**：
- 🚧 发言人识别
- 🚧 多语言翻译
- 🚧 任务自动提取
- 🚧 导出功能（PDF/Word）

### 1.3 设计原则

1. **最小化可行产品**：快速交付核心价值，避免过度设计
2. **渐进式架构**：每层独立演进，便于迭代
3. **代码复用**：充分利用现有 TARS 组件（LLM、数据库、日志等）
4. **用户隐私优先**：采用本地 Whisper 模型，数据不外传

---

## 2. 系统架构

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                      用户交互层                               │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Web 界面（会议助手专属页面）                               ││
│  │                                                          ││
│  │  ┌────────────────┐      ┌────────────────┐            ││
│  │  │ 📁 文件上传    │      │ 🎤 实时录音    │            ││
│  │  │ • 支持拖拽     │      │ • 一键开始     │            ││
│  │  │ • 格式检查     │      │ • 实时显示     │            ││
│  │  └────────────────┘      └────────────────┘            ││
│  │                                                          ││
│  │  ┌────────────────────────────────────────────────────┐ ││
│  │  │ 📋 历史记录列表                                    │ ││
│  │  │ • 转写历史                                        │ ││
│  │  │ • 摘要查看                                        │ ││
│  │  └────────────────────────────────────────────────────┘ ││
│  └──────────────────────────────────────────────────────────┘│
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│                   TARS Skill 层                              │
│  skills/meeting_notes/                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 仅支持文件转录的触发                                  │   │
│  │ • "转录会议录音"                                     │   │
│  │ • "总结会议文件"                                     │   │
│  │ （实时录音仅通过页面操作）                            │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│                   Tool 层                                   │
│  backend/tars/tools/meeting_recognizer.py                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ • transcribe()          - 音频转写                   │   │
│  │ • transcribe_stream()    - 流式转写                   │   │
│  │ • summarize()           - 生成摘要                    │   │
│  │ • get_transcription()   - 获取历史记录               │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│                   API 层                                     │
│  backend/api/meeting.py                                    │
│  ┌─────────────────┐  ┌─────────────────┐                │
│  │ /upload         │  │ /transcribe     │                │
│  │ /record/ws      │  │ /summarize      │                │
│  │ /status/{id}    │  │ /history        │                │
│  └─────────────────┘  └─────────────────┘                │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│                   处理引擎层                                 │
│  ┌─────────────────────────┐ ┌────────────────────────┐   │
│  │ Whisper Engine          │ │ LLM Summary Engine     │   │
│  │ • 本地模型加载          │ │ • TARS 现有 LLM        │   │
│  │ • 音频分片              │ │ • 提示词模板           │   │
│  │ • 并行转写              │ │ • 结果格式化           │   │
│  └─────────────────────────┘ └────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

- **后端框架**：FastAPI (Python 3.11+)
- **语音识别**：OpenAI Whisper (本地部署)
- **LLM**：TARS 现有模型支持（OpenRouter / Claude / GPT）
- **数据库**：SQLite + FTS5（复用 TARS 数据库层）
- **前端**：Vue 3 + TypeScript + TailwindCSS
- **实时通信**：WebSocket

---

## 3. API 层详细设计

### 3.1 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/meeting/upload` | 上传音频文件并开始转写 |
| POST | `/api/meeting/transcribe` | 对已有文件进行转写 |
| POST | `/api/meeting/summarize` | 生成会议摘要 |
| GET | `/api/meeting/status/{id}` | 查询任务状态 |
| GET | `/api/meeting/history` | 获取转写历史 |
| DELETE | `/api/meeting/{id}` | 删除转写记录 |
| WS | `/api/meeting/ws/record/{session_id}` | 实时录音转写 |

### 3.2 请求与响应模型

#### 3.2.1 上传并转写

```python
# 请求
POST /api/meeting/upload
Content-Type: multipart/form-data

file: File (音频文件)
language: str (可选，语言代码)
model: str (可选，Whisper模型，默认 base)

# 响应
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "file_path": "/storage/meetings/user_123/1699999999_recording.mp3",
  "language": "zh",
  "duration": null,
  "transcript": null,
  "created_at": "2026-05-15T10:30:00Z"
}
```

#### 3.2.2 生成摘要

```python
# 请求
POST /api/meeting/summarize
{
  "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
  "summary_type": "structured",
  "max_length": 500
}

# 响应
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
  "summary": "本次会议主要讨论了项目进度和下周计划...",
  "key_points": [
    "完成了第一阶段的开发工作",
    "下周开始用户测试",
    "需要优化性能瓶颈"
  ],
  "timeline": [
    {"time": "00:01", "content": "开场介绍"},
    {"time": "00:05", "content": "项目进度汇报"}
  ],
  "created_at": "2026-05-15T10:35:00Z"
}
```

### 3.3 WebSocket 实时转写协议

```json
// 客户端 -> 服务端：发送音频数据
{
  "type": "audio",
  "data": "<base64 encoded audio chunk>"
}

// 客户端 -> 服务端：停止录音
{
  "type": "stop"
}

// 服务端 -> 客户端：实时转写结果
{
  "type": "transcript",
  "text": "正在讨论项目...",
  "done": false
}

// 服务端 -> 客户端：最终结果
{
  "type": "done",
  "transcription_id": "xxx",
  "full_text": "完整转写文本...",
  "duration": 123.5
}

// 服务端 -> 客户端：错误信息
{
  "type": "error",
  "message": "转写失败，请重试"
}
```

---

## 4. Tool 层详细设计

### 4.1 工具定义

```python
class MeetingRecognizerTool(BaseTool):
    name = "meeting_recognizer"
    description = "转录会议录音并生成摘要。输入音频文件路径，返回转写文本和结构化摘要。"
    
    parameters = {
        "file_path": {
            "type": "string",
            "description": "音频文件路径",
            "required": True
        },
        "action": {
            "type": "string",
            "description": "操作类型：transcribe（仅转写）或 summarize（转写+总结）",
            "default": "summarize"
        },
        "language": {
            "type": "string",
            "description": "语言代码，如 zh/en/ja，默认自动检测",
            "required": False
        }
    }
```

### 4.2 核心流程

1. **验证文件**：检查文件存在性和格式
2. **加载模型**：首次调用时懒加载 faster-whisper 模型
3. **执行转写**：在 ProcessPoolExecutor 中调用 faster-whisper（避免阻塞事件循环）
4. **生成摘要**：调用 TARS 现有 LLM Provider 提取要点（可选）
5. **保存结果**：持久化到数据库
6. **返回结果**：结构化 JSON 输出

### 4.3 异步执行方案

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

_whisper_pool = ProcessPoolExecutor(max_workers=2)

def _sync_transcribe(file_path: str, language: str = None, model_size: str = "base") -> dict:
    """在独立进程中执行转写（CPU 密集型，不能在事件循环中运行）"""
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(file_path, language=language)
    text = " ".join([seg.text for seg in segments])
    return {"text": text, "language": info.language, "duration": info.duration}

async def transcribe(file_path: str, language: str = None) -> dict:
    """异步包装，不阻塞事件循环"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_whisper_pool, _sync_transcribe, file_path, language)
```

> **关键设计决策**：Whisper 转写必须在 `ProcessPoolExecutor` 中执行。
> 之前调度器因事件循环阻塞导致后端卡死（已修复），此处采用相同防护策略。
> 使用进程池而非线程池，因为 Whisper 是 CPU 密集型且有 GIL 限制。

---

## 5. Skill 层详细设计

### 5.1 定位说明

**会议助手 Skill 仅支持文件转录功能**。实时录音功能通过前端页面独立操作，不支持通过自然语言触发。

### 5.2 触发条件

```yaml
name: meeting_notes
description: 会议助手，转录会议录音并生成结构化摘要。

trigger_keywords:
  - 转录会议录音
  - 会议文件转录
  - 总结会议文件

# 注意：实时录音功能仅通过页面操作，不支持自然语言触发
```

### 5.3 技能执行

```python
# skills/meeting_notes/main.py

class MeetingNotesSkill:
    """
    会议笔记技能
    
    注意：此技能仅处理文件转录请求。
    实时录音功能通过前端页面独立实现。
    """
    
    async def execute(self, file_path: str, action: str = "summarize"):
        """执行文件转录和摘要"""
        # 仅处理文件路径
        result = await self.meeting_tool.execute(
            file_path=file_path,
            action=action
        )
        return self._format_output(result)
```

### 5.4 输出格式

```json
{
  "status": "success",
  "transcription_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "会议转录和摘要完成",
  "content": "## 📋 会议摘要\n本次会议主要讨论了...\n\n## 🎯 关键要点\n1. 要点1\n2. 要点2",
  "full_transcript": "完整转写文本..."
}
```

### 5.5 使用限制

- ⚠️ 仅支持文件路径，不支持实时录音
- ⚠️ 实时录音请使用前端的"实时录音"功能
- ⚠️ 不支持语音输入触发转写任务

---

## 6. 数据库设计

### 6.1 表结构

```sql
CREATE TABLE IF NOT EXISTS transcriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT,
    file_size INTEGER,
    duration REAL,
    language TEXT,
    status TEXT DEFAULT 'pending',
    
    transcript TEXT,
    segments TEXT,
    
    summary TEXT,
    summary_type TEXT,
    key_points TEXT,
    
    model_used TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_transcriptions_user ON transcriptions(user_id);
CREATE INDEX idx_transcriptions_status ON transcriptions(status);
CREATE INDEX idx_transcriptions_created ON transcriptions(created_at DESC);
```

---

## 7. 数据流设计

### 7.1 文件上传流程

```
用户上传文件
    ↓
前端格式检查（mp3/wav/m4a/mp4/webm）
    ↓
POST /api/meeting/upload
    ↓
保存到 storage/meetings/{user_id}/{timestamp}_{filename}
    ↓
创建 transcription 记录 (status: pending)
    ↓
返回 transcription_id
    ↓
异步处理（后台任务）
    ↓
加载 Whisper 模型
    ↓
执行转写
    ↓
调用 LLM 生成摘要（可选）
    ↓
更新数据库 (status: completed)
    ↓
通知前端（WebSocket / Polling）
```

### 7.2 实时录音流程

```
前端开始录音（Web Audio API）
    ↓
音频分片（每 5 秒一段）
    ↓
WebSocket 发送到后端
    ↓
后端实时转写
    ↓
返回转写片段
    ↓
前端实时显示
    ↓
用户停止录音
    ↓
合并全部文本
    ↓
生成最终摘要
    ↓
返回完整结果
```

---

## 8. 错误处理

### 8.1 错误码定义

| 错误码 | HTTP 状态 | 说明 | 可恢复 |
|--------|-----------|------|--------|
| FILE_NOT_FOUND | 404 | 文件不存在 | ❌ |
| UNSUPPORTED_FORMAT | 400 | 不支持的格式 | ❌ |
| FILE_TOO_LARGE | 413 | 文件超过 50MB | ❌ |
| TRANSCRIPTION_FAILED | 500 | 转写失败 | ✅ |
| WHISPER_LOAD_FAILED | 500 | 模型加载失败 | ✅ |
| LLM_SUMMARY_FAILED | 500 | 摘要生成失败 | ✅ |
| RECORDING_TIMEOUT | 400 | 录音超时 | ❌ |

### 8.2 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "TRANSCRIPTION_FAILED",
    "message": "转写失败，请稍后重试"
  }
}
```

---

## 9. 配置管理

### 9.1 环境变量

```python
# Whisper 配置（faster-whisper）
WHISPER_MODEL = "base"           # tiny/base/small/medium/large-v3
WHISPER_DEVICE = "cpu"           # cpu/cuda
WHISPER_COMPUTE_TYPE = "int8"    # int8/float16/float32

# 文件限制
MAX_FILE_SIZE_MB = 50
SUPPORTED_FORMATS = ["mp3", "wav", "m4a", "mp4", "webm"]

# 录音限制
MAX_RECORDING_DURATION = 7200    # 2小时
AUDIO_CHUNK_DURATION = 5          # 5秒

# 存储配置
STORAGE_PATH = "storage/meetings"

# LLM 配置（复用 TARS 现有 Provider，不单独配置模型）
# 摘要通过 agent.provider 调用，继承当前选中的模型
SUMMARY_MAX_TOKENS = 1000
SUMMARY_TEMPERATURE = 0.7
```

---

## 10. 技术依赖

```txt
# 新增依赖
faster-whisper>=1.0.0
pydub>=0.25.1
```

> 选择 `faster-whisper`（基于 CTranslate2）而非 `openai-whisper`（PyTorch），原因：
> - 内存占用减半（base 模型 ~500MB vs ~1.5GB）
> - 推理速度快 4x
> - 不依赖 PyTorch（避免与 sentence-transformers 的 torch 版本冲突）

---

## 11. 实现计划

### Phase 1: MVP（3-5 天）

- [ ] API 层基础实现
  - [ ] 文件上传接口
  - [ ] 转写接口
  - [ ] 状态查询接口
- [ ] Tool 层实现
  - [ ] Whisper 集成
  - [ ] 工具注册
- [ ] 数据库模型
- [ ] 前端文件上传 UI
- [ ] 端到端测试

### Phase 2: 实时录音（2-3 天）

- [ ] WebSocket 实时接口
- [ ] 前端录音组件
- [ ] 实时显示功能

### Phase 3: 增强功能（后续迭代）

- [ ] 发言人识别
- [ ] 多语言翻译
- [ ] 任务提取
- [ ] 导出功能

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Whisper 模型加载慢 | 首次调用延迟高 | 模型缓存 + 预热机制 |
| 长音频处理超时 | 大文件转写失败 | 分片处理 + 超时配置 |
| 中文识别准确率 | 特定词汇误识别 | 提供语言参数 + 后处理校正 |
| 前端录音兼容性 | 某些浏览器不支持 | 检测并提示 + WebRTC fallback |

---

## 13. 验收标准

### 功能验收

- ✅ 支持上传 mp3/wav/m4a/mp4/webm 格式
- ✅ 单文件最大 50MB
- ✅ 转写准确率 ≥ 85%（中文标准普通话）
- ✅ 摘要生成完整（包含要点、结论）
- ✅ WebSocket 实时转写延迟 < 3 秒

### 性能验收

- ✅ 文件上传响应 < 1 秒
- ✅ 1 小时音频转写 < 15 分钟（CPU 模式）
- ✅ 并发处理 ≥ 3 个转写任务

### 集成验收

- ✅ TARS Skill 正确触发
- ✅ 历史记录可查询
- ✅ 结果可删除

---

**文档版本**: v1.0  
**创建日期**: 2026-05-15  
**下次审查**: 实现前
