#!/usr/bin/env python3
"""
测试 TARS Agent WebSocket 连接
"""
import asyncio
import websockets
import json
from datetime import datetime


async def test_agent():
    """测试 Agent 天气查询"""
    uri = "ws://localhost:8000/ws"
    
    print("=" * 60)
    print("TARS Agent 测试 - 天气查询")
    print("=" * 60)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("\n✅ 已连接到 TARS Agent")
            
            # 发送天气查询消息
            message = {
                "type": "chat",
                "content": "明天上海天气情况怎么样",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"\n📤 发送消息: {message['content']}")
            await websocket.send(json.dumps(message))
            
            # 接收响应
            print("\n📥 接收响应:")
            print("-" * 60)
            
            full_response = ""
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "text_chunk":
                        chunk = data.get("content", "")
                        print(chunk, end="", flush=True)
                        full_response += chunk
                    elif data.get("type") == "done":
                        print("\n" + "-" * 60)
                        print("✅ 响应完成")
                        break
                    elif data.get("type") == "error":
                        print(f"\n❌ 错误: {data.get('message')}")
                        break
                    else:
                        # 其他类型的消息
                        print(f"\n[消息类型: {data.get('type')}]")
                        
                except asyncio.TimeoutError:
                    print("\n⏱️ 响应超时")
                    break
                    
            print("\n" + "=" * 60)
            print("测试完成")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_agent())
