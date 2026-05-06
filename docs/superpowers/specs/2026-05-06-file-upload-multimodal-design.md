# Chat 文件上传与多模态理解设计

## 概述

为 TARS 聊天系统添加文件上传功能，支持图片和文档的上传与理解。多模态模型直接理解图片，非多模态模型通过 OCR 降级处理并提示用户。

## 支持的文件类型

| 类别 | 格式 | 处理方式 |
|------|------|---------|
| 图片 | jpg/png/gif/webp | 多模态模型直接理解；非多模态 OCR 提取文字 |
| 纯文本 | txt/md/py/json/yaml/代码 | 直接读取内容 |
| PDF | pdf | pypdf 提取文本 |
| Word | docx | python-docx 提取文本 |
| Excel/CSV | xlsx/csv | openpyxl 转文本表格 |

## 整体流程

```
前端                              后端
─────                            ─────
1. 用户点击 📎 选择文件
2. POST /api/files/upload    →   接收文件，保存到 uploads/
                             ←   返回 { file_id, type, name, size, preview }
3. 输入框上方显示附件预览
4. 用户输入文字，点击发送
5. WS send { content, file_ids } → Agent.handle_message()
                                    ↓
                              6. 根据 file_id 加载文件
                              7. FileParser 解析文件内容
                              8. 判断模型是否支持多模态
                                 - 支持：图片作为 images 字段发给 Ollama
                                 - 不支持：OCR 提取文字 + 发送 warning 事件
                              9. 文档类：提取文本附加到用户消息
                              10. 组装完整消息发给 LLM
                             ←   正常流式响应
```

## 后端模块设计

### 目录结构

```
tars/
├── files/
│   ├── __init__.py
│   ├── storage.py      # 文件存储管理
│   ├── parser.py       # 文件解析（文本提取、OCR）
│   └── models.py       # 数据模型
```

### 数据模型（models.py）

```python
@dataclass
class FileRecord:
    file_id: str
    name: str
    type: str           # "image" | "document"
    mime_type: str
    size: int
    path: str
    created_at: datetime

@dataclass
class ParsedContent:
    type: str                       # "image" | "text"
    text: Optional[str]             # 提取的文本内容
    image_base64: Optional[str]     # 图片 base64（仅图片）
    mime_type: Optional[str]        # image/png 等
    truncated: bool = False         # 是否被截断
    ocr_text: Optional[str]        # OCR 文字（图片降级用）
```

### FileStorage（storage.py）

```python
class FileStorage:
    def __init__(self, upload_dir: str = "uploads"):
        ...

    async def save(self, filename: str, content: bytes) -> FileRecord:
        """保存文件，生成 file_id，返回 FileRecord"""

    def get(self, file_id: str) -> Optional[FileRecord]:
        """根据 file_id 获取文件记录"""

    def delete(self, file_id: str) -> bool:
        """删除文件"""

    def generate_preview(self, record: FileRecord) -> str:
        """生成预览：图片返回缩略图 base64，文档返回前 200 字符"""
```

- 文件保存到 `backend/uploads/{file_id}/{原始文件名}`
- file_id 用 UUID 生成
- 内存中维护 file_id → FileRecord 映射
- 文件保留 24 小时后自动清理

### FileParser（parser.py）

```python
class FileParser:
    async def parse(self, record: FileRecord) -> ParsedContent:
        """根据文件类型分发解析"""

    async def parse_image(self, path: Path) -> ParsedContent:
        """返回 base64 + OCR 文本"""

    async def parse_text(self, path: Path) -> ParsedContent:
        """直接读取文本内容"""

    async def parse_pdf(self, path: Path) -> ParsedContent:
        """pypdf 提取文本"""

    async def parse_docx(self, path: Path) -> ParsedContent:
        """python-docx 提取文本"""

    async def parse_excel(self, path: Path) -> ParsedContent:
        """openpyxl/csv 转文本表格"""
```

**截断策略**：
- 文本类文件：最大 30000 字符
- 图片 OCR 文本：最大 5000 字符
- 超出时标记 `truncated=True`，Agent 附加提示

### OCR 降级

- 使用 pytesseract（Tesseract OCR 封装）
- 如果 Tesseract 未安装，返回提示"无法提取图片文字，建议安装 Tesseract 或切换到多模态模型"
- 不阻塞流程

