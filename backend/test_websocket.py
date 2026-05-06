#!/usr/bin/env python3
"""WebSocket 测试客户端"""
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws"
    print(f"连接到 {uri}...")
    
    try:
        async with websockets.connect(uri) as ws:
            print("✅ WebSocket 连接成功!")
            
            # 发送测试消息
            test_messages = [
                "执行 github 技能",
                "查询天气",
                "你好",
            ]
            
            for msg in test_messages:
                print(f"\n发送: {msg}")
                await ws.send(json.dumps({
                    "session_id": "test123",
                    "content": msg
                }))
                
                # 接收响应
                try:
                    for _ in range(5):  # 最多接收5条消息
                        response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        data = json.loads(response)
                        print(f"收到: {data.get('type')} - {data.get('content', data.get('message', ''))[:100]}...")
                except asyncio.TimeoutError:
                    print("⏱️ 等待响应超时")
                    
            print("\n测试完成!")
            
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    asyncio.run(test())
