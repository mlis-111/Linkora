"""Chat 模块单元测试

覆盖内容:
1. 正常私聊流程（加密→转发→入库）
2. 公共聊天室消息（广播）
3. 历史记录查询（p2p/room）
4. 参数异常处理（空内容、缺参数）
5. 接收方不在线处理
6. 历史记录加密返回

author: 董钧豪
"""

import pytest
from unittest.mock import MagicMock, patch
from common.messages import MT


# ========== Fixtures ==========

@pytest.fixture
def mock_ctx():
    """创建 Mock ServerContext"""
    ctx = MagicMock()
    ctx.crypto.decrypt.side_effect = lambda x: f"decrypted_{x}"
    ctx.crypto.encrypt.side_effect = lambda x: f"encrypted_{x}"
    ctx.online.is_online.return_value = True
    ctx.online.send.return_value = True
    # 群聊相关 mock
    ctx.db.groups.get_by_id.return_value = {"group_id": "group_public", "group_name": "公共聊天室"}
    ctx.db.groups.is_member.return_value = True
    ctx.db.groups.list_member_ids.return_value = [100, 200, 300]
    return ctx


@pytest.fixture
def mock_session(mock_ctx):
    """创建 Mock Session"""
    session = MagicMock()
    session.ctx = mock_ctx
    session.user_id = 100
    session.username = "test_user"
    return session


# ========== 注册测试 ==========

class TestRegister:
    """模块注册测试"""

    def test_register_all_types(self):
        """验证 chat 模块注册了全部三种消息类型"""
        from server.modules import chat
        router = MagicMock()
        ctx = MagicMock()
        chat.register(router, ctx)
        assert router.register.call_count == 3
        types_registered = [call[0][0] for call in router.register.call_args_list]
        assert MT.CHAT in types_registered
        assert MT.ROOM_CHAT in types_registered
        assert MT.HISTORY_REQ in types_registered


# ========== 私聊测试 ==========

