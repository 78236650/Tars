const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:8000/ws');

ws.on('open', () => {
  console.log('✅ WebSocket 连接成功!');
  
  // 发送测试消息
  const msg = {
    session_id: 'node_test_' + Date.now(),
    content: '执行 github 技能'
  };
  
  console.log('发送:', JSON.stringify(msg));
  ws.send(JSON.stringify(msg));
});

ws.on('message', (data) => {
  console.log('收到:', data.toString().substring(0, 200));
});

ws.on('error', (err) => {
  console.error('❌ WebSocket 错误:', err.message);
});

ws.on('close', (code, reason) => {
  console.log(`连接关闭: ${code} - ${reason}`);
});

// 30秒后关闭
setTimeout(() => {
  ws.close();
  process.exit(0);
}, 30000);
