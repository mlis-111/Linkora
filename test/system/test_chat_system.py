"""聊天模块系统测试

通过真实 TCP 连接测试完整的聊天流程：
1. 私聊：加密发送 → 服务器解密入库 → 转发密文给接收方
2. 群聊：成员校验 → 广播
3. 公共聊天室广播
4. 历史记录查询（加密返回）
5. 离线消息提示
6. 多客户端在线消息路由
"""

import hashlib
import os
import time

import pytest
from common.messages import MT, PUBLIC_ROOM_ID
from test.system.conftest import login, recv_all


# ════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════

def _setup_two_users(server, uid_a=100, uid_b=200):
    """在 mock DB 中设置两个用户并登录，返回 (sock_a, sock_b)"""
    pwd = "123456"
    server.db.users.get_all_users.return_value = [
        {"user_id": uid_a, "username": "user_a", "nickname": "用户A"},
        {"user_id": uid_b, "username": "user_b", "nickname": "用户B"},
    ]

    users = {}
    for uid, uname in [(uid_a, "user_a"), (uid_b, "user_b")]:
        salt = os.urandom(16).hex()
        users[uid] = {
            "user_id": uid, "username": uname,
            "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
            "salt": salt, "nickname": f"用户{chr(65 + uid - 100)}",
        }

    sock_a = server.connect()
    sock_b = server.connect()

    # 用户A登录
    server.db.users.get_by_username.return_value = users[uid_a]
    server.db.users.get_by_id.return_value = users[uid_a]
    resp_a = login(server, sock_a, "user_a")
    assert resp_a["ok"] is True

    # 清空用户A的广播缓冲区
    _ = recv_all(server, sock_a, count=3)

    # 用户B登录
    server.db.users.get_by_username.return_value = users[uid_b]
    server.db.users.get_by_id.return_value = users[uid_b]
    resp_b = login(server, sock_b, "user_b")
    assert resp_b["ok"] is True

    _ = recv_all(server, sock_b, count=3)

    return sock_a, sock_b


# ════════════════════════════════════════════════════════════════
# 私聊系统测试
# ════════════════════════════════════════════════════════════════

class TestPrivateChatSystem:
    """私聊完整系统测试"""

    def test_chat_message_delivered(self, server):
        """加密消息从发送方经过服务器到达接收方"""
        sock_a, sock_b = _setup_two_users(server)

        try:
            plain = "你好，这是一条私聊消息！"
            encrypted = server.crypto.encrypt(plain)

            # A 发送给 B
            server.send_dict(sock_a, {
                "type": MT.CHAT,
                "to": 200,
                "content": encrypted,
                "ts": 1234567890,
            })

            # B 收到消息
            received = server.recv_dict(sock_b)
            assert received is not None
            assert received["type"] == MT.CHAT
            assert received["from"] == 100
            assert received["to"] == 200

            # B 解密成功
            decrypted = server.crypto.decrypt(received["content"])
            assert decrypted == plain

            # 验证服务器入库了明文
            server.db.messages.insert.assert_called_with(
                1, 100, 200, None, plain
            )
        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)

    def test_chat_message_not_leaked_to_others(self, server):
        """私聊消息不会送达第三方"""
        sock_a, sock_b = _setup_two_users(server)
        sock_c = server.connect()

        try:
            # 第三个用户登录
            salt = os.urandom(16).hex()
            pwd = "123456"
            server.db.users.get_by_username.return_value = {
                "user_id": 300, "username": "user_c",
                "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
                "salt": salt, "nickname": "用户C",
            }
            server.db.users.get_by_id.return_value = {
                "user_id": 300, "username": "user_c", "nickname": "用户C",
            }
            server.db.users.get_all_users.return_value = [
                {"user_id": 100, "username": "user_a", "nickname": "用户A"},
                {"user_id": 200, "username": "user_b", "nickname": "用户B"},
                {"user_id": 300, "username": "user_c", "nickname": "用户C"},
            ]
            login(server, sock_c, "user_c")
            # 清空所有登录广播
            _ = recv_all(server, sock_c, count=5, timeout=0.5)

            # 也清空 A 和 B 可能收到的广播
            _ = recv_all(server, sock_a, count=2, timeout=0.2)
            _ = recv_all(server, sock_b, count=2, timeout=0.2)

            encrypted = server.crypto.encrypt("secret to B")

            # A 发给 B
            server.send_dict(sock_a, {
                "type": MT.CHAT, "to": 200, "content": encrypted,
            })

            # B 收到
            received_b = server.recv_dict(sock_b)
            assert received_b is not None
            assert received_b["type"] == MT.CHAT

            # C 不应收到任何私聊消息
            extra = recv_all(server, sock_c, count=2, timeout=0.3)
            chat_to_c = [m for m in extra if m["type"] == MT.CHAT]
            assert len(chat_to_c) == 0
        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)
            server.disconnect(sock_c)

    def test_chat_offline_receiver_notification(self, server):
        """接收方不在线时，发送方收到通知"""
        server.setup_user(uid=100)
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user_a", "nickname": "用户A"},
        ]

        sock_a = server.connect()
        login(server, sock_a, "user_a")
        _ = recv_all(server, sock_a, count=3)

        try:
            # 发送给不在线的用户 200
            encrypted = server.crypto.encrypt("hello offline")
            server.send_dict(sock_a, {
                "type": MT.CHAT, "to": 200, "content": encrypted,
            })

            # 收到多个响应（OFFLINE 错误 + 可能其他消息）
            responses = recv_all(server, sock_a, count=3)
            error_msgs = [r for r in responses if r["type"] == MT.ERROR]
            assert len(error_msgs) >= 1
            assert "不在线" in error_msgs[0].get("message", "")
        finally:
            server.disconnect(sock_a)


