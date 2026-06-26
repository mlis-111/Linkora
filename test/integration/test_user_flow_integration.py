"""User 模块集成测试

测试用户模块与服务器框架的完整协作：
1. 登录流程（Router dispatch → User handler → DB查询 → 在线表 → 广播）
2. 注册流程（校验 → 查重 → 哈希 → 入库）
3. 登出流程（在线表移除 → 广播）
4. 断连清理（钩子链 → 在线表移除 → 广播）
5. 错误场景（用户不存在、密码错误、重复登录、空参数）
"""

import hashlib
import os

import pytest
from unittest.mock import MagicMock, call
from common.messages import MT
from server.modules.user import (
    register as register_user_module,
    handle_login,
    handle_register,
    handle_logout,
    on_disconnect,
    _verify_password,
)


# ════════════════════════════════════════════════════════════════
# 辅助：设置用户模块需要的 DB mock 数据
# ════════════════════════════════════════════════════════════════

def _setup_db_for_login(ctx, username="testuser", password="123456", uid=100,
                        use_sha256=True, nickname="测试用户"):
    """配置 DB mock 以支持登录测试"""
    if use_sha256:
        salt = os.urandom(16).hex()
        pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    else:
        salt = ""
        pwd_hash = hashlib.md5(password.encode()).hexdigest()

    ctx.db.users.get_by_username.return_value = {
        "user_id": uid,
        "username": username,
        "password_hash": pwd_hash,
        "salt": salt,
        "nickname": nickname,
    }
    ctx.db.users.get_by_id.return_value = {
        "user_id": uid,
        "username": username,
        "nickname": nickname,
    }
    ctx.db.users.get_all_users.return_value = [
        {"user_id": uid, "username": username, "nickname": nickname},
    ]
    return pwd_hash, salt


# ════════════════════════════════════════════════════════════════
# 模块注册测试
# ════════════════════════════════════════════════════════════════

class TestModuleRegistration:
    """用户模块注册集成测试"""

    def test_register_integrates_with_router(self, router, ctx):
        """向真实 Router 注册后，LOGIN 消息能路由到 handle_login"""
        register_user_module(router, ctx)

        # 验证注册了三个消息类型
        assert MT.LOGIN in router._handlers
        assert MT.REGISTER in router._handlers
        assert MT.LOGOUT in router._handlers

        # 验证注册了断连钩子
        assert len(ctx._disconnect_hooks) == 1


# ════════════════════════════════════════════════════════════════
# 密码校验测试
# ════════════════════════════════════════════════════════════════

class TestPasswordVerification:
    """密码校验兼容性测试（SHA256 / MD5）"""

    def test_sha256_match(self):
        """SHA256 密码匹配"""
        salt = "abcd1234"
        pwd = "mypassword"
        pwd_hash = hashlib.sha256((salt + pwd).encode()).hexdigest()
        assert _verify_password(pwd, pwd_hash, salt)

    def test_sha256_mismatch(self):
        """SHA256 密码不匹配"""
        salt = "abcd1234"
        pwd_hash = hashlib.sha256((salt + "correct").encode()).hexdigest()
        assert not _verify_password("wrong", pwd_hash, salt)

    def test_md5_match(self):
        """MD5 兼容模式（预置账号）"""
        pwd = "123456"
        pwd_hash = hashlib.md5(pwd.encode()).hexdigest()
        assert _verify_password(pwd, pwd_hash, "")

    def test_md5_mismatch(self):
        """MD5 密码不匹配"""
        pwd_hash = hashlib.md5("correct".encode()).hexdigest()
        assert not _verify_password("wrong", pwd_hash, "")


# ════════════════════════════════════════════════════════════════
# 登录集成测试
# ════════════════════════════════════════════════════════════════

