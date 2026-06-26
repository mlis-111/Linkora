"""完整用户旅程系统测试

测试从注册到日常使用的完整用户路径，全部通过真实 TCP 连接：
1. 注册 → 登录 → 加好友 → 聊天 → 登出
2. 新用户注册完整流程
3. 好友生命周期：搜索 → 申请 → 同意 → 聊天 → 删除
4. 群组生命周期：创建 → 加入 → 聊天 → 离开
5. 登录会话恢复
"""

import hashlib
import os
import time

import pytest
from common.messages import MT
from test.system.conftest import login, recv_all, register


# ════════════════════════════════════════════════════════════════
# 完整端到端用户旅程
# ════════════════════════════════════════════════════════════════

class TestEndToEndJourney:
    """完整端到端用户旅程"""

    def test_register_login_chat_logout(self, server):
        """新用户：注册 → 登录 → 聊天 → 登出"""
        # === Phase 1: 注册 ===
        server.db.users.exists.return_value = False
        server.db.users.insert_user.return_value = 100

        sock = server.connect()

        resp = register(server, sock, "newuser", "mypassword", "新用户")
        assert resp["type"] == MT.REGISTER_RESP
        assert resp["ok"] is True
        server.db.users.insert_user.assert_called_once()

        # === Phase 2: 登录 ===
        server.setup_user(username="newuser", password="mypassword", nickname="新用户")
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "newuser", "nickname": "新用户"},
        ]

        login_resp = login(server, sock, "newuser", "mypassword")
        assert login_resp["ok"] is True
        assert login_resp["user_id"] == 100
        assert login_resp["nickname"] == "新用户"
        assert server.ctx.online.is_online(100)

        # 清空登录后的广播缓冲
        _ = recv_all(server, sock, count=5, timeout=0.5)

        # === Phase 3: 查询历史（空） ===
        server.db.messages.query_p2p.return_value = []
        server.send_dict(sock, {
            "type": MT.HISTORY_REQ,
            "scope": "p2p",
            "target": 200,
        })
        hist_resp = server.recv_dict(sock)
        assert hist_resp is not None
        assert hist_resp["type"] == MT.HISTORY_RESP
        assert len(hist_resp["records"]) == 0

        # === Phase 4: 发私聊消息 ===
        # 添加接收方到在线表
        from unittest.mock import MagicMock
        target_handler = MagicMock()
        target_handler.send = MagicMock()
        target_handler.conn = MagicMock()
        server.ctx.online.add(200, target_handler)

        plain = "你好，我的第一条消息！"
        encrypted = server.crypto.encrypt(plain)
        server.send_dict(sock, {
            "type": MT.CHAT,
            "to": 200,
            "content": encrypted,
        })

        # 等待服务器线程处理完成
        time.sleep(0.1)

        # 消息入库
        server.db.messages.insert.assert_called_with(1, 100, 200, None, plain)

        # === Phase 5: 登出 ===
        server.send_dict(sock, {"type": MT.LOGOUT})
        time.sleep(0.1)

        assert not server.ctx.online.is_online(100)

        server.disconnect(sock)

    def test_two_users_full_interaction(self, server):
        """两个用户完整交互：注册→登录→加好友→聊天→删好友"""
        pwd = "123456"

        # === 设置用户A ===
        server.db.users.exists.return_value = False
        server.db.users.insert_user.return_value = 100

        # === 用户A注册并登录 ===
        sock_a = server.connect()
        register(server, sock_a, "user_a", pwd, "用户A")

        salt_a = os.urandom(16).hex()
        user_a = {
            "user_id": 100, "username": "user_a",
            "password_hash": hashlib.sha256((salt_a + pwd).encode()).hexdigest(),
            "salt": salt_a, "nickname": "用户A",
        }
        server.db.users.get_by_username.return_value = user_a
        server.db.users.get_by_id.return_value = user_a
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user_a", "nickname": "用户A"},
        ]

        login(server, sock_a, "user_a")
        _ = recv_all(server, sock_a, count=5, timeout=0.5)

        # === 用户B注册并登录 ===
        server.db.users.insert_user.return_value = 200
        sock_b = server.connect()
        register(server, sock_b, "user_b", pwd, "用户B")

        salt_b = os.urandom(16).hex()
        user_b = {
            "user_id": 200, "username": "user_b",
            "password_hash": hashlib.sha256((salt_b + pwd).encode()).hexdigest(),
            "salt": salt_b, "nickname": "用户B",
        }
        server.db.users.get_by_username.return_value = user_b
        server.db.users.get_by_id.return_value = user_b
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user_a", "nickname": "用户A"},
            {"user_id": 200, "username": "user_b", "nickname": "用户B"},
        ]

        login(server, sock_b, "user_b")
        _ = recv_all(server, sock_b, count=5, timeout=0.5)

        # 清空 A 收到的广播（B 登录触发的 USER_LIST）
        _ = recv_all(server, sock_a, count=5, timeout=0.5)

        try:
            # === A搜索B ===
            server.db.users.get_by_id.return_value = user_b
            server.db.friends.list_by_user.return_value = []

            server.send_dict(sock_a, {
                "type": MT.USER_SEARCH,
                "target_id": "200",
            })
            search_resp = server.recv_dict(sock_a)
            assert search_resp["type"] == MT.USER_SEARCH_RESP
            assert search_resp["ok"] is True
            assert search_resp["user"]["user_id"] == 200

            # === A申请添加B为好友 ===
            server.db.friends.list_by_user.return_value = []
            server.db.friend_requests.find_reverse_pending.return_value = None
            server.db.friend_requests.create.return_value = 1

            server.send_dict(sock_a, {
                "type": MT.FRIEND_ADD,
                "target_id": "200",
                "message": "交个朋友吧！",
            })
            add_resp = server.recv_dict(sock_a)
            assert add_resp["type"] == MT.FRIEND_ADD_RESP
            assert add_resp["ok"] is True

            # B 收到好友申请通知
            b_notifications = recv_all(server, sock_b, count=3)
            friend_req = [m for m in b_notifications
                         if m["type"] == MT.FRIEND_REQ_NOTIFY]
            assert len(friend_req) >= 1
            assert friend_req[0]["from_id"] == 100

            # === B同意申请 ===
            server.db.friend_requests.find_pending.return_value = {
                "id": 1, "from_id": 100,
            }
            server.db.users.get_by_id.return_value = user_a
            server.db.friends.list_by_user.return_value = [
                {"user_id": 100, "username": "user_a", "remark": ""},
            ]

            server.send_dict(sock_b, {
                "type": MT.FRIEND_AGREE,
                "from_id": 100,
            })
            agree_resp = server.recv_dict(sock_b)
            assert agree_resp["type"] == MT.FRIEND_AGREE_RESP
            assert agree_resp["ok"] is True

            # 双向加好友
            server.db.friends.add.assert_any_call(200, 100)
            server.db.friends.add.assert_any_call(100, 200)

            # === A和B互发消息 ===
            _ = recv_all(server, sock_a, count=5)
            _ = recv_all(server, sock_b, count=5)

            plain_a = "你好B！很高兴认识你"
            encrypted_a = server.crypto.encrypt(plain_a)
            server.send_dict(sock_a, {
                "type": MT.CHAT,
                "to": 200,
                "content": encrypted_a,
            })

            msg_for_b = server.recv_dict(sock_b, timeout=1.0)
            assert msg_for_b is not None
            assert msg_for_b["type"] == MT.CHAT
            assert msg_for_b["from"] == 100
            assert server.crypto.decrypt(msg_for_b["content"]) == plain_a

            plain_b = "你好A！我也很高兴！"
            encrypted_b = server.crypto.encrypt(plain_b)
            server.send_dict(sock_b, {
                "type": MT.CHAT,
                "to": 100,
                "content": encrypted_b,
            })

            msg_for_a = server.recv_dict(sock_a, timeout=1.0)
            assert msg_for_a is not None
            assert msg_for_a["type"] == MT.CHAT
            assert server.crypto.decrypt(msg_for_a["content"]) == plain_b

            # === A删除好友B ===
            server.db.friends.delete.return_value = 1
            server.db.friends.list_by_user.return_value = []

            server.send_dict(sock_a, {
                "type": MT.FRIEND_REMOVE,
                "friend_id": 200,
            })
            remove_resp = server.recv_dict(sock_a)
            assert remove_resp["type"] == MT.FRIEND_REMOVE_RESP
            assert remove_resp["ok"] is True
            server.db.friends.delete.assert_called_with(100, 200)

        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)


