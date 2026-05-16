# Checklist

## 数据库层

- [ ] `transcriptions` 表在 `Database._init_db()` 中正确创建（含所有字段和索引）
- [ ] `Transcription` dataclass 定义完整
- [ ] `create_transcription` 方法正确插入记录并返回对象
- [ ] `get_transcription` 方法通过 id 正确查询记录
- [ ] `list_transcriptions` 方法按 `created_at DESC` 返回列表
- [ ] `update_transcription` 方法支持部分字段更新
- [ ] `delete_transcription` 方法正确删除记录

## Tool 层

- [ ] `MeetingRecognizerTool` 继承 `BaseTool`，name="meeting_recognizer"
- [ ] `parameters_schema` 正确定义（file_path, action, language）
- [ ] `execute` 方法验证文件存在性和格式
- [ ] Whisper 转写在 `ProcessPoolExecutor` 中执行（非事件循环阻塞）
- [ ] `summarize` 方法调用 LLM provider 生成结构化摘要
- [ ] 摘要输出包含 summary、key_points、timeline
- [ ] Tool 在 `backend/tars/tools/builtin/__init__.py` 中导出

## API 层

- [ ] `POST /api/meeting/upload` 支持 multipart 上传，格式检查，大小限制
- [ ] 上传成功后返回 transcription_id 和 pending 状态
- [ ] 异步后台执行转写，更新数据库状态
- [ ] `POST /api/meeting/transcribe` 对已有文件执行转写
- [ ] `POST /api/meeting/summarize` 生成结构化摘要
- [ ] `GET /api/meeting/status/{id}` 返回当前转录状态
- [ ] `GET /api/meeting/history` 返回分页历史列表
- [ ] `DELETE /api/meeting/{id}` 删除记录和关联文件
- [ ] 错误响应格式统一（success: false, error: {code, message}）
- [ ] API 在 `main.py` 中正确注册和初始化

## Skill 层

- [ ] `skills/meeting_notes/SKILL.md` 符合 v2.5 规范
- [ ] 触发关键词包含："转录会议录音"、"会议文件转录"、"总结会议文件"
- [ ] Skill 描述清晰说明仅支持文件转录

## 前端类型与 API

- [ ] `Transcription` 接口在 `types/index.ts` 中定义完整
- [ ] `meetingApi` 在 `api/index.ts` 中定义（upload, history, summarize, delete, status）

## 前端组件

- [ ] `AudioUploader.vue` 支持拖拽和点击上传
- [ ] 上传前进行格式检查（mp3/wav/m4a/mp4/webm）
- [ ] 上传过程中显示进度/状态
- [ ] `TranscriptionList.vue` 显示历史记录列表
- [ ] 列表项显示文件名、状态、创建时间
- [ ] 支持删除操作
- [ ] `TranscriptionDetail.vue` 显示转写文本
- [ ] 显示结构化摘要（summary、key_points、timeline）

## 前端页面与路由

- [ ] `MeetingView.vue` 整合上传、列表、详情三区域
- [ ] `/meeting` 路由在 `router/index.ts` 中注册
- [ ] 导航栏/侧边栏有会议助手入口

## 注册与集成

- [ ] `MeetingRecognizerTool` 在 `main.py` 中注册到 `tool_registry`
- [ ] `meeting_router` 在 `main.py` 中挂载到 app
- [ ] `init_meeting_api(db)` 在 `main.py` 中被调用
- [ ] LLM provider 正确注入到 Tool（用于摘要生成）

## 依赖

- [ ] `faster-whisper>=1.0.0` 已添加到项目依赖文件

## 端到端验证

- [ ] 后端启动无报错，API 路由注册成功
- [ ] 文件上传接口返回正确（curl/Postman）
- [ ] 转写流程执行成功（生成 transcript）
- [ ] 摘要生成接口返回正确结构
- [ ] 历史查询和删除接口工作正常
- [ ] 前端 `/meeting` 页面可访问，UI 渲染正常
- [ ] 前端上传音频文件流程完整跑通
- [ ] Skill 触发：Chat 中发送关键词可调用 meeting_recognizer
