#!/usr/bin/env python3
"""使用 wsproto 库的 WebSocket 测试"""
import sys
sys.path.insert(0, '/Users/daobanxiang/myproject/TARS/backend')

def test_with_wsproto():
    try:
        from wsproto import WSConnection, ConnectionState
        from wsproto.extensions import PerMessageDeflate
        import ssl
    except ImportError:
        print("需要安装 wsproto: pip install wsproto")
        return
    
    print("使用 wsproto 测试 WebSocket...")
    
    # 创建 SSL 上下文
    conn = WSConnection(client=True, host='localhost', port=8000)
    
    # 建立 TCP 连接
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('localhost', 8000))
    
    # 发送握手
    request = conn.send(conn.connect())
    sock.send(request)
    
    # 接收握手响应
    response = sock.recv(4096)
    conn.receive_data(response)
    
    print(f"连接状态: {conn.state}")
    
    # 发送测试消息
    test_msg = '{"session_id": "test456", "content": "执行 github 技能"}'
    ws_msg = conn.send(conn.send_message(test_msg))
    sock.send(ws_msg)
    
    print(f"发送: {test_msg}")
    
    # 接收响应
    sock.settimeout(15)
    try:
        for i in range(20):
            data = sock.recv(8192)
            if not data:
                print("连接关闭")
                break
            conn.receive_data(data)
            for event in conn.events():
                if hasattr(event, 'data'):
                    print(f"收到消息: {event.data}")
                elif hasattr(event, 'reason'):
                    print(f"收到关闭: {event.code} - {event.reason}")
                else:
                    print(f"收到事件: {event}")
    except socket.timeout:
        print("等待响应超时")
    
    sock.close()

if __name__ == "__main__":
    test_with_wsproto()
