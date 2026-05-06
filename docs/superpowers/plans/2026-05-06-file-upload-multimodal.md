# Chat 文件上传与多模态理解实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 TARS 聊天系统添加图片和文档上传功能，多模态模型直接理解图片，非多模态模型通过 OCR 降级。

**Architecture:** 文件通过 HTTP 上传后端保存到 `uploads/`，返回 `file_id`。WebSocket 消息携带 `file_ids` 引用，Agent 层根据模型能力组装多模态消息（Ollama `images` 字段或文本注入）。

**Tech Stack:** Python 3 (FastAPI, pypdf, python-docx, openpyxl, Pillow, pytesseract), Vue 3 + TypeScript (原生 File API)

---

## 文件结构

**后端新增：**
- `backend/tars/files/__init__.py` — 模块入口
- `backend/tars/files/models.py` — FileRecord + ParsedContent 数据类
- `backend/tars/files/storage.py` — FileStorage 类
- `backend/tars/files/parser.py` — FileParser 类
- `backend/tars/api/files.py` — 上传/获取/删除路由

**后端修改：**
- `backend/tars/models/ollama.py` — OllamaProvider 增加 images 参数支持
- `backend/tars/models/base.py` — ChatMessage 增加 images 字段
- `backend/tars/agent/agent_v2.py` — handle_message 增加 file_ids + 多模态适配
- `backend/tars/channels/websocket.py` — receive 解析 file_ids 字段
- `backend/tars/main.py` — 注册 files 路由
- `backend/requirements.txt` — 新增依赖

**前端修改：**
- `frontend/src/types/index.ts` — 新增 Attachment 类型
- `frontend/src/api/index.ts` — 新增 filesApi
- `frontend/src/views/ChatView.vue` — 文件上传 UI + file_ids 发送
- `frontend/src/components/chat/ChatPanel.vue` — 附件展示

**测试新增：**
- `backend/tests/test_files.py` — 存储、解析、API 测试

---

## Task 1: 新增依赖

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 在 requirements.txt 末尾追加依赖**

在文件末尾追加：
```
pypdf>=4.0.0
python-docx>=1.0.0
openpyxl>=3.1.0
Pillow>=10.0.0
pytesseract>=0.3.10
python-multipart>=0.0.6
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend && ./venv/bin/pip install pypdf python-docx openpyxl Pillow pytesseract python-multipart`
Expected: 所有包安装成功

- [ ] **Step 3: 验证导入**

Run: `./venv/bin/python3 -c "import pypdf, docx, openpyxl, PIL, pytesseract; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add file parsing dependencies"
```

---

## Task 2: FileRecord 和 ParsedContent 数据模型

**Files:**
- Create: `backend/tars/files/__init__.py`
- Create: `backend/tars/files/models.py`
- Test: `backend/tests/test_files.py`

- [ ] **Step 1: 写失败测试 tests/test_files.py**

```python
"""TARS 文件模块测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime


class TestFileRecord:
    def test_create_file_record(self):
        from tars.files.models import FileRecord
        rec = FileRecord(
            file_id="f_abc",
            name="test.png",
            type="image",
            mime_type="image/png",
            size=1024,
            path="/tmp/test.png",
            created_at=datetime.now(),
        )
        assert rec.file_id == "f_abc"
        assert rec.type == "image"


class TestParsedContent:
    def test_create_parsed_content(self):
        from tars.files.models import ParsedContent
        pc = ParsedContent(type="text", text="hello")
        assert pc.type == "text"
        assert pc.text == "hello"
        assert pc.truncated is False
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd backend && ./venv/bin/python3 -m pytest tests/test_files.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'tars.files'

- [ ] **Step 3: 实现 files/__init__.py**

```python
from .models import FileRecord, ParsedContent

__all__ = ["FileRecord", "ParsedContent"]
```

- [ ] **Step 4: 实现 files/models.py**

```python
"""TARS 文件模块 - 数据模型"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    type: str                           # "image" | "text"
    text: Optional[str] = None
    image_base64: Optional[str] = None
    mime_type: Optional[str] = None
    truncated: bool = False
    ocr_text: Optional[str] = None
```

- [ ] **Step 5: 运行测试验证通过**

Run: `cd backend && ./venv/bin/python3 -m pytest tests/test_files.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/tars/files/ backend/tests/test_files.py
git commit -m "feat(files): add FileRecord and ParsedContent models"
```