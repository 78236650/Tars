#!/usr/bin/env python3
"""使用标准库 websocket client 测试 WebSocket"""
import socket
import threading
import time
import json

def test_websocket():
    # 使用 socket 直接测试
    print("测试 WebSocket 连接...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 8000))
        sock.settimeout(5)
        
        # 发送 WebSocket 握手
        handshake = (
            "GET /ws HTTP/1.1\r\n"
            "Host: localhost:8000\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.send(handshake.encode())
        
        # 读取握手响应
        response = sock.recv(4096).decode()
        print(f"握手响应:\n{response[:200]}")
        
        if "101" in response:
            print("✅ WebSocket 握手成功!")
            
            # 发送测试消息
            test_msg = json.dumps({
                "session_id": "test123",
                "content": "执行 github 技能"
            })
            
            # WebSocket 帧格式
            payload = test_msg.encode('utf-8')
            frame = bytearray()
            frame.append(0x81)  # FIN + text frame
            frame.append(len(payload))
            frame.extend(payload)
            
            sock.send(frame)
            print(f"✅ 发送消息: {test_msg}")
            
            # 接收响应
            sock.settimeout(10)
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    print(f"收到: {data}")
            except socket.timeout:
                print("等待响应超时")
        else:
            print("❌ WebSocket 握手失败")
            
        sock.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    test_websocket()
