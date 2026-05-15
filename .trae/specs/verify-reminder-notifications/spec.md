# 定时提醒通知验证 Spec

## Why
当前定时任务的 `reminder` 已能在到点时投递到聊天会话，但用户只能在聊天消息流中被动看到一条系统消息，缺少专门的通知入口、可复查的提醒详情，以及用于验证“任务是否真的执行”的摘要日志。需要补齐一个最小可用的提醒通知体验，方便确认定时任务是否正常工作，并为后续更复杂的任务链路展示留出清晰边界。

## What Changes
- 新增右上角铃铛通知入口，用于显示当前用户收到的定时提醒通知
- 新增提醒通知列表与未读状态，支持查看最近收到的 reminder
- 新增提醒详情视图，展示任务名、提醒内容、触发时间、投递结果和关键摘要日志
- 新增 reminder 通知事件的持久化存储，避免只靠 WebSocket 瞬时消息
- 新增 reminder 验证与排障接口，用于确认任务是否按时执行、是否成功投递
- 保留现有聊天流中的 `cron_reminder` 系统消息，作为兼容展示
- 不扩展到任意业务流的完整执行链路展示；该能力留待后续规格

## Impact
- Affected specs: 定时任务执行、WebSocket 提醒投递、聊天页通知入口、提醒详情查看、执行验证与日志摘要
- Affected code: `backend/tars/cron/runtime.py`、`backend/tars/database/base.py`、`backend/tars/main.py`、`frontend/src/views/ChatView.vue`、新增通知相关 store / 组件 / API 封装

## ADDED Requirements
### Requirement: 提供独立的提醒通知入口
系统 SHALL 在聊天页右上角提供铃铛图标，作为定时提醒通知的统一入口。

#### Scenario: 聊天页显示通知入口
- **WHEN** 用户进入聊天页
- **THEN** 页面右上角显示铃铛图标
- **THEN** 当存在未读 reminder 通知时，铃铛显示未读数量或红点

### Requirement: 持久化 reminder 通知事件
系统 SHALL 在 reminder 实际触发并进入投递流程时记录一条通知事件，供后续列表、详情和验证使用。

#### Scenario: reminder 成功进入投递流程
- **WHEN** `CronRuntime` 执行一个 `task_type=reminder` 的定时任务
- **THEN** 系统创建一条 reminder 通知记录
- **THEN** 记录至少包含 `job_id`、`session_id`、任务名称、提醒内容、触发时间、投递状态

#### Scenario: reminder 缺少 session_id
- **WHEN** 老 reminder 任务缺少 `session_id`
- **THEN** 系统仍记录一条通知事件
- **THEN** 详情中标记为“兼容广播路径”或等价状态，便于排障

### Requirement: 提供提醒通知列表
系统 SHALL 支持用户查看最近收到的 reminder 通知列表，而不依赖聊天消息历史是否仍在当前窗口中。

#### Scenario: 打开通知列表
- **WHEN** 用户点击右上角铃铛
- **THEN** 页面展示最近通知列表，按触发时间倒序排列
- **THEN** 每条通知至少显示任务名、提醒内容摘要、触发时间、已读状态

### Requirement: 提供提醒详情摘要日志
系统 SHALL 支持用户查看单条 reminder 的关键验证信息，用于判断该定时任务是否正常工作。

#### Scenario: 查看提醒详情
- **WHEN** 用户在通知列表中点击一条 reminder
- **THEN** 页面展示该通知详情
- **THEN** 详情至少包含任务名、提醒内容、计划触发时间或实际触发时间、投递目标会话、投递结果、关键摘要日志

#### Scenario: 摘要日志最小范围
- **WHEN** 系统生成 reminder 详情日志
- **THEN** 摘要日志仅覆盖本次 reminder 的关键链路节点
- **THEN** 节点至少包括“调度命中 / runtime 执行 / 通知记录写入 / websocket 投递尝试 / 投递结果”

### Requirement: 保持现有聊天内提醒展示
系统 SHALL 在新增通知中心后继续保留聊天消息流中的 reminder 展示，避免影响当前使用习惯。

#### Scenario: reminder 到点触发
- **WHEN** reminder 发送到当前聊天会话
- **THEN** 聊天消息流仍显示 `cron_reminder` 系统消息
- **THEN** 同一事件同时可在通知中心中查看

### Requirement: 提供 reminder 验证能力
系统 SHALL 提供明确的验证路径，让用户或开发者能够确认 reminder 是否已执行、是否已投递、是否已展示。

#### Scenario: 验证任务是否正常工作
- **WHEN** 用户查看某个 cronjob 或其 reminder 通知
- **THEN** 系统能给出最近一次执行时间、下一次执行时间、最近一条通知状态
- **THEN** 出现失败或兼容广播时，系统能展示可读的失败原因或状态说明

## MODIFIED Requirements
### Requirement: 现有提醒展示方式
系统当前仅在聊天消息流中追加 `cron_reminder` 系统消息。修改后，系统必须同时提供“聊天流展示 + 通知中心展示”两条可见路径，其中通知中心作为主要验证入口，聊天流作为兼容展示。

## REMOVED Requirements
### Requirement: 将提醒验证完全依赖聊天消息流
**Reason**: 聊天消息流不适合承载提醒通知列表、未读状态和执行验证信息，用户切换会话或刷新后也难以回查。
**Migration**: 现有聊天内 `cron_reminder` 继续保留；新增通知中心作为标准查看和排障入口。
