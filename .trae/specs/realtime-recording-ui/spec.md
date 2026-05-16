# 实时录音转写 UI 升级 Spec

## Why

当前实现把录音按钮塞在文件上传组件里，没有独立的录音界面。需要在会议助手页面中提供独立的录音功能，让用户能够：
- 一键开始录音（独立入口）
- 实时查看转写文本
- 录音结束后自动保存为独立会话
- 可选生成摘要

## What Changes

- **新增** `frontend/src/components/meeting/RecordingPanel.vue` — 独立录音面板组件
- **修改** `frontend/src/views/MeetingView.vue` — 添加录音面板入口和布局
- **依赖** `backend/tars/api/meeting.py` — WebSocket 端点 `/api/meeting/ws/record`（已实现）

## Impact

- 新增能力：实时录音转写、录音会话管理
- 影响代码：前端组件层
- 依赖：后端 WebSocket 实时转写服务

## ADDED Requirements

### Requirement: 录音面板组件

The system SHALL provide a `RecordingPanel.vue` component that manages the complete recording lifecycle.

#### Scenario: 空闲状态
- **WHEN** 用户未开始录音
- **THEN** 显示"开始录音"大按钮，点击后请求麦克风权限并开始录音

#### Scenario: 录音中状态
- **WHEN** 用户开始录音后
- **THEN** 显示录音时长（格式 MM:SS）、实时转写文本区域
- **AND** 每 5 秒通过 WebSocket 发送音频 chunk 到后端
- **AND** 显示"停止并保存"和"取消录音"按钮

#### Scenario: 录音完成状态
- **WHEN** 用户点击"停止并保存"或后端发送完成信号
- **THEN** 显示完整转写文本
- **AND** 显示"返回列表"按钮

### Requirement: 页面布局

The system SHALL provide a `MeetingView.vue` page that integrates file upload and recording functionality.

#### Scenario: 正常视图
- **WHEN** 用户访问会议助手页面且未在录音
- **THEN** 显示左侧面板：文件上传区 + 录音面板 + 历史记录列表
- **AND** 显示右侧面板：转写详情

### Requirement: WebSocket 实时转写

The system SHALL connect to the backend WebSocket endpoint for real-time transcription.

#### Scenario: 连接建立
- **WHEN** 用户开始录音
- **THEN** 前端连接到 `ws://host/api/meeting/ws/record`
- **AND** 每 5 秒发送 Base64 编码的 audio chunk

#### Scenario: 接收转写
- **WHEN** 后端返回 `{"type": "transcript", "text": "..."}`
- **THEN** 将文本追加到转写区域

#### Scenario: 录音结束
- **WHEN** 用户点击"停止并保存"
- **THEN** 前端发送 `{"type": "stop"}`
- **AND** 后端返回 `{"type": "done", "transcription_id": "..."}`
- **AND** 组件进入 completed 状态

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
