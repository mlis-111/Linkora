"""Chat 模块集成测试

测试聊天模块与服务器框架的完整协作：
1. 私聊流程（Router dispatch → 解密 → 入库 → 加密转发 → 送达）
2. 群聊流程（成员校验 → 解密 → 入库 → 广播）
3. 历史记录（查询 → 加密返回）
4. 错误场景（缺参数、不在线、非群成员）
"""

import pytest
from unittest.mock import MagicMock, call, ANY, patch
from common.messages import MT
from common.crypto import CryptoUtil
from server.modules.chat import (
    register as register_chat_module,
    handle_chat,
    handle_room_chat,
    handle_history,
)
from server.core.session import Session


# ════════════════════════════════════════════════════════════════
# 辅助 fixtures
# ════════════════════════════════════════════════════════════════

@pytest.fixture
def chat_crypto():
    """聊天模块使用的加密工具"""
    return CryptoUtil(b"chat_test_key_16")


@pytest.fixture
def chat_ctx(ctx, chat_crypto):
    """配置好群聊相关 mock 的上下文（broadcast/broadcast_to 用 MagicMock 包装）"""
    ctx.crypto = chat_crypto
    ctx.db.groups.get_by_id.return_value = {"group_id": 1, "group_name": "公共聊天室"}
    ctx.db.groups.is_member.return_value = True
    ctx.db.groups.list_member_ids.return_value = [100, 200, 300]
    # 用 MagicMock 包装真实 OnlineRegistry 的 broadcast/broadcast_to
    # 以便使用 assert_called 等 mock 断言
    ctx.online.broadcast = MagicMock(wraps=ctx.online.broadcast)
    ctx.online.broadcast_to = MagicMock(wraps=ctx.online.broadcast_to)
    return ctx


def _make_online_handler():
    """创建一个 mock handler 并添加到在线表"""
    h = MagicMock()
    h.send = MagicMock()
    h.conn = MagicMock()
    return h


# ════════════════════════════════════════════════════════════════
# 模块注册测试
# ════════════════════════════════════════════════════════════════

class TestChatModuleRegistration:
    """聊天模块注册集成测试"""

    def test_registers_all_types(self, router, ctx):
        """注册所有聊天消息类型"""
        register_chat_module(router, ctx)

        assert MT.CHAT in router._handlers
        assert MT.ROOM_CHAT in router._handlers
        assert MT.HISTORY_REQ in router._handlers


# ════════════════════════════════════════════════════════════════
# 私聊集成测试
# ════════════════════════════════════════════════════════════════

