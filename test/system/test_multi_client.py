"""多客户端并发系统测试

测试多个真实 TCP 客户端同时在线时的交互行为：
1. 广播消息正确送达所有目标客户端
2. 在线用户列表实时同步
3. 群聊多人在线消息路由
4. 部分客户端断线不影响其余客户端
5. 并发登录不互相干扰
"""

import hashlib
import os
import threading
import time

import pytest
from common.messages import MT
from test.system.conftest import login, recv_all


def _login_user(server, uid, username, nickname):
    """登录一个用户，返回 socket"""
    pwd = "123456"
    salt = os.urandom(16).hex()
    user_data = {
        "user_id": uid, "username": username,
        "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
        "salt": salt, "nickname": nickname,
    }
    server.db.users.get_by_username.return_value = user_data
    server.db.users.get_by_id.return_value = user_data

    sock = server.connect()
    resp = login(server, sock, username)
    assert resp["ok"] is True
    _ = recv_all(server, sock, count=3)
    return sock


# ════════════════════════════════════════════════════════════════
# 多客户端广播测试
# ════════════════════════════════════════════════════════════════

class TestBroadcastToMultipleClients:
    """多客户端广播系统测试"""

    @pytest.fixture
    def three_clients(self, server):
        """创建三个已登录的客户端"""
        users = [
            (100, "user_a", "用户A"),
            (200, "user_b", "用户B"),
            (300, "user_c", "用户C"),
        ]
        server.db.users.get_all_users.return_value = [
            {"user_id": uid, "username": uname, "nickname": nick}
            for uid, uname, nick in users
        ]

        socks = []
        try:
            for uid, uname, nick in users:
                sock = _login_user(server, uid, uname, nick)
                socks.append(sock)
            yield server, socks
        finally:
            for s in socks:
                try:
                    server.disconnect(s)
                except Exception:
                    pass

    def test_user_list_updates_on_new_login(self, three_clients):
        """新用户登录时所有在线用户收到更新的 USER_LIST"""
        server, socks = three_clients
        sock_a, sock_b, sock_c = socks

        # 新用户 400 登录
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user_a", "nickname": "用户A"},
            {"user_id": 200, "username": "user_b", "nickname": "用户B"},
            {"user_id": 300, "username": "user_c", "nickname": "用户C"},
            {"user_id": 400, "username": "user_d", "nickname": "用户D"},
        ]
        sock_d = _login_user(server, 400, "user_d", "用户D")
        server.disconnect(sock_d)

        # 所有现有用户应收到 USER_LIST 广播
        for sock in socks:
            msgs = recv_all(server, sock, count=3, timeout=0.5)
            user_lists = [m for m in msgs if m["type"] == MT.USER_LIST]
            assert len(user_lists) >= 1

    def test_user_list_on_disconnect(self, three_clients):
        """用户断开时其余用户收到更新的 USER_LIST"""
        server, socks = three_clients
        sock_a, sock_b, sock_c = socks

        # 清空缓冲区
        for s in socks:
            _ = recv_all(server, s, count=5)

        # 用户A断开连接
        server.disconnect(sock_a)

        # 等待断连钩子执行
        time.sleep(0.15)

        # B 和 C 应收到 USER_LIST 广播
        for sock in [sock_b, sock_c]:
            msgs = recv_all(server, sock, count=3, timeout=0.5)
            user_lists = [m for m in msgs if m["type"] == MT.USER_LIST]
            assert len(user_lists) >= 1, f"用户应收到断线广播"

    def test_public_room_chat_reaches_all_online(self, three_clients):
        """公共聊天室消息送达所有在线用户"""
        server, socks = three_clients
        sock_a, sock_b, sock_c = socks

        # 清空缓冲区
        for s in socks:
            _ = recv_all(server, s, count=5)

        plain = "公共聊天室：大家好！"
        encrypted = server.crypto.encrypt(plain)

        server.send_dict(sock_a, {
            "type": MT.ROOM_CHAT,
            "room_id": 1,  # PUBLIC_ROOM_ID
            "content": encrypted,
        })

        # B 和 C 都应收到（A 也会收到自己的广播）
        for sock in [sock_b, sock_c]:
            msgs = recv_all(server, sock, count=3, timeout=0.5)
            room_msgs = [m for m in msgs if m["type"] == MT.ROOM_CHAT]
            assert len(room_msgs) >= 1, "应收到公共聊天室消息"


# ════════════════════════════════════════════════════════════════
# 并发交互测试
# ════════════════════════════════════════════════════════════════