# ════════════════════════════════════════════════════════════════
# 群组生命周期系统测试
# ════════════════════════════════════════════════════════════════

class TestGroupJourney:
    """群组完整生命周期系统测试"""

    def test_create_group_and_chat(self, server):
        """创建群组 → 加入 → 聊天"""
        server.setup_user(uid=100, username="owner")
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "owner", "nickname": "群主"},
        ]

        sock = server.connect()
        login(server, sock, "owner")
        _ = recv_all(server, sock, count=3)

        try:
            # === 创建群聊 ===
            server.db.groups.create.return_value = 100
            server.db.groups.add_member.return_value = 1

            server.send_dict(sock, {
                "type": MT.GROUP_CREATE,
                "group_name": "测试群组",
                "invitees": [],
            })
            create_resp = server.recv_dict(sock)
            assert create_resp["type"] == MT.GROUP_CREATE_RESP
            assert create_resp["ok"] is True
            assert create_resp["group_name"] == "测试群组"

            # === 查询我的群列表 ===
            server.db.groups.list_by_user.return_value = [
                {"group_id": 100, "group_name": "测试群组", "owner_id": 100,
                 "remark": "", "joined_at": "2024-01-01"},
            ]
            server.db.groups.list_available.return_value = []

            server.send_dict(sock, {"type": MT.GROUP_LIST})
            list_resp = server.recv_dict(sock)
            assert list_resp["type"] == MT.GROUP_LIST_RESP
            assert len(list_resp["my_groups"]) == 1

            # === 查询群成员 ===
            server.db.groups.get_by_id.return_value = {
                "group_id": 100, "group_name": "测试群组", "owner_id": 100,
            }
            server.db.groups.list_members.return_value = [
                {"user_id": 100, "username": "owner", "nickname": "群主",
                 "role": 0, "remark": ""},
            ]

            server.send_dict(sock, {
                "type": MT.GROUP_MEMBERS,
                "group_id": 100,
            })
            members_resp = server.recv_dict(sock)
            assert members_resp["type"] == MT.GROUP_MEMBERS_RESP
            assert len(members_resp["members"]) == 1

            # === 在群中发消息 ===
            server.db.groups.is_member.return_value = True
            server.db.groups.list_member_ids.return_value = [100]

            plain = "群聊第一条消息"
            encrypted = server.crypto.encrypt(plain)
            server.send_dict(sock, {
                "type": MT.ROOM_CHAT,
                "room_id": 100,
                "content": encrypted,
            })
            # 群聊消息会广播给群成员（包括自己）
            msgs = recv_all(server, sock, count=2, timeout=0.3)
            room_msgs = [m for m in msgs if m["type"] == MT.ROOM_CHAT]
            assert len(room_msgs) >= 1

        finally:
            server.disconnect(sock)


