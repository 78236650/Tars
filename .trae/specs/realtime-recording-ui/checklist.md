# Checklist

## RecordingPanel 组件

- [x] idle 状态显示"开始录音"大按钮
- [x] recording 状态显示录音时长（MM:SS 格式）
- [x] recording 状态显示实时转写文本区域
- [x] recording 状态显示"停止并保存"按钮
- [x] recording 状态显示"取消录音"按钮
- [x] completed 状态显示完整转写文本
- [x] completed 状态显示"返回列表"按钮
- [x] 错误时显示错误消息

## WebSocket 集成

- [x] 正确连接到 `ws://host/api/meeting/ws/record`
- [x] 使用 `audio/webm;codecs=opus` MIME 类型
- [x] 每 5 秒发送 audio chunk（Base64 编码）
- [x] 正确处理 `{"type": "transcript"}` 消息
- [x] 正确处理 `{"type": "done"}` 消息
- [x] 正确处理 `{"type": "error"}` 消息
- [x] 停止时发送 `{"type": "stop"}`
- [x] 组件卸载时正确清理资源

## MediaRecorder

- [x] 正确请求麦克风权限
- [x] 停止时释放音频轨道
- [x] WebSocket 关闭时清理 MediaRecorder

## MeetingView 页面

- [x] RecordingPanel 正确集成到页面
- [x] 录音完成事件正确触发历史列表刷新
- [x] 录音保存后正确选中新建记录

## 样式

- [x] idle 状态按钮样式：红色边框、白色背景
- [x] recording 状态样式：红色背景面板、闪烁录音指示器
- [x] completed 状态样式：绿色背景面板
- [x] 转写区域滚动显示最新内容