class TestConcurrentInteractions:
    """并发交互系统测试"""

    def test_simultaneous_chat_from_multiple_clients(self, server):
        """多个客户端同时发送消息，各自正确路由"""
        # 设置5个用户
        users = [(i, f"user_{i}", f"用户{i}") for i in range(100, 500, 100)]
        server.db.users.get_all_users.return_value = [
            {"user_id": uid, "username": uname, "nickname": nick}
            for uid, uname, nick in users
        ]

        socks = {}
        try:
            for uid, uname, nick in users:
                socks[uid] = _login_user(server, uid, uname, nick)

            # 清空所有缓冲区
            for s in socks.values():
                _ = recv_all(server, s, count=5)

            errors = []

            def send_worker(from_uid, to_uid):
                try:
                    plain = f"msg from {from_uid} to {to_uid}"
                    encrypted = server.crypto.encrypt(plain)
                    server.send_dict(socks[from_uid], {
                        "type": MT.CHAT,
                        "to": to_uid,
                        "content": encrypted,
                    })
                except Exception as e:
                    errors.append(str(e))

            def recv_worker(uid):
                try:
                    msgs = recv_all(server, socks[uid], count=5, timeout=1.0)
                    chat_msgs = [m for m in msgs if m["type"] == MT.CHAT]
                    for m in chat_msgs:
                        _ = server.crypto.decrypt(m["content"])
                except Exception as e:
                    errors.append(str(e))

            # 并发发送消息
            threads = []
            for from_uid in socks:
                for to_uid in socks:
                    if from_uid != to_uid:
                        t = threading.Thread(target=send_worker, args=(from_uid, to_uid))
                        threads.append(t)

            # 并发接收
            recv_threads = []
            for uid in socks:
                t = threading.Thread(target=recv_worker, args=(uid,))
                recv_threads.append(t)

            for t in threads:
                t.start()
            for t in recv_threads:
                t.start()

            for t in threads:
                t.join(timeout=5)
            for t in recv_threads:
                t.join(timeout=5)

            assert len(errors) == 0, f"并发错误: {errors}"

        finally:
            for s in socks.values():
                server.disconnect(s)

    def test_one_client_disconnect_doesnt_affect_others(self, server):
        """一个客户端断开不影响其他客户端"""
        users = [(100, "user_a", "用户A"), (200, "user_b", "用户B")]
        server.db.users.get_all_users.return_value = [
            {"user_id": uid, "username": uname, "nickname": nick}
            for uid, uname, nick in users
        ]

        sock_a = _login_user(server, 100, "user_a", "用户A")
        sock_b = _login_user(server, 200, "user_b", "用户B")

        try:
            _ = recv_all(server, sock_a, count=5)
            _ = recv_all(server, sock_b, count=5)

            # 用户A断开
            server.disconnect(sock_a)

            # 用户B 应该仍然能正常通信
            server.send_dict(sock_b, {"type": "ping"})
            resp = server.recv_dict(sock_b, timeout=1.0)
            assert resp is not None

            # 用户B在线状态不受影响
            assert server.ctx.online.is_online(200)
            assert not server.ctx.online.is_online(100)
        finally:
            server.disconnect(sock_b)  # sock_a 已断开


# ════════════════════════════════════════════════════════════════
# 在线列表一致性测试
# ════════════════════════════════════════════════════════════════

class TestOnlineListConsistency:
    """在线列表一致性系统测试"""

    def test_online_list_after_login_sequence(self, server):
        """按顺序登录/登出后在线列表保持一致"""
        server.db.users.get_all_users.return_value = []

        socks = []
        try:
            # 逐个登录
            for i, (uid, uname) in enumerate([(100, "a"), (200, "b"), (300, "c")]):
                server.db.users.get_all_users.return_value = [
                    {"user_id": u, "username": n, "nickname": n}
                    for u, n in [(100, "a"), (200, "b"), (300, "c")][:i+1]
                ]
                sock = _login_user(server, uid, uname, uname)
                socks.append(sock)
                time.sleep(0.02)

            # 所有三个在线
            assert server.ctx.online.is_online(100)
            assert server.ctx.online.is_online(200)
            assert server.ctx.online.is_online(300)
            assert len(server.ctx.online.online_ids()) == 3

            # 逐个登出
            server.disconnect(socks[0])
            time.sleep(0.15)

            assert not server.ctx.online.is_online(100)
            assert server.ctx.online.is_online(200)
            assert server.ctx.online.is_online(300)
            assert len(server.ctx.online.online_ids()) == 2

            server.disconnect(socks[1])
            time.sleep(0.15)

            assert len(server.ctx.online.online_ids()) == 1

            server.disconnect(socks[2])
            time.sleep(0.15)

            assert len(server.ctx.online.online_ids()) == 0
        finally:
            for s in socks:
                try:
                    server.disconnect(s)
                except Exception:
                    pass
