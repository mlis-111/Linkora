"""登录模块系统测试

通过真实 TCP 连接测试完整的登录/注册/登出流程：
1. 成功登录（密码正确 → Session 绑定 → 在线表加入 → 快照返回）
2. 登录失败场景（用户不存在、密码错误、重复登录）
3. 注册流程（创建账户 → 密码哈希 → 入库）
4. 登出流程（在线表移除 → 广播）
5. 登录后广播 USER_LIST
6. 多客户端登录不同用户
"""

import hashlib
import os

import pytest
from common.messages import MT
from test.system.conftest import login, register, recv_all


# ════════════════════════════════════════════════════════════════
# 成功登录
# ════════════════════════════════════════════════════════════════

class TestLoginSuccess:
    """成功登录系统测试"""

    def test_login_returns_ok_and_user_info(self, server, client):
        """登录成功返回 ok=True 及用户信息"""
        server.setup_user()

        resp = login(server, client)

        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is True
        assert resp["user_id"] == 100
        assert resp["nickname"] == "测试用户"
        assert "online_users" in resp
        assert "all_users" in resp

    def test_login_response_contains_online_users(self, server, client):
        """登录响应包含在线用户列表"""
        server.setup_user()
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "testuser", "nickname": "测试用户"},
        ]

        resp = login(server, client)

        assert len(resp["online_users"]) >= 1
        online_ids = [u["user_id"] for u in resp["online_users"]]
        assert 100 in online_ids

    def test_login_broadcasts_to_other_clients(self, server):
        """登录后其他在线客户端收到 USER_LIST 广播"""
        server.setup_user(uid=100)
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user1", "nickname": "用户1"},
            {"user_id": 200, "username": "user2", "nickname": "用户2"},
        ]

        # 第一个用户登录
        sock_a = server.connect()
        salt = os.urandom(16).hex()
        pwd = "123456"
        server.db.users.get_by_username.return_value = {
            "user_id": 100, "username": "user1",
            "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
            "salt": salt, "nickname": "用户1",
        }
        server.db.users.get_by_id.return_value = {
            "user_id": 100, "username": "user1", "nickname": "用户1",
        }

        login(server, sock_a, "user1")

        # 第二个用户登录（会收到包含第一个用户的 USER_LIST）
        salt2 = os.urandom(16).hex()
        server.db.users.get_by_username.return_value = {
            "user_id": 200, "username": "user2",
            "password_hash": hashlib.sha256((salt2 + pwd).encode()).hexdigest(),
            "salt": salt2, "nickname": "用户2",
        }
        server.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "user2", "nickname": "用户2",
        }

        sock_b = server.connect()
        resp_b = login(server, sock_b, "user2")

        # 用户2 的响应包含用户1（已在线）
        assert resp_b["ok"] is True

        # 用户1 收到广播（USER_LIST）
        extra = recv_all(server, sock_a, count=2)
        broadcast = [m for m in extra if m["type"] == MT.USER_LIST]
        assert len(broadcast) >= 1

        server.disconnect(sock_a)
        server.disconnect(sock_b)


# ════════════════════════════════════════════════════════════════
# 登录失败场景
# ════════════════════════════════════════════════════════════════

class TestLoginFailures:
    """登录失败系统测试"""

    def test_login_user_not_found(self, server, client):
        """用户不存在"""
        server.db.users.get_by_username.return_value = None

        resp = login(server, client, username="nobody")

        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is False
        assert "不存在" in resp.get("reason", "")

    def test_login_wrong_password(self, server, client):
        """密码错误"""
        server.setup_user(password="correct_password")

        resp = login(server, client, password="wrong_password")

        assert resp["ok"] is False
        assert "密码" in resp.get("reason", "")

    def test_login_duplicate_rejected(self, server):
        """已在线用户不能重复登录"""
        server.setup_user(uid=100)

        # 第一次登录成功
        sock_a = server.connect()
        resp_a = login(server, sock_a)
        assert resp_a["ok"] is True

        # 第二次登录同一用户被拒绝
        sock_b = server.connect()
        resp_b = login(server, sock_b)
        assert resp_b["ok"] is False
        assert "在线" in resp_b.get("reason", "")

        server.disconnect(sock_a)
        server.disconnect(sock_b)

    def test_login_empty_username(self, server, client):
        """空用户名"""
        server.db.users.get_by_username.return_value = None

        server.send_dict(client, {
            "type": MT.LOGIN,
            "username": "",
            "password": "123456",
        })
        resp = server.recv_dict(client)

        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is False


# ════════════════════════════════════════════════════════════════
# 注册流程
# ════════════════════════════════════════════════════════════════

