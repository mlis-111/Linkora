"""服务器生命周期系统测试

通过真实 TCP 连接测试服务器的启动、连接、断开和基础行为：
1. 服务器启动与客户端连接
2. 多个客户端并发连接
3. 客户端正常断开
4. 客户端异常断开（对端关闭）
5. 未知消息类型处理
6. 未登录状态下发送消息
7. 服务器高负载（频繁连接/断开）
"""

import socket
import time
import threading

import pytest
from common.protocol import send_msg, recv_msg
from common.messages import MT
from test.system.conftest import TestServer


# ════════════════════════════════════════════════════════════════
# 基础连接测试
# ════════════════════════════════════════════════════════════════

class TestServerStartup:
    """服务器启动与连接测试"""

    def test_server_starts_and_accepts_connection(self, server):
        """服务器启动后能接受客户端连接"""
        sock = server.connect()
        assert sock is not None
        # 发送一条消息确认连接正常
        server.send_dict(sock, {"type": "ping"})
        resp = server.recv_dict(sock)
        # 未注册的消息类型返回错误
        assert resp is not None
        assert resp["type"] == MT.ERROR
        server.disconnect(sock)

    def test_multiple_sequential_connections(self, server):
        """多个客户端依次连接和断开"""
        for i in range(5):
            sock = server.connect()
            server.send_dict(sock, {"type": "ping"})
            resp = server.recv_dict(sock)
            assert resp is not None
            server.disconnect(sock)

    def test_multiple_concurrent_connections(self, server):
        """多个客户端同时在线"""
        socks = []
        try:
            for i in range(10):
                sock = server.connect()
                server.send_dict(sock, {"type": "ping"})
                socks.append(sock)

            # 验证所有连接都活着
            for sock in socks:
                resp = server.recv_dict(sock)
                assert resp is not None
                assert resp["type"] == MT.ERROR  # 未知消息类型
        finally:
            for sock in socks:
                server.disconnect(sock)

    def test_server_port_is_accessible(self, server):
        """服务器端口可访问"""
        sock = socket.create_connection(("127.0.0.1", server.port), timeout=2)
        assert sock is not None
        sock.close()


# ════════════════════════════════════════════════════════════════
# 断开连接测试
# ════════════════════════════════════════════════════════════════

class TestDisconnect:
    """客户端断开连接测试"""

    def test_graceful_disconnect(self, server):
        """客户端正常关闭连接"""
        sock = server.connect()
        server.disconnect(sock)
        # 连接已关闭，发送应失败
        with pytest.raises(OSError):
            server.send_dict(sock, {"type": "ping"})

    def test_server_handles_client_crash(self, server):
        """模拟客户端崩溃（直接关闭 socket，不发送任何数据）"""
        sock = server.connect()
        # 直接关闭（不经过协议层）
        sock.close()
        # 服务器应该能继续接受新连接
        time.sleep(0.1)
        new_sock = server.connect()
        server.send_dict(new_sock, {"type": "ping"})
        resp = server.recv_dict(new_sock)
        assert resp is not None
        server.disconnect(new_sock)

    def test_half_open_connection_cleanup(self, server):
        """半开连接后服务器仍正常工作"""
        # 创建连接后立即关闭（模拟网络中断）
        sock = server.connect()
        sock.close()

        # 服务器继续接受新连接
        time.sleep(0.05)
        new_sock = server.connect()
        server.send_dict(new_sock, {"type": "ping"})
        resp = server.recv_dict(new_sock)
        assert resp is not None
        server.disconnect(new_sock)


# ════════════════════════════════════════════════════════════════
# 消息处理测试
# ════════════════════════════════════════════════════════════════

class TestMessageHandling:
    """基础消息处理系统测试"""

    def test_unknown_message_type(self, server, client):
        """未知消息类型返回错误"""
        server.send_dict(client, {"type": "completely_unknown_type"})
        resp = server.recv_dict(client)
        assert resp["type"] == MT.ERROR
        assert "未知" in resp.get("message", "") or "UNKNOWN" in resp.get("code", "")

    def test_empty_message(self, server, client):
        """空消息"""
        server.send_dict(client, {})
        resp = server.recv_dict(client)
        assert resp["type"] == MT.ERROR

    def test_message_without_type(self, server, client):
        """缺少 type 字段的消息"""
        server.send_dict(client, {"data": "no_type"})
        resp = server.recv_dict(client)
        assert resp is not None
        assert resp["type"] == MT.ERROR

    def test_large_message(self, server, client):
        """大消息传输"""
        large_content = "x" * 10000
        server.send_dict(client, {
            "type": "ping",
            "payload": large_content,
        })
        resp = server.recv_dict(client)
        assert resp is not None

    def test_unicode_message(self, server, client):
        """Unicode 消息传输"""
        server.send_dict(client, {
            "type": "ping",
            "payload": "你好世界 🌍 🎉\n\t特殊字符",
        })
        resp = server.recv_dict(client)
        assert resp is not None

    def test_multiple_messages_in_sequence(self, server, client):
        """同一连接上连续发送多条消息"""
        for i in range(20):
            server.send_dict(client, {"type": f"msg_{i}", "seq": i})

        responses = []
        for _ in range(20):
            resp = server.recv_dict(client)
            if resp:
                responses.append(resp)

        assert len(responses) == 20
        # 所有响应都应为错误（未知消息类型）
        for r in responses:
            assert r["type"] == MT.ERROR

    def test_interleaved_messages(self, server):
        """两个客户端交叉发送消息"""
        sock_a = server.connect()
        sock_b = server.connect()

        try:
            server.send_dict(sock_a, {"type": "ping_a", "n": 1})
            server.send_dict(sock_b, {"type": "ping_b", "n": 1})
            server.send_dict(sock_a, {"type": "ping_a", "n": 2})

            resp_a1 = server.recv_dict(sock_a)
            resp_b1 = server.recv_dict(sock_b)
            resp_a2 = server.recv_dict(sock_a)

            assert resp_a1 is not None
            assert resp_b1 is not None
            assert resp_a2 is not None
        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)


# ════════════════════════════════════════════════════════════════
# 并发/压力测试
# ════════════════════════════════════════════════════════════════

class TestConcurrency:
    """并发连接与高负载测试"""

    def test_rapid_connect_disconnect(self, server):
        """快速连接和断开"""
        for i in range(20):
            sock = server.connect()
            server.send_dict(sock, {"type": "ping"})
            _ = server.recv_dict(sock)
            server.disconnect(sock)

    def test_concurrent_message_flood(self, server):
        """并发发送大量消息"""
        errors = []

        def flood(tag):
            try:
                sock = server.connect()
                for i in range(10):
                    server.send_dict(sock, {"type": f"flood_{tag}", "seq": i})
                    server.recv_dict(sock)
                server.disconnect(sock)
            except Exception as e:
                errors.append((tag, str(e)))

        threads = [threading.Thread(target=flood, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"并发错误: {errors}"