class TestHandleChat:
    """私聊消息处理测试"""

    def test_normal_p2p_chat(self, mock_session, mock_ctx):
        """正常私聊流程"""
        from server.modules.chat import handle_chat
        msg = {"to": 200, "content": "hello_encrypted", "ts": 12345}
        handle_chat(mock_session, msg)

        # 验证解密
        mock_ctx.crypto.decrypt.assert_called_with("hello_encrypted")

        # 验证入库
        mock_ctx.db.messages.insert.assert_called_with(1, 100, 200, None, "decrypted_hello_encrypted")

        # 验证转发
        mock_ctx.online.send.assert_called_with(200, msg)

    def test_chat_missing_target(self, mock_session):
        """缺少接收方时返回错误"""
        from server.modules.chat import handle_chat
        handle_chat(mock_session, {"content": "hello"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_chat_empty_content(self, mock_session):
        """空内容时返回错误"""
        from server.modules.chat import handle_chat
        handle_chat(mock_session, {"to": 200, "content": ""})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_chat_offline_target(self, mock_session, mock_ctx):
        """对方不在线时提示发送方"""
        from server.modules.chat import handle_chat
        mock_ctx.online.send.return_value = False
        handle_chat(mock_session, {"to": 200, "content": "hi"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不在线" in resp.get("message", "")

    def test_chat_ts_is_set(self, mock_session):
        """自动补充时间戳"""
        from server.modules.chat import handle_chat
        msg = {"to": 200, "content": "hi"}
        handle_chat(mock_session, msg)
        assert "ts" in msg
        assert "from" in msg
        assert msg["from"] == 100


# ========== 群聊测试 ==========

class TestHandleRoomChat:
    """群聊消息处理测试"""

    def test_normal_room_chat(self, mock_session, mock_ctx):
        """正常群聊流程"""
        from server.modules.chat import handle_room_chat
        msg = {"room_id": "group_public", "content": "room_msg_encrypted", "ts": 12345}
        handle_room_chat(mock_session, msg)

        # 验证校验群成员
        mock_ctx.db.groups.is_member.assert_called_with("group_public", 100)

        # 验证解密和入库
        mock_ctx.crypto.decrypt.assert_called_with("room_msg_encrypted")
        mock_ctx.db.messages.insert.assert_called_with(2, 100, None, "group_public", "decrypted_room_msg_encrypted")

        # 验证广播给群成员
        mock_ctx.online.broadcast_to.assert_called_with(msg, [100, 200, 300])

    def test_room_chat_missing_room_id(self, mock_session):
        """缺少 room_id 时返回错误"""
        from server.modules.chat import handle_room_chat
        handle_room_chat(mock_session, {"content": "hi"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "群聊ID" in resp.get("message", "")

    def test_room_chat_empty_content(self, mock_session):
        """空内容时返回错误"""
        from server.modules.chat import handle_room_chat
        handle_room_chat(mock_session, {"room_id": "group_public", "content": ""})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_room_chat_not_member(self, mock_session, mock_ctx):
        """非群成员发消息被拒"""
        from server.modules.chat import handle_room_chat
        mock_ctx.db.groups.is_member.return_value = False
        handle_room_chat(mock_session, {"room_id": "group_public", "content": "hi"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "成员" in resp.get("message", "")

    def test_room_chat_nonexistent_group(self, mock_session, mock_ctx):
        """群聊不存在时返回错误"""
        from server.modules.chat import handle_room_chat
        mock_ctx.db.groups.get_by_id.return_value = None
        handle_room_chat(mock_session, {"room_id": "nonexistent", "content": "hi"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不存在" in resp.get("message", "")

    def test_room_chat_sets_from(self, mock_session):
        """自动补充发送者ID"""
        from server.modules.chat import handle_room_chat
        msg = {"room_id": "group_public", "content": "hi"}
        handle_room_chat(mock_session, msg)
        assert msg["from"] == 100


# ========== 历史记录测试 ==========

class TestHandleHistory:
    """历史记录查询测试"""

    def test_history_p2p(self, mock_session, mock_ctx):
        """私聊历史查询"""
        from server.modules.chat import handle_history
        mock_ctx.db.messages.query_p2p.return_value = [
            {"sender_id": 100, "receiver_id": 200, "content": "hello", "sent_at": "2024-01-01 10:00:00"},
            {"sender_id": 200, "receiver_id": 100, "content": "world", "sent_at": "2024-01-01 10:01:00"},
        ]
        handle_history(mock_session, {"scope": "p2p", "target": 200})

        mock_ctx.db.messages.query_p2p.assert_called_with(100, 200)
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.HISTORY_RESP
        assert resp["scope"] == "p2p"
        assert len(resp["records"]) == 2
        # 验证内容被加密
        assert resp["records"][0]["content"].startswith("encrypted_")

    def test_history_room(self, mock_session, mock_ctx):
        """群聊历史查询"""
        from server.modules.chat import handle_history
        mock_ctx.db.messages.query_room.return_value = [
            {"sender_id": 100, "receiver_id": None, "content": "hello all", "sent_at": "2024-01-01 10:00:00"},
        ]
        handle_history(mock_session, {"scope": "room", "room_id": 1})

        mock_ctx.db.messages.query_room.assert_called_with(1)
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.HISTORY_RESP
        assert len(resp["records"]) == 1

    def test_history_empty(self, mock_session, mock_ctx):
        """无历史记录返回空列表"""
        from server.modules.chat import handle_history
        mock_ctx.db.messages.query_p2p.return_value = []
        handle_history(mock_session, {"scope": "p2p", "target": 200})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert len(resp["records"]) == 0

    def test_history_invalid_scope(self, mock_session):
        """无效 scope 返回错误"""
        from server.modules.chat import handle_history
        handle_history(mock_session, {"scope": "invalid"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_history_missing_target(self, mock_session):
        """p2p 查询缺少 target 返回错误"""
        from server.modules.chat import handle_history
        handle_history(mock_session, {"scope": "p2p"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