## Agent 消息组装

### 多模态模型判断

```python
MULTIMODAL_MODELS = ["llava", "bakllava", "llama3.2-vision", "minicpm-v", "qwen2-vl", "qwen-vl"]

def _is_multimodal(self, model_name: str) -> bool:
    return any(m in model_name.lower() for m in MULTIMODAL_MODELS)
```

### 消息组装策略

| 文件类型 | 模型支持多模态 | 消息格式 |
|---------|-------------|---------|
| 图片 | 是 | Ollama 格式：`{"role": "user", "content": "...", "images": ["base64..."]}` |
| 图片 | 否 | 文本消息 + OCR 内容 + 发送 warning 事件 |
| 文档 | 任意 | 用户消息 + `\n\n---\n[文件: xxx.pdf]\n{提取的文本}` |

### Warning 事件

非多模态模型收到图片时，通过 WebSocket 发送：
```json
{
  "type": "warning",
  "session_id": "xxx",
  "message": "当前模型不支持图片理解，已使用 OCR 提取文字。建议切换到多模态模型（如 llava）获得更好效果。",
  "timestamp": "..."
}
```

## API 路由

### 新增路由（tars/api/files.py）

```
POST   /api/files/upload      # 上传文件（multipart/form-data）
GET    /api/files/{file_id}   # 获取文件信息
DELETE /api/files/{file_id}   # 删除文件
```

### 上传接口

请求：`multipart/form-data`，字段名 `file`

响应：
```json
{
  "success": true,
  "file": {
    "file_id": "f_abc123",
    "name": "screenshot.png",
    "type": "image",
    "mime_type": "image/png",
    "size": 245000,
    "preview": "data:image/png;base64,..."
  }
}
```

preview 字段：图片返回缩略图 base64（最大 200x200）；文档返回前 200 字符文本。

### WebSocket 协议变更

消息格式新增 `file_ids`：
```json
{"session_id": "xxx", "content": "帮我分析这张图片", "file_ids": ["f_abc123"]}
```

新增事件类型：

| 事件 | 说明 |
|------|------|
| `warning` | 模型能力不足提示 |
| `file_processing` | 文件正在解析中 |

## 前端改动

### ChatView.vue

输入区域新增：
- 📎 按钮触发文件选择
- 已选附件预览区（输入框上方）
- 附件可单独移除

布局：
```
┌─────────────────────────────────────────────────┐
│ [附件预览区]                                      │
│  📷 screenshot.png ✕   📄 report.pdf ✕           │
├─────────────────────────────────────────────────┤
│ 📎 │ Type a message...                    [Send] │
└─────────────────────────────────────────────────┘
```

发送时携带 file_ids，发送后清空附件列表。

### ChatPanel.vue

用户消息气泡中展示附件：
- 图片：显示缩略图（可点击放大）
- 文档：显示文件名 + 图标 + 大小

新增事件处理：
- `warning`：聊天面板中显示黄色提示条
- `file_processing`：显示"正在解析文件..."加载状态

### 前端限制

- 单文件最大 20MB
- 单次消息最多 5 个附件
- 超出时前端直接提示，不发请求

## 新增依赖

```
# requirements.txt 新增
pypdf>=4.0.0
python-docx>=1.0.0
openpyxl>=3.1.0
Pillow>=10.0.0
pytesseract>=0.3.10
```

系统依赖：`tesseract-ocr`（可选，未安装时 OCR 功能降级为提示）

## OllamaProvider 变更

需要支持 `images` 字段传递给 Ollama API：

```python
# 当消息包含图片时
formatted_messages.append({
    "role": "user",
    "content": text_content,
    "images": [base64_image_data]  # Ollama 多模态格式
})
```

## 实现阶段

1. **Phase 1**：后端 `files/` 模块（storage + parser + models）
2. **Phase 2**：API 路由 `/api/files/upload`
3. **Phase 3**：Agent 消息组装 + 多模态适配 + OllamaProvider images 支持
4. **Phase 4**：WebSocket 协议变更（file_ids 字段 + warning/file_processing 事件）
5. **Phase 5**：前端 ChatView 文件上传 UI + ChatPanel 附件展示
