"""端到端测试 web_search 通过 WebSocket"""
import asyncio
import json
import websockets
import uuid

WS_URL = "ws://localhost:8000/ws"

async def test_web_search():
    session_id = str(uuid.uuid4())
    
    async with websockets.connect(WS_URL) as ws:
        user_msg = {
            "type": "chat",
            "user_id": "test-user",
            "session_id": session_id,
            "content": "帮我搜索一下今天的中国央行利率是多少",
            "file_ids": [],
        }
        
        print(f"→ 发送: {user_msg['content']}")
        await ws.send(json.dumps(user_msg))
        
        received_events = []
        done = False
        
        while not done:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                event = json.loads(raw)
                event_type = event.get("type", "?")
                
                if event_type == "text_chunk":
                    print(event.get("content", ""), end="", flush=True)
                elif event_type == "tool_call":
                    print(f"\n🔧 [{event_type}] {event.get('tool_name')} args={event.get('arguments')}")
                elif event_type == "tool_result":
                    output = event.get("output", "")
                    print(f"📋 [{event_type}] {event.get('tool_name')}: {output[:200]}...")
                elif event_type == "thinking_step":
                    print(f"💭 [{event_type}] {event.get('title')}")
                elif event_type == "done":
                    print(f"\n✅ [done]")
                    done = True
                elif event_type == "error":
                    print(f"\n❌ [error] {event.get('message')}")
                    done = True
                else:
                    print(f"[{event_type}]", end="", flush=True)
                
                received_events.append(event)
                
            except asyncio.TimeoutError:
                print("\n⏰ 超时 (30s)")
                done = True
            except Exception as e:
                print(f"\n❌ 错误: {e}")
                done = True
        
        print(f"\n收到 {len(received_events)} 个事件")
        
        # 检查是否调用了 web_search
        tool_calls = [e for e in received_events if e.get("type") == "tool_call"]
        tool_results = [e for e in received_events if e.get("type") == "tool_result"]
        text_chunks = [e for e in received_events if e.get("type") == "text_chunk"]
        
        print(f"工具调用: {len(tool_calls)}")
        print(f"工具结果: {len(tool_results)}")
        print(f"文本块: {len(text_chunks)}")
        
        if not tool_calls:
            print("❌ LLM 没有调用 web_search 工具！")
            return False
        if not tool_results:
            print("❌ 工具调用后没有返回结果！")
            return False
        if not text_chunks:
            print("⚠️ LLM 没有生成基于搜索结果的文本回复")
            return False
        
        print("✅ web_search 端到端测试通过")
        return True

if __name__ == "__main__":
    result = asyncio.run(test_web_search())
    exit(0 if result else 1)
