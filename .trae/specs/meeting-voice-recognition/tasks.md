# Tasks

## Phase 1: 后端基础实现

- [ ] **Task 1: 数据库层 — transcriptions 表**
  - [ ] SubTask 1.1: 在 `Database._init_db()` 中添加 `transcriptions` 表创建 SQL
  - [ ] SubTask 1.2: 添加 `Transcription` dataclass
  - [ ] SubTask 1.3: 添加数据库操作方法：`create_transcription`, `get_transcription`, `list_transcriptions`, `update_transcription`, `delete_transcription`
  - [ ] SubTask 1.4: 添加索引：`idx_transcriptions_user`, `idx_transcriptions_status`, `idx_transcriptions_created`

- [ ] **Task 2: Tool 层 — MeetingRecognizerTool**
  - [ ] SubTask 2.1: 创建 `backend/tars/tools/builtin/meeting_recognizer.py`
  - [ ] SubTask 2.2: 实现 `MeetingRecognizerTool` 类，继承 `BaseTool`
  - [ ] SubTask 2.3: 实现 `execute` 方法：验证文件、调用 `_sync_transcribe`（ProcessPoolExecutor 中执行 faster-whisper）
  - [ ] SubTask 2.4: 实现 `summarize` 方法：调用 LLM provider 生成结构化摘要
  - [ ] SubTask 2.5: 在 `backend/tars/tools/builtin/__init__.py` 中导出 `MeetingRecognizerTool`

- [ ] **Task 3: API 层 — meeting.py**
  - [ ] SubTask 3.1: 创建 `backend/tars/api/meeting.py`
  - [ ] SubTask 3.2: 实现 `POST /api/meeting/upload` — 上传音频并创建转录任务
  - [ ] SubTask 3.3: 实现 `POST /api/meeting/transcribe` — 对已有文件执行转写
  - [ ] SubTask 3.4: 实现 `POST /api/meeting/summarize` — 生成会议摘要
  - [ ] SubTask 3.5: 实现 `GET /api/meeting/status/{id}` — 查询转录状态
  - [ ] SubTask 3.6: 实现 `GET /api/meeting/history` — 获取转录历史列表
  - [ ] SubTask 3.7: 实现 `DELETE /api/meeting/{id}` — 删除转录记录
  - [ ] SubTask 3.8: 添加 `init_meeting_api(db)` 函数用于依赖注入

- [ ] **Task 4: 注册与集成**
  - [ ] SubTask 4.1: 在 `backend/tars/main.py` 中注册 `MeetingRecognizerTool` 到 `tool_registry`
  - [ ] SubTask 4.2: 在 `backend/tars/main.py` 中 `app.include_router(meeting_router)`
  - [ ] SubTask 4.3: 在 `backend/tars/main.py` 中调用 `init_meeting_api(db)`
  - [ ] SubTask 4.4: 在 `backend/tars/main.py` 中将 `agent.provider` 注入到 tool（用于摘要生成）

- [ ] **Task 5: Skill 层 — meeting_notes**
  - [ ] SubTask 5.1: 创建 `skills/meeting_notes/SKILL.md`（v2.5 规范）
  - [ ] SubTask 5.2: 定义触发关键词："转录会议录音"、"会议文件转录"、"总结会议文件"

## Phase 2: 前端实现

- [ ] **Task 6: 前端类型与 API**
  - [ ] SubTask 6.1: 在 `frontend/src/types/index.ts` 中添加 `Transcription` 接口
  - [ ] SubTask 6.2: 在 `frontend/src/api/index.ts` 中添加 `meetingApi`（upload, history, summarize, delete, status）

- [ ] **Task 7: 前端组件**
  - [ ] SubTask 7.1: 创建 `frontend/src/components/meeting/AudioUploader.vue` — 拖拽/点击上传音频，格式检查，进度显示
  - [ ] SubTask 7.2: 创建 `frontend/src/components/meeting/TranscriptionList.vue` — 历史记录列表，状态显示，删除操作
  - [ ] SubTask 7.3: 创建 `frontend/src/components/meeting/TranscriptionDetail.vue` — 转写文本展示、摘要展示、要点列表

- [ ] **Task 8: 前端页面与路由**
  - [ ] SubTask 8.1: 创建 `frontend/src/views/MeetingView.vue` — 整合上传、列表、详情三区域布局
  - [ ] SubTask 8.2: 在 `frontend/src/router/index.ts` 中添加 `/meeting` 路由
  - [ ] SubTask 8.3: 在导航栏/布局中添加会议助手入口（如侧边栏菜单）

## Phase 3: 依赖与验证

- [ ] **Task 9: Python 依赖**
  - [ ] SubTask 9.1: 检查 `backend/requirements.txt` 是否存在，添加 `faster-whisper>=1.0.0`
  - [ ] SubTask 9.2: 如无 requirements.txt，检查 `pyproject.toml` 或 `setup.py`，添加依赖

- [ ] **Task 10: 端到端验证**
  - [ ] SubTask 10.1: 启动后端，确认 API 路由注册成功
  - [ ] SubTask 10.2: 使用 curl/Postman 测试上传接口
  - [ ] SubTask 10.3: 测试转写流程（需 faster-whisper 模型下载）
  - [ ] SubTask 10.4: 测试摘要生成接口
  - [ ] SubTask 10.5: 测试历史查询和删除接口
  - [ ] SubTask 10.6: 启动前端，访问 `/meeting` 页面，验证 UI 渲染
  - [ ] SubTask 10.7: 测试 Skill 触发：在 Chat 中发送 "转录会议录音 /path/to/file.mp3"

# Task Dependencies

- Task 2 depends on Task 1（Tool 需要数据库操作）
- Task 3 depends on Task 1, Task 2（API 需要 Tool 和数据库）
- Task 4 depends on Task 2, Task 3（注册需要 Tool 和 API 已定义）
- Task 5 无依赖（纯 Skill 定义）
- Task 6 无依赖（纯前端类型/API 封装）
- Task 7 depends on Task 6（组件需要类型和 API）
- Task 8 depends on Task 7（页面需要组件）
- Task 9 无依赖
- Task 10 depends on Task 4, Task 8, Task 9（端到端需要前后端都就绪）

# Parallelizable Work

- Task 1, Task 5, Task 6, Task 9 可并行
- Task 2, Task 3 可并行（都依赖 Task 1，但彼此独立）
- Task 7, Task 8 可串行在前端类型完成后进行