class TestLoginIntegration:
    """登录完整流程集成测试"""

    def test_full_login_flow(self, ctx, unbound_session):
        """完整登录流程：
        Router dispatch LOGIN → handle_login → DB校验 → 在线表add → 快照 → 广播
        """
        _setup_db_for_login(ctx)

        register_user_module(MagicMock(), ctx)

        handle_login(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "123456",
        })

        # 1. Session 已绑定用户
        assert unbound_session.user_id == 100
        assert unbound_session.username == "testuser"

        # 2. 用户已加入在线表
        assert ctx.online.is_online(100)

        # 3. 返回登录成功响应
        resp = unbound_session._handler.send.call_args_list[0][0][0]
        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is True
        assert resp["user_id"] == 100
        assert resp["nickname"] == "测试用户"
        assert "online_users" in resp
        assert "all_users" in resp

    def test_login_user_not_found(self, ctx, unbound_session):
        """用户不存在"""
        ctx.db.users.get_by_username.return_value = None

        handle_login(unbound_session, {
            "type": MT.LOGIN,
            "username": "nobody",
            "password": "123456",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is False
        assert "不存在" in resp.get("reason", "")

    def test_login_wrong_password(self, ctx, unbound_session):
        """密码错误"""
        _setup_db_for_login(ctx, password="correct_password")

        handle_login(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "wrong_password",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is False
        assert "密码" in resp.get("reason", "")

    def test_login_duplicate_online_rejected(self, ctx, unbound_session, second_session):
        """已在线用户拒绝重复登录"""
        _setup_db_for_login(ctx, uid=200)

        # 用户 200 已在 second_session fixture 中上线
        # 现在用 unbound_session 尝试登录同一用户
        handle_login(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "123456",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is False
        assert "在线" in resp.get("reason", "")

    def test_login_broadcast_to_others(self, ctx, unbound_session, second_session):
        """登录成功后向其他在线用户广播 USER_LIST"""
        _setup_db_for_login(ctx, uid=300)

        # second_session (用户200) 已在线
        handle_login(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "123456",
        })

        # 用户200 收到广播
        assert second_session._handler.send.called
        broadcast_msg = second_session._handler.send.call_args[0][0]
        assert broadcast_msg["type"] == MT.USER_LIST
        assert "online_users" in broadcast_msg

    def test_login_response_contains_online_users(self, ctx, unbound_session, second_session):
        """登录响应的 online_users 包含已登录的其他用户"""
        _setup_db_for_login(ctx, uid=300)

        # second_session (用户200) 已在线
        ctx.db.users.get_by_id.side_effect = lambda uid: {
            200: {"user_id": 200, "username": "friend_user", "nickname": "好友"},
            300: {"user_id": 300, "username": "testuser", "nickname": "测试用户"},
        }.get(uid)
        ctx.db.users.get_all_users.return_value = [
            {"user_id": 200, "username": "friend_user", "nickname": "好友"},
            {"user_id": 300, "username": "testuser", "nickname": "测试用户"},
        ]

        handle_login(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "123456",
        })

        resp = unbound_session._handler.send.call_args_list[0][0][0]
        online_ids = [u["user_id"] for u in resp["online_users"]]
        # 200 已在线上，300 刚登录
        assert 200 in online_ids


# ════════════════════════════════════════════════════════════════
# 注册集成测试
# ════════════════════════════════════════════════════════════════

class TestRegisterIntegration:
    """注册完整流程集成测试"""

    def test_full_register_flow(self, ctx, unbound_session):
        """完整注册流程：校验 → 查重 → 哈希 → 入库 → 响应"""
        ctx.db.users.exists.return_value = False
        ctx.db.users.insert_user.return_value = 300

        handle_register(unbound_session, {
            "type": MT.REGISTER,
            "username": "newuser",
            "password": "secure123",
            "nickname": "新用户",
        })

        # 验证入库调用（nickname 和 is_ai_bot 通过关键字传递）
        ctx.db.users.insert_user.assert_called_once()
        args = ctx.db.users.insert_user.call_args[0]
        kwargs = ctx.db.users.insert_user.call_args[1]
        assert args[0] == "newuser"  # username
        assert args[1] != "secure123"  # 存的是哈希不是明文
        assert len(args[1]) == 64  # SHA256 哈希长度
        assert len(args[2]) == 32  # salt 长度（16字节hex）
        assert kwargs.get("nickname") == "新用户"  # nickname

        # 验证响应
        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["type"] == MT.REGISTER_RESP
        assert resp["ok"] is True

    def test_register_empty_username(self, ctx, unbound_session):
        """用户名为空"""
        handle_register(unbound_session, {
            "type": MT.REGISTER,
            "username": "",
            "password": "123456",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "不能为空" in resp.get("reason", "")

    def test_register_empty_password(self, ctx, unbound_session):
        """密码为空"""
        handle_register(unbound_session, {
            "type": MT.REGISTER,
            "username": "user",
            "password": "",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "不能为空" in resp.get("reason", "")

    def test_register_duplicate_username(self, ctx, unbound_session):
        """用户名已存在"""
        ctx.db.users.exists.return_value = True

        handle_register(unbound_session, {
            "type": MT.REGISTER,
            "username": "existing",
            "password": "123456",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "已存在" in resp.get("reason", "")

    def test_register_default_nickname(self, ctx, unbound_session):
        """未提供昵称时默认使用用户名"""
        ctx.db.users.exists.return_value = False

        handle_register(unbound_session, {
            "type": MT.REGISTER,
            "username": "newuser",
            "password": "123456",
        })

        kwargs = ctx.db.users.insert_user.call_args[1]
        assert kwargs.get("nickname") == "newuser"  # nickname 默认等于 username


# ════════════════════════════════════════════════════════════════
# 登出集成测试
# ════════════════════════════════════════════════════════════════

class TestLogoutIntegration:
    """登出完整流程集成测试"""

    def test_full_logout_flow(self, ctx, session, second_session):
        """完整登出流程：在线表移除 → 广播 → 关闭连接"""
        ctx.db.users.get_by_id.side_effect = lambda uid: {
            200: {"user_id": 200, "username": "friend_user", "nickname": "好友"},
        }.get(uid)
        ctx.db.users.get_all_users.return_value = [
            {"user_id": 200, "username": "friend_user", "nickname": "好友"},
        ]

        # session(用户100) 和 second_session(用户200) 都在线
        ctx.online.add(100, session._handler)

        handle_logout(session, {"type": MT.LOGOUT})

        # 1. 用户已从在线表移除
        assert not ctx.online.is_online(100)

        # 2. 其他在线用户收到广播
        assert second_session._handler.send.called
        broadcast_msg = second_session._handler.send.call_args[0][0]
        assert broadcast_msg["type"] == MT.USER_LIST

        # 3. 连接已关闭
        session._handler.conn.close.assert_called()

    def test_logout_unbound_session(self, ctx, unbound_session):
        """未绑定用户的 Session 登出（无操作）"""
        handle_logout(unbound_session, {"type": MT.LOGOUT})
        # 不应有任何副作用
        unbound_session._handler.conn.close.assert_not_called()


# ════════════════════════════════════════════════════════════════
# 断连钩子集成测试
# ════════════════════════════════════════════════════════════════

class TestDisconnectIntegration:
    """断连钩子集成测试"""

    def test_disconnect_hook_broadcasts(self, ctx, session, second_session):
        """用户断连时钩子广播下线通知"""
        ctx.online.add(100, session._handler)
        ctx.db.users.get_all_users.return_value = [
            {"user_id": 200, "username": "friend_user", "nickname": "好友"},
        ]

        on_disconnect(session)

        # 其他在线用户收到广播
        assert second_session._handler.send.called
        msg = second_session._handler.send.call_args[0][0]
        assert msg["type"] == MT.USER_LIST

    def test_disconnect_hook_unbound_user_noop(self, ctx, unbound_session):
        """未绑定用户的断连钩子无副作用"""
        on_disconnect(unbound_session)
        # 不应尝试广播
        unbound_session._handler.send.assert_not_called()


# ════════════════════════════════════════════════════════════════
# Router 分发集成测试（用户模块通过 Router 分发）
# ════════════════════════════════════════════════════════════════

class TestUserRouterIntegration:
    """通过 MessageRouter 分发用户消息的集成测试"""

    def test_login_via_router(self, router, ctx, unbound_session):
        """通过 Router dispatch LOGIN 消息"""
        register_user_module(router, ctx)
        _setup_db_for_login(ctx)

        router.dispatch(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "123456",
        })

        resp = unbound_session._handler.send.call_args_list[0][0][0]
        assert resp["type"] == MT.LOGIN_RESP
        assert resp["ok"] is True
        assert unbound_session.user_id == 100

    def test_register_via_router(self, router, ctx, unbound_session):
        """通过 Router dispatch REGISTER 消息"""
        register_user_module(router, ctx)
        ctx.db.users.exists.return_value = False

        router.dispatch(unbound_session, {
            "type": MT.REGISTER,
            "username": "newuser",
            "password": "password",
        })

        resp = unbound_session._handler.send.call_args[0][0]
        assert resp["type"] == MT.REGISTER_RESP
        assert resp["ok"] is True

    def test_logout_via_router(self, router, ctx, session):
        """通过 Router dispatch LOGOUT 消息"""
        register_user_module(router, ctx)
        ctx.online.add(100, session._handler)

        router.dispatch(session, {"type": MT.LOGOUT})

        assert not ctx.online.is_online(100)
