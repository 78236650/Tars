# TARS 文件上传与多模态使用指南 (v2.0)

## 概述

TARS v2.0 支持在聊天中上传文件，Agent 能理解文件内容：

- **图片**（jpg/png/gif/webp/bmp）— 多模态模型直接理解，非多模态模型自动 OCR 降级
- **文档**（txt/md/pdf/docx/xlsx/csv/代码）— 提取文本后注入消息

## 使用方式

1. 点击聊天输入框左侧的 📎 按钮
2. 选择文件（单文件最大 20MB，单次最多 5 个）
3. 附件预览出现在输入框上方
4. 输入文字，点击 Send

## 支持的模型

### 多模态模型（能直接理解图片）

```
llava, bakllava
llama3.2-vision
minicpm-v
qwen2-vl, qwen-vl
```

这些模型会通过 Ollama 的 `images` 字段直接接收图片。

### 非多模态模型

上传图片时：
- 前端会收到 `warning` 事件：提示建议切换到多模态模型
- 后端自动用 Tesseract OCR 提取图片文字
- 将 OCR 文本注入消息发给 LLM

## 文件处理细节

| 格式 | 处理方式 | 最大内容长度 |
|------|---------|------------|
| 图片 | base64 → images 字段 / OCR 文本 | 图片: 20MB / OCR: 5000 字符 |
| txt/md/代码 | 直接读取 | 30000 字符 |
| PDF | pypdf 提取文本 | 30000 字符 |
| Word (docx) | python-docx 提取段落 | 30000 字符 |
| Excel (xlsx) | openpyxl 转制表符表格 | 30000 字符 |
| CSV | 直接读取 | 30000 字符 |

超出长度会自动截断，并在消息中附加"内容过长已截断"提示。

## OCR 降级

非多模态模型收到图片时会尝试 OCR：

- 需要系统安装 Tesseract：
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu: `apt install tesseract-ocr tesseract-ocr-chi-sim`
- 不安装时不报错，只是返回"无法提取图片文字"提示
- OCR 语言默认 `chi_sim+eng`（中英文）

## API

### 上传文件

```bash
curl -X POST http://localhost:8000/api/files/upload \
  -F "file=@/path/to/file.pdf"
```

响应：

```json
{
  "success": true,
  "file": {
    "file_id": "f_abc123",
    "name": "file.pdf",
    "type": "document",
    "mime_type": "application/pdf",
    "size": 245000,
    "preview": "前 200 字符..."
  }
}
```

### 获取文件信息

```
GET /api/files/{file_id}
```

### 删除文件

```
DELETE /api/files/{file_id}
```

## WebSocket 协议

发送消息时附加 `file_ids`：

```json
{
  "session_id": "xxx",
  "content": "帮我分析这张图片",
  "file_ids": ["f_abc123"]
}
```

后端会：
1. 根据 `file_id` 加载文件
2. 解析内容（文本提取/图片 base64）
3. 根据模型能力组装多模态消息
4. 发给 LLM

## 存储策略

- 文件保存到 `backend/uploads/{file_id}/{原始文件名}`
- 文件保留 24 小时后可自动清理
- 文件记录保存在内存，服务重启后丢失（聊天附件不持久化是合理的）

## 限制

- 单文件最大 20MB
- 单次消息最多 5 个附件
- 文本类文件最大 30000 字符
- OCR 文本最大 5000 字符

## 依赖

```
pypdf>=4.0.0
python-docx>=1.0.0
openpyxl>=3.1.0
Pillow>=10.0.0
pytesseract>=0.3.10
python-multipart>=0.0.6
```

系统依赖（可选）：`tesseract-ocr`（用于 OCR 降级）
