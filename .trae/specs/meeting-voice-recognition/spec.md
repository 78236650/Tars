# 会议语音转录与总结功能 Spec

## Why

TARS Agent 需要支持会议录音的自动转录和智能总结，使用户能够：
- 上传会议录音文件（mp3/wav/m4a/mp4/webm）自动转录为文本
- 通过 LLM 生成结构化会议摘要（要点、决策、待办）
- 在 Web 界面管理转录历史记录
- 通过自然语言触发转录（TARS Skill 集成）

## What Changes

- **新增** `backend/tars/tools/builtin/meeting_recognizer.py` — MeetingRecognizerTool（Whisper 转录 + LLM 摘要）
- **新增** `backend/tars/api/meeting.py` — 会议 API 路由（上传、转写、摘要、历史、删除）
- **新增** `skills/meeting_notes/SKILL.md` — 会议助手 Skill 定义
- **新增** `frontend/src/views/MeetingView.vue` — 会议助手页面
- **新增** `frontend/src/components/meeting/AudioUploader.vue` — 音频上传组件
- **新增** `frontend/src/components/meeting/TranscriptionList.vue` — 转录历史列表
- **新增** `frontend/src/components/meeting/TranscriptionDetail.vue` — 转写结果与摘要展示
- **修改** `backend/tars/database/base.py` — 新增 `transcriptions` 表及数据访问方法
- **修改** `backend/tars/tools/builtin/__init__.py` — 导出新 Tool
- **修改** `backend/tars/main.py` — 注册 Tool 和 API Router
- **修改** `frontend/src/router/index.ts` — 添加 `/meeting` 路由
- **修改** `frontend/src/api/index.ts` — 添加 `meetingApi`
- **修改** `frontend/src/types/index.ts` — 添加 `Transcription` 类型

## Impact

- 新增能力：音频文件转录、会议摘要生成、转录历史管理
- 影响代码：后端 Tool 层、API 层、数据库层；前端路由、API、视图、组件
- 依赖新增 Python 包：`faster-whisper>=1.0.0`

## ADDED Requirements

### Requirement: 音频文件上传与转录

The system SHALL provide an API endpoint to upload audio files and transcribe them using Whisper.

#### Scenario: 成功上传并转录
- **WHEN** user uploads an audio file (mp3/wav/m4a/mp4/webm, ≤50MB)
- **THEN** the system saves the file, creates a transcription record with status `pending`, returns transcription_id
- **AND** asynchronously transcribes the audio using faster-whisper in a ProcessPoolExecutor
- **AND** updates the record with transcript text, language, duration, and status `completed`

#### Scenario: 不支持格式
- **WHEN** user uploads a file with unsupported extension
- **THEN** return HTTP 400 with error code `UNSUPPORTED_FORMAT`

#### Scenario: 文件过大
- **WHEN** user uploads a file > 50MB
- **THEN** return HTTP 413 with error code `FILE_TOO_LARGE`

### Requirement: 会议摘要生成

The system SHALL generate structured meeting summaries from transcription text using the configured LLM provider.

#### Scenario: 成功生成摘要
- **WHEN** user requests summary for a completed transcription
- **THEN** the system calls the current LLM provider with a summary prompt
- **AND** returns structured summary including: summary text, key_points list, timeline list

### Requirement: 转录历史管理

The system SHALL support CRUD operations for transcription records.

#### Scenario: 查询历史
- **WHEN** user requests transcription history
- **THEN** return paginated list of transcription records ordered by created_at DESC

#### Scenario: 删除记录
- **WHEN** user deletes a transcription record
- **THEN** remove the database record and associated audio file

### Requirement: TARS Skill 集成

The system SHALL expose meeting transcription as a TARS Skill triggerable via natural language.

#### Scenario: 通过对话触发转录
- **WHEN** user says "转录会议录音" or "总结会议文件" and provides a file path
- **THEN** TARS invokes the meeting_recognizer tool with the file path
- **AND** returns the transcription and summary to the user

### Requirement: Web 界面

The system SHALL provide a dedicated Meeting page in the TARS web UI.

#### Scenario: 访问会议助手页面
- **WHEN** user navigates to `/meeting`
- **THEN** display audio upload area, transcription history list, and detail view

#### Scenario: 上传音频
- **WHEN** user drags or selects an audio file
- **THEN** upload the file, show progress, and display transcription result when complete

## MODIFIED Requirements

### Requirement: Database Schema

The `Database._init_db()` method SHALL create the `transcriptions` table with the following schema:

```sql
CREATE TABLE IF NOT EXISTS transcriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
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
    created_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
)
```

### Requirement: Tool Registry

The `ToolRegistry` SHALL include `MeetingRecognizerTool` on startup.

### Requirement: API Router

The FastAPI app SHALL include the meeting router at prefix `/api/meeting`.

### Requirement: Frontend Router

The Vue router SHALL include the `/meeting` route pointing to `MeetingView.vue`.

## REMOVED Requirements

None.
