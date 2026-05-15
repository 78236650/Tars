# Tasks

- [ ] Task 1: 定义 reminder 通知数据模型与存储接口
  - [ ] SubTask 1.1: 梳理现有 `cronjobs` / `CronRuntime` / WebSocket 提醒链路，确定通知事件最小字段集
  - [ ] SubTask 1.2: 为 reminder 通知记录设计持久化方案与读写接口
  - [ ] SubTask 1.3: 明确已读状态、列表查询、详情查询的数据返回结构

- [ ] Task 2: 补齐后端 reminder 通知记录与验证接口
  - [ ] SubTask 2.1: 在 reminder 执行时写入通知事件与关键摘要日志
  - [ ] SubTask 2.2: 提供通知列表、通知详情、标记已读接口
  - [ ] SubTask 2.3: 在 cronjob 查询结果中补充最近通知状态或等价验证字段
  - [ ] SubTask 2.4: 为兼容广播路径和投递失败路径定义状态与错误说明

- [ ] Task 3: 新增聊天页右上角铃铛通知入口
  - [ ] SubTask 3.1: 在现有聊天页头部加入铃铛 icon 与未读标记
  - [ ] SubTask 3.2: 实现通知列表弹层、抽屉或等价轻量容器
  - [ ] SubTask 3.3: 接入通知列表 API，并支持查看详情与已读更新

- [ ] Task 4: 实现提醒详情摘要日志展示
  - [ ] SubTask 4.1: 设计详情面板最小字段：任务名、提醒内容、触发时间、目标会话、投递状态
  - [ ] SubTask 4.2: 展示关键链路日志摘要，不扩展为完整业务流时间线
  - [ ] SubTask 4.3: 明确失败状态、兼容广播状态、无日志状态的空态与提示文案

- [ ] Task 5: 保持聊天内 reminder 展示并补齐前端状态联动
  - [ ] SubTask 5.1: 保留现有 `cron_reminder` 系统消息展示
  - [ ] SubTask 5.2: reminder 到达时同步刷新通知列表或未读计数
  - [ ] SubTask 5.3: 确认切换会话时通知中心不丢失最近提醒记录

- [ ] Task 6: 增加验证与回归测试
  - [ ] SubTask 6.1: 增加后端测试，覆盖 reminder 通知事件写入、列表查询、详情查询、兼容广播路径
  - [ ] SubTask 6.2: 增加前端测试或最小可验证用例，覆盖铃铛入口、未读态、通知详情展示
  - [ ] SubTask 6.3: 增加端到端手动验证步骤，确认“创建 reminder -> 到点触发 -> 铃铛通知出现 -> 可查看详情摘要”

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 2
- Task 5 depends on Task 3
- Task 6 depends on Task 2, Task 3, Task 4, Task 5
