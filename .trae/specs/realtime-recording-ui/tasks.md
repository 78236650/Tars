# Tasks

## 前端组件

- [x] **Task 1: RecordingPanel 组件状态机**
  - [x] SubTask 1.1: 实现 idle 状态：显示"开始录音"大按钮
  - [x] SubTask 1.2: 实现 recording 状态：录音时长 + 实时转写 + 停止/取消按钮
  - [x] SubTask 1.3: 实现 completed 状态：完整转写 + 返回按钮
  - [x] SubTask 1.4: 处理错误状态和清理逻辑（onBeforeUnmount）

- [x] **Task 2: RecordingPanel WebSocket 集成**
  - [x] SubTask 2.1: 实现麦克风权限获取（getUserMedia）
  - [x] SubTask 2.2: 实现 MediaRecorder 音频采集
  - [x] SubTask 2.3: 实现 WebSocket 连接和数据发送
  - [x] SubTask 2.4: 处理 WebSocket 消息（transcript、done、error）
  - [x] SubTask 2.5: 实现停止和取消逻辑

- [x] **Task 3: MeetingView 页面整合**
  - [x] SubTask 3.1: 添加 RecordingPanel 到页面布局
  - [x] SubTask 3.2: 处理录音完成事件，刷新历史列表
  - [x] SubTask 3.3: 处理录音保存事件，选中新建记录

# Task Dependencies

- Task 3 depends on Task 1, Task 2（页面整合需要组件完成）

# Parallelizable Work

- Task 1, Task 2 可并行开发（独立的状态和 WebSocket 逻辑）