# ════════════════════════════════════════════════════════════════
# 错误恢复测试
# ════════════════════════════════════════════════════════════════

class TestErrorRecovery:
    """错误恢复系统测试"""

    def test_server_recovers_from_bad_message(self, server):
        """服务器收到异常消息后继续正常服务（新连接）"""
        # 发送格式错误的数据（非 JSON 导致 ClientHandler 线程崩溃）
        bad_sock = server.connect()
        try:
            # 发送无效长度前缀的数据
            bad_sock.sendall(b'\x00\x00\x00\x05hello')
            time.sleep(0.15)
        except Exception:
            pass
        finally:
            try:
                bad_sock.close()
            except Exception:
                pass

        # 服务器应继续正常工作——接受新连接
        time.sleep(0.1)
        new_sock = server.connect()
        try:
            server.send_dict(new_sock, {"type": "ping"})
            resp = server.recv_dict(new_sock, timeout=1.0)
            assert resp is not None
            assert resp["type"] == MT.ERROR
        finally:
            server.disconnect(new_sock)

    def test_reconnect_after_disconnect(self, server):
        """断开后重新连接仍正常工作"""
        server.setup_user()
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "testuser", "nickname": "测试用户"},
        ]

        # 第一次连接
        sock1 = server.connect()
        resp1 = login(server, sock1)
        assert resp1["ok"] is True
        server.disconnect(sock1)

        time.sleep(0.1)

        # 用户在断连钩子中可能已从在线表移除
        # 需要重新设置才能再次登录
        salt = os.urandom(16).hex()
        pwd = "123456"
        server.db.users.get_by_username.return_value = {
            "user_id": 100, "username": "testuser",
            "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
            "salt": salt, "nickname": "测试用户",
        }

        # 第二次连接（同用户）
        sock2 = server.connect()
        resp2 = login(server, sock2)
        assert resp2["ok"] is True
        server.disconnect(sock2)