class TestRegisterSystem:
    """注册流程系统测试"""

    def test_register_success(self, server, client):
        """注册成功"""
        server.db.users.exists.return_value = False
        server.db.users.insert_user.return_value = 300

        resp = register(server, client, "newuser", "secure123", "新用户")

        assert resp["type"] == MT.REGISTER_RESP
        assert resp["ok"] is True

        # 验证密码被哈希存储
        server.db.users.insert_user.assert_called_once()
        args = server.db.users.insert_user.call_args[0]
        assert args[0] == "newuser"
        assert args[1] != "secure123"  # 不是明文

    def test_register_duplicate_username(self, server, client):
        """用户名已存在"""
        server.db.users.exists.return_value = True

        resp = register(server, client, "existing", "123456")

        assert resp["ok"] is False
        assert "已存在" in resp.get("reason", "")

    def test_register_empty_fields(self, server, client):
        """用户名或密码为空"""
        server.send_dict(client, {
            "type": MT.REGISTER,
            "username": "",
            "password": "",
        })
        resp = server.recv_dict(client)

        assert resp["type"] == MT.REGISTER_RESP
        assert resp["ok"] is False

    def test_register_default_nickname(self, server, client):
        """未提供昵称时默认使用用户名"""
        server.db.users.exists.return_value = False

        resp = register(server, client, "newuser2", "password")

        assert resp["ok"] is True
        kwargs = server.db.users.insert_user.call_args[1]
        assert kwargs.get("nickname") == "newuser2"


# ════════════════════════════════════════════════════════════════
# 登出流程
# ════════════════════════════════════════════════════════════════

class TestLogoutSystem:
    """登出流程系统测试"""

    def test_logout_removes_from_online(self, server, client):
        """登出后从在线表移除"""
        server.setup_user()
        login(server, client)

        # 登出前在在线表
        assert server.ctx.online.is_online(100)

        server.send_dict(client, {"type": MT.LOGOUT})
        # LOGOUT 会关闭连接，不发送响应
        # 给一点时间处理
        import time
        time.sleep(0.1)

        # 登出后不在在线表
        assert not server.ctx.online.is_online(100)

    def test_logout_broadcasts_to_others(self, server):
        """登出后其他在线用户收到 USER_LIST"""
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user1", "nickname": "用户1"},
            {"user_id": 200, "username": "user2", "nickname": "用户2"},
        ]

        # 第一个用户登录
        salt = os.urandom(16).hex()
        pwd = "123456"
        server.db.users.get_by_username.return_value = {
            "user_id": 100, "username": "user1",
            "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
            "salt": salt, "nickname": "用户1",
        }

        sock_a = server.connect()
        login(server, sock_a, "user1")

        # 第二个用户登录
        salt2 = os.urandom(16).hex()
        server.db.users.get_by_username.return_value = {
            "user_id": 200, "username": "user2",
            "password_hash": hashlib.sha256((salt2 + pwd).encode()).hexdigest(),
            "salt": salt2, "nickname": "用户2",
        }
        server.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "user2", "nickname": "用户2",
        }

        sock_b = server.connect()
        login(server, sock_b, "user2")

        # 清空 sock_b 的接收缓冲区
        _ = recv_all(server, sock_b, count=5)

        # 用户1 登出
        server.send_dict(sock_a, {"type": MT.LOGOUT})
        import time
        time.sleep(0.1)

        # 用户2 应收到广播
        broadcasts = recv_all(server, sock_b, count=3, timeout=0.5)
        user_list_msgs = [m for m in broadcasts if m["type"] == MT.USER_LIST]
        # 登出会触发 on_disconnect 广播
        assert len(user_list_msgs) >= 1

        server.disconnect(sock_a)
        server.disconnect(sock_b)


# ════════════════════════════════════════════════════════════════
# 多用户场景
# ════════════════════════════════════════════════════════════════

class TestMultiUserLogin:
    """多用户登录场景"""

    def test_two_users_login_concurrently(self, server):
        """两个用户同时登录"""
        server.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "user1", "nickname": "用户1"},
            {"user_id": 200, "username": "user2", "nickname": "用户2"},
        ]

        pwd = "123456"
        users = {}
        for uid, uname in [(100, "user1"), (200, "user2")]:
            salt = os.urandom(16).hex()
            users[uid] = {
                "user_id": uid, "username": uname,
                "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
                "salt": salt, "nickname": f"用户{uid}",
            }

        sock_a = server.connect()
        sock_b = server.connect()

        try:
            # 用户A登录
            server.db.users.get_by_username.return_value = users[100]
            server.db.users.get_by_id.return_value = users[100]
            resp_a = login(server, sock_a, "user1")

            # 用户B登录
            server.db.users.get_by_username.return_value = users[200]
            server.db.users.get_by_id.return_value = users[200]
            resp_b = login(server, sock_b, "user2")

            assert resp_a["ok"] is True
            assert resp_b["ok"] is True
            assert resp_a["user_id"] == 100
            assert resp_b["user_id"] == 200

            # 两个用户都在线
            assert server.ctx.online.is_online(100)
            assert server.ctx.online.is_online(200)
        finally:
            server.disconnect(sock_a)
            server.disconnect(sock_b)