# ════════════════════════════════════════════════════════════════
# 群聊系统测试
# ════════════════════════════════════════════════════════════════

class TestRoomChatSystem:
    """群聊系统测试"""

    def test_room_chat_broadcast_to_members(self, server):
        """群聊消息广播给所有在线群成员"""
        sock_a, sock_b = _setup_two_users(server)

        try:
            server.db.groups.get_by_id.return_value = {
                "group_id": 2, "group_name": "测试群组", "owner_id": 100,
            }
            server.db.groups.is_member.return_value = True
            server.db.groups.list_member_ids.return_value = [100, 200]

            plain = "群聊消息！"
            encrypted = server.crypto.encrypt(plain)

            server.send_dict(sock_a, {
                "type": MT.ROOM_CHAT,
                "room_id": 2,
                "content": encrypted,
            })

            # A 发送者也会收到广播... 不，群聊广播给所有群成员
            # broadcast_to 发送给 member_ids 中的所有在线用户
            # 由于 A 在线，A 也会收到自己的广播
            msgs_a = recv_all(server, sock_a, count=2, timeout=0.3)
            msgs_b = recv_all(server, sock_b, count=2, timeout=0.3)

            # B 收到群聊消息
            room_msgs_b = [m for m in msgs_b if m["type"] == MT.ROOM_CHAT]
            assert len(room_msgs_b) >= 1

            # 解密验证
            decrypted = server.crypto.decrypt(room_msgs_b[0]["content"])
            assert decrypted == plain
        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)

    def test_public_room_broadcast_to_all(self, server):
        """公共聊天室广播给所有在线用户"""
        sock_a, sock_b = _setup_two_users(server)

        try:
            plain = "公共聊天室消息"
            encrypted = server.crypto.encrypt(plain)

            server.send_dict(sock_a, {
                "type": MT.ROOM_CHAT,
                "room_id": PUBLIC_ROOM_ID,
                "content": encrypted,
            })

            # 公共聊天室用 broadcast()，发给所有在线用户
            msgs_b = recv_all(server, sock_b, count=3, timeout=0.5)
            room_msgs = [m for m in msgs_b if m["type"] == MT.ROOM_CHAT]
            assert len(room_msgs) >= 1
        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)

    def test_non_member_cannot_send_to_room(self, server):
        """非群成员不能发送群聊消息"""
        server.setup_user()
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "testuser", "nickname": "测试用户"},
        ]

        sock = server.connect()
        login(server, sock)
        _ = recv_all(server, sock, count=3)

        try:
            server.db.groups.get_by_id.return_value = {
                "group_id": 2, "group_name": "私密群", "owner_id": 200,
            }
            server.db.groups.is_member.return_value = False

            server.send_dict(sock, {
                "type": MT.ROOM_CHAT,
                "room_id": 2,
                "content": "尝试发消息到非成员群",
            })

            resp = server.recv_dict(sock)
            assert resp["type"] == MT.ERROR
            assert "成员" in resp.get("message", "")
        finally:
            server.disconnect(sock)


# ════════════════════════════════════════════════════════════════
# 历史记录系统测试
# ════════════════════════════════════════════════════════════════

class TestHistorySystem:
    """历史记录查询系统测试"""

    def test_p2p_history_encrypted(self, server):
        """查询私聊历史，返回加密内容"""
        server.setup_user()
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "testuser", "nickname": "测试用户"},
        ]

        sock = server.connect()
        login(server, sock)
        _ = recv_all(server, sock, count=3)

        try:
            server.db.messages.query_p2p.return_value = [
                {"sender_id": 100, "receiver_id": 200,
                 "content": "历史消息1", "sent_at": "2024-01-01 10:00:00"},
                {"sender_id": 200, "receiver_id": 100,
                 "content": "历史消息2", "sent_at": "2024-01-01 10:01:00"},
            ]

            server.send_dict(sock, {
                "type": MT.HISTORY_REQ,
                "scope": "p2p",
                "target": 200,
            })

            resp = server.recv_dict(sock)
            assert resp["type"] == MT.HISTORY_RESP
            assert resp["scope"] == "p2p"
            assert len(resp["records"]) == 2

            # 内容被加密
            for record in resp["records"]:
                decrypted = server.crypto.decrypt(record["content"])
                assert decrypted in ("历史消息1", "历史消息2")
        finally:
            server.disconnect(sock)

    def test_empty_history(self, server):
        """无历史记录返回空列表"""
        server.setup_user()
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "testuser", "nickname": "测试用户"},
        ]

        sock = server.connect()
        login(server, sock)
        _ = recv_all(server, sock, count=3)

        try:
            server.db.messages.query_p2p.return_value = []

            server.send_dict(sock, {
                "type": MT.HISTORY_REQ,
                "scope": "p2p",
                "target": 200,
            })

            resp = server.recv_dict(sock)
            assert resp["type"] == MT.HISTORY_RESP
            assert len(resp["records"]) == 0
        finally:
            server.disconnect(sock)