class TestPrivateChatIntegration:
    """私聊完整流程集成测试"""

    def test_full_private_chat_flow(self, chat_ctx, session):
        """完整私聊流程：解密 → 入库 → 转发"""
        # 将接收方加入在线表
        target_handler = _make_online_handler()
        chat_ctx.online.add(200, target_handler)

        plain_content = "你好，朋友！"
        encrypted = chat_ctx.crypto.encrypt(plain_content)

        handle_chat(session, {
            "type": MT.CHAT,
            "to": 200,
            "content": encrypted,
            "ts": 1234567890,
        })

        # 1. 解密内容后入库
        chat_ctx.db.messages.insert.assert_called_once_with(
            1, 100, 200, None, plain_content
        )

        # 2. 转发给接收方
        target_handler.send.assert_called_once()
        msg_sent = target_handler.send.call_args[0][0]
        assert msg_sent["type"] == MT.CHAT
        assert msg_sent["from"] == 100
        assert msg_sent["to"] == 200
        assert msg_sent["content"] == encrypted  # 原文转发（不解密）

    def test_chat_sets_from_and_ts(self, chat_ctx, session):
        """自动补充发送者ID和时间戳"""
        target_handler = _make_online_handler()
        chat_ctx.online.add(200, target_handler)

        handle_chat(session, {"type": MT.CHAT, "to": 200, "content": "hi"})

        msg_sent = target_handler.send.call_args[0][0]
        assert "from" in msg_sent
        assert msg_sent["from"] == 100
        assert "ts" in msg_sent

    def test_chat_missing_to(self, session):
        """缺少接收方ID"""
        handle_chat(session, {"type": MT.CHAT, "content": "hello"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "接收方" in resp.get("message", "")

    def test_chat_empty_content(self, session):
        """空消息内容"""
        handle_chat(session, {"type": MT.CHAT, "to": 200, "content": ""})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_chat_offline_receiver(self, chat_ctx, session):
        """接收方不在线时通知发送方"""
        # 200 不在线（不加入在线表）
        handle_chat(session, {"type": MT.CHAT, "to": 200, "content": "hi"})

        # 仍然入库了
        chat_ctx.db.messages.insert.assert_called_once()

        # 通知发送方对方不在线
        calls = session._handler.send.call_args_list
        error_msgs = [c[0][0] for c in calls if c[0][0].get("type") == MT.ERROR]
        assert len(error_msgs) > 0
        assert "不在线" in error_msgs[0].get("message", "")

    def test_chat_encrypt_decrypt_integration(self, chat_ctx, session):
        """验证加密内容被正确解密后入库"""
        target_handler = _make_online_handler()
        chat_ctx.online.add(200, target_handler)

        plain = "这是一条加密的聊天消息 🔒"
        encrypted = chat_ctx.crypto.encrypt(plain)
        assert encrypted != plain  # 确实被加密了

        handle_chat(session, {
            "type": MT.CHAT,
            "to": 200,
            "content": encrypted,
        })

        # 入库的是解密后的明文
        stored_content = chat_ctx.db.messages.insert.call_args[0][4]
        assert stored_content == plain


# ════════════════════════════════════════════════════════════════
# 群聊集成测试
# ════════════════════════════════════════════════════════════════

class TestRoomChatIntegration:
    """群聊完整流程集成测试"""

    def test_full_room_chat_flow(self, chat_ctx, session):
        """完整群聊流程：成员校验 → 解密 → 入库 → 广播"""
        plain = "大家好！"
        encrypted = chat_ctx.crypto.encrypt(plain)

        # 使用 room_id=2 避免走公共聊天室（room_id=1）的跳过逻辑
        handle_room_chat(session, {
            "type": MT.ROOM_CHAT,
            "room_id": 2,
            "content": encrypted,
            "ts": 1234567890,
        })

        # 1. 校验成员身份
        chat_ctx.db.groups.is_member.assert_called_with(2, 100)

        # 2. 解密后入库（msg_type=2 为群聊）
        chat_ctx.db.messages.insert.assert_called_once_with(
            2, 100, None, 2, plain
        )

        # 3. 广播给所有群成员
        chat_ctx.online.broadcast_to.assert_called_once()
        msg_broadcast = chat_ctx.online.broadcast_to.call_args[0][0]
        assert msg_broadcast["type"] == MT.ROOM_CHAT
        assert msg_broadcast["from"] == 100
        assert msg_broadcast["room_id"] == 2

    def test_room_chat_not_member(self, chat_ctx, session):
        """非群成员发消息被拒绝"""
        chat_ctx.db.groups.is_member.return_value = False

        # 使用 room_id=2 避免公共聊天室跳过成员校验
        handle_room_chat(session, {
            "type": MT.ROOM_CHAT,
            "room_id": 2,
            "content": "hi",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "成员" in resp.get("message", "")
        # 未入库
        chat_ctx.db.messages.insert.assert_not_called()

    def test_room_chat_group_not_exist(self, chat_ctx, session):
        """群聊不存在"""
        chat_ctx.db.groups.get_by_id.return_value = None

        handle_room_chat(session, {
            "type": MT.ROOM_CHAT,
            "room_id": 999,
            "content": "hi",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不存在" in resp.get("message", "")

    def test_room_chat_missing_room_id(self, session):
        """缺少群聊ID"""
        handle_room_chat(session, {"type": MT.ROOM_CHAT, "content": "hi"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "群聊ID" in resp.get("message", "")

    def test_room_chat_empty_content(self, session):
        """空消息内容"""
        handle_room_chat(session, {
            "type": MT.ROOM_CHAT,
            "room_id": 1,
            "content": "",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_public_room_chat(self, chat_ctx, session):
        """公共聊天室（room_id=1）跳过成员校验，广播给所有人"""
        from common.messages import PUBLIC_ROOM_ID
        plain = "公共聊天室消息"
        encrypted = chat_ctx.crypto.encrypt(plain)

        handle_room_chat(session, {
            "type": MT.ROOM_CHAT,
            "room_id": PUBLIC_ROOM_ID,
            "content": encrypted,
        })

        # 公共聊天室不校验成员
        chat_ctx.db.groups.is_member.assert_not_called()

        # 使用 broadcast（不是 broadcast_to）
        chat_ctx.online.broadcast.assert_called_once()


# ════════════════════════════════════════════════════════════════
# 历史记录集成测试
# ════════════════════════════════════════════════════════════════

class TestHistoryIntegration:
    """历史记录查询集成测试"""

    def test_p2p_history(self, chat_ctx, session):
        """私聊历史查询：DB查询 → 加密返回"""
        chat_ctx.db.messages.query_p2p.return_value = [
            {"sender_id": 100, "receiver_id": 200, "content": "hello", "sent_at": "2024-01-01 10:00:00"},
            {"sender_id": 200, "receiver_id": 100, "content": "world", "sent_at": "2024-01-01 10:01:00"},
        ]

        handle_history(session, {"type": MT.HISTORY_REQ, "scope": "p2p", "target": 200})

        chat_ctx.db.messages.query_p2p.assert_called_with(100, 200, 200)

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.HISTORY_RESP
        assert resp["scope"] == "p2p"
        assert len(resp["records"]) == 2

        # 内容被加密返回（不同于原始明文）
        for record in resp["records"]:
            original = record["content"]
            decrypted = chat_ctx.crypto.decrypt(original)
            assert decrypted in ("hello", "world")

    def test_room_history(self, chat_ctx, session):
        """群聊历史查询"""
        chat_ctx.db.messages.query_room.return_value = [
            {"sender_id": 100, "content": "hello all", "sent_at": "2024-01-01 10:00:00"},
        ]

        handle_history(session, {"type": MT.HISTORY_REQ, "scope": "room", "room_id": 1})

        chat_ctx.db.messages.query_room.assert_called_with(1)

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.HISTORY_RESP
        assert len(resp["records"]) == 1

    def test_history_empty(self, chat_ctx, session):
        """无历史记录返回空列表"""
        chat_ctx.db.messages.query_p2p.return_value = []

        handle_history(session, {"type": MT.HISTORY_REQ, "scope": "p2p", "target": 200})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.HISTORY_RESP
        assert len(resp["records"]) == 0

    def test_history_invalid_scope(self, session):
        """无效 scope"""
        handle_history(session, {"type": MT.HISTORY_REQ, "scope": "invalid"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_history_missing_target_for_p2p(self, session):
        """p2p 查询缺少 target"""
        handle_history(session, {"type": MT.HISTORY_REQ, "scope": "p2p"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ════════════════════════════════════════════════════════════════
# Router 分发集成测试
# ════════════════════════════════════════════════════════════════

class TestChatRouterIntegration:
    """通过 Router 分发聊天消息的集成测试"""

    def test_chat_via_router(self, router, chat_ctx, session):
        """通过 Router dispatch CHAT 消息"""
        register_chat_module(router, chat_ctx)
        target_handler = _make_online_handler()
        chat_ctx.online.add(200, target_handler)

        plain = "router chat test"
        encrypted = chat_ctx.crypto.encrypt(plain)

        router.dispatch(session, {
            "type": MT.CHAT,
            "to": 200,
            "content": encrypted,
        })

        # 验证入库
        chat_ctx.db.messages.insert.assert_called_once_with(
            1, 100, 200, None, plain
        )

    def test_room_chat_via_router(self, router, chat_ctx, session):
        """通过 Router dispatch ROOM_CHAT 消息"""
        register_chat_module(router, chat_ctx)
        plain = "router room chat"
        encrypted = chat_ctx.crypto.encrypt(plain)

        router.dispatch(session, {
            "type": MT.ROOM_CHAT,
            "room_id": 1,
            "content": encrypted,
        })

        chat_ctx.db.messages.insert.assert_called_once_with(
            2, 100, None, 1, plain
        )

    def test_history_via_router(self, router, chat_ctx, session):
        """通过 Router dispatch HISTORY_REQ 消息"""
        register_chat_module(router, chat_ctx)
        chat_ctx.db.messages.query_p2p.return_value = []

        router.dispatch(session, {
            "type": MT.HISTORY_REQ,
            "scope": "p2p",
            "target": 200,
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.HISTORY_RESP


# ════════════════════════════════════════════════════════════════
# 端到端：多模块联合流程
# ════════════════════════════════════════════════════════════════

class TestEndToEndChatFlow:
    """端到端聊天流程（User + Chat 模块联合）"""

    def test_login_then_chat_flow(self, router, ctx, unbound_session):
        """用户登录后发送私聊消息的完整流程"""
        from server.modules.user import register as register_user
        from server.modules.chat import register as register_chat
        import hashlib, os

        # 注册两个模块
        register_user(router, ctx)
        register_chat(router, ctx)

        # 配置登录 DB mock
        salt = os.urandom(16).hex()
        pwd = "123456"
        ctx.db.users.get_by_username.return_value = {
            "user_id": 100,
            "username": "testuser",
            "password_hash": hashlib.sha256((salt + pwd).encode()).hexdigest(),
            "salt": salt,
            "nickname": "测试用户",
        }
        ctx.db.users.get_by_id.return_value = {
            "user_id": 100, "username": "testuser", "nickname": "测试用户",
        }
        ctx.db.users.get_all_users.return_value = [
            {"user_id": 100, "username": "testuser", "nickname": "测试用户"},
            {"user_id": 200, "username": "friend_user", "nickname": "好友"},
        ]

        # Step 1: 登录
        router.dispatch(unbound_session, {
            "type": MT.LOGIN,
            "username": "testuser",
            "password": "123456",
        })

        login_resp = unbound_session._handler.send.call_args_list[0][0][0]
        assert login_resp["ok"] is True
        assert unbound_session.user_id == 100
        assert ctx.online.is_online(100)

        # 添加接收方到在线表
        target_handler = _make_online_handler()
        ctx.online.add(200, target_handler)

        # Step 2: 发私聊消息
        plain = "登录后的第一条消息"
        encrypted = ctx.crypto.encrypt(plain)

        router.dispatch(unbound_session, {
            "type": MT.CHAT,
            "to": 200,
            "content": encrypted,
        })

        # 验证入库了明文
        ctx.db.messages.insert.assert_called_with(1, 100, 200, None, plain)
