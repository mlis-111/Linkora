"""
单元测试：AI 问答模块
作者：董浩楠

测试范围：
1. register 正确注册 MT.AI_ASK（语句覆盖）
2. handle_ai_ask 将任务提交到 ctx.workers（语句覆盖）
3. _do_ask 正常流程：入库提问 → 调 API → 入库回答 → 回传 ai_answer（语句覆盖 + 判定覆盖）
4. _do_ask 异常处理：API 超时/失败时发送 ERROR 消息（判定条件覆盖 + 路径覆盖）
5. _do_ask 多轮上下文：查历史拼到 API 请求（条件覆盖 + 条件组合覆盖）

六种覆盖保证：
- 语句覆盖：所有可执行语句至少执行一次
- 判定覆盖：每个判定的真/假分支各执行一次
- 条件覆盖：每个条件的所有可能取值
- 判定条件覆盖：判定 + 条件的组合
- 条件组合覆盖：所有条件取值的组合
- 路径覆盖：所有可能的执行路径

使用 pytest + unittest.mock
"""

import pytest
import sys
import os
import time
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from common.messages import MT
from server.core.router import MessageRouter


# ==================== Fixtures ====================

@pytest.fixture
def mock_ctx():
    """构造一个带完整依赖的 mock ServerContext"""
    ctx = Mock()
    ctx.config.AI_API_URL = "https://api.deepseek.com/v1/chat/completions"
    ctx.config.AI_API_KEY = "test-key"
    ctx.config.AI_MODEL = "deepseek-chat"
    ctx.config.AI_USER_ID = 1

    # mock 数据库
    ctx.db.messages.insert = Mock(return_value=100)
    ctx.db.messages.query_p2p = Mock(return_value=[])

    # mock 线程池：同步执行提交的任务（方便测试）
    def fake_submit(fn, *args, **kwargs):
        fn(*args, **kwargs)
    ctx.workers.submit = Mock(side_effect=fake_submit)

    return ctx


@pytest.fixture
def mock_session(mock_ctx):
    """构造一个已登录用户的 mock Session"""
    session = Mock()
    session.ctx = mock_ctx
    session.user_id = 42
    session.username = "testuser"
    session.send = Mock()
    return session


@pytest.fixture
def router():
    return MessageRouter()


# ==================== 语句覆盖 & 判定覆盖：register 注册 ====================

class TestRegistration:
    """测试 AI 模块的 register 函数（语句覆盖 + 判定覆盖）"""

    def test_register_ai_ask(self, router, mock_ctx):
        """语句覆盖：register 应该注册 MT.AI_ASK 消息类型"""
        from server.modules.ai import register

        register(router, mock_ctx)

        assert MT.AI_ASK in router._handlers

    def test_register_only_ai_types(self, router, mock_ctx):
        """判定覆盖：register 不应该注册不属于 AI 模块的消息类型"""
        from server.modules.ai import register

        register(router, mock_ctx)

        assert MT.AI_ASK in router._handlers
        assert MT.CHAT not in router._handlers
        assert MT.LOGIN not in router._handlers


# ==================== 语句覆盖：handle_ai_ask 调度 ====================

class TestHandleAiAsk:
    """测试 handle_ai_ask：将任务提交到线程池（语句覆盖）"""

    def test_submits_to_worker_pool(self, router, mock_ctx, mock_session):
        """语句覆盖：handle_ai_ask 应该调用 ctx.workers.submit 异步处理"""
        from server.modules.ai import register

        register(router, mock_ctx)
        msg = {"type": MT.AI_ASK, "question": "AES 怎么实现？", "ts": int(time.time())}

        router.dispatch(mock_session, msg)

        assert mock_ctx.workers.submit.called

    def test_passes_correct_args_to_submit(self, router, mock_ctx, mock_session):
        """判定覆盖：验证 submit 传递了正确的函数和参数"""
        from server.modules.ai import register, _do_ask

        register(router, mock_ctx)
        msg = {"type": MT.AI_ASK, "question": "测试问题", "ts": 1234567890}

        router.dispatch(mock_session, msg)

        call_args = mock_ctx.workers.submit.call_args[0]
        assert call_args[0] == _do_ask
        assert call_args[1] == mock_session


# ==================== 语句覆盖 & 判定覆盖：_do_ask 正常流程 ====================

class TestDoAskNormalFlow:
    """测试 _do_ask 正常处理流程（语句覆盖 + 判定覆盖）"""

    @patch("server.modules.ai.requests.post")
    def test_inserts_question_to_db(self, mock_post, mock_session):
        """语句覆盖：应该将用户提问入库（sender=用户, receiver=AI_USER_ID）"""
        from server.modules.ai import _do_ask

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "推荐使用 AES-256-CBC 模式"}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "AES 怎么实现？", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        ctx = mock_session.ctx
        ctx.db.messages.insert.assert_any_call(
            1, 42, 1, None, "AES 怎么实现？"
        )

    @patch("server.modules.ai.requests.post")
    def test_inserts_answer_to_db(self, mock_post, mock_session):
        """判定覆盖：应该将 AI 回答入库（sender=AI_USER_ID, receiver=用户）——插入方向反转"""
        from server.modules.ai import _do_ask

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "推荐使用 AES-256-CBC 模式"}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "AES 怎么实现？", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        ctx = mock_session.ctx
        ctx.db.messages.insert.assert_any_call(
            1, 1, 42, None, "推荐使用 AES-256-CBC 模式"
        )

    @patch("server.modules.ai.requests.post")
    def test_sends_ai_answer_to_client(self, mock_post, mock_session):
        """语句覆盖：应该向客户端发送正确格式的 ai_answer 消息"""
        from server.modules.ai import _do_ask

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "推荐使用 AES-256-CBC 模式"}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "AES 怎么实现？", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        assert mock_session.send.called
        call_args = mock_session.send.call_args[0][0]
        assert call_args["type"] == MT.AI_ANSWER
        assert call_args["answer"] == "推荐使用 AES-256-CBC 模式"
        assert "ts" in call_args

    @patch("server.modules.ai.requests.post")
    def test_calls_deepseek_api_correctly(self, mock_post, mock_session):
        """判定覆盖：验证 API 调用参数正确（URL, headers, body, model）"""
        from server.modules.ai import _do_ask

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "好的"}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "什么是 TCP？", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        ctx = mock_session.ctx
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.deepseek.com/v1/chat/completions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
        assert call_args[1]["json"]["model"] == "deepseek-chat"
        messages = call_args[1]["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert "校园通" in messages[0]["content"]


# ==================== 条件覆盖 & 条件组合覆盖：多轮上下文 ====================

class TestDoAskMultiTurn:
    """测试 _do_ask 多轮上下文（条件覆盖 + 条件组合覆盖）"""

    @patch("server.modules.ai.requests.post")
    def test_queries_history_for_context(self, mock_post, mock_session):
        """条件覆盖：应该查询用户与 AI 的历史消息"""
        from server.modules.ai import _do_ask

        mock_session.ctx.db.messages.query_p2p.return_value = [
            {"sender_id": 42, "content": "上次的问题"},
            {"sender_id": 1, "content": "上次的回答"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "好的，基于之前的讨论..."}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "能详细说说吗？", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        mock_session.ctx.db.messages.query_p2p.assert_called_once_with(42, 1, limit=20)

    @patch("server.modules.ai.requests.post")
    def test_includes_history_in_api_request(self, mock_post, mock_session):
        """条件组合覆盖：历史中同时有用户消息和 AI 消息时，拼成正确的 messages 数组"""
        from server.modules.ai import _do_ask

        mock_session.ctx.db.messages.query_p2p.return_value = [
            {"sender_id": 42, "content": "上次的问题"},
            {"sender_id": 1, "content": "上次的回答"},
        ]

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "继续..."}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "追问", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        messages = mock_post.call_args[1]["json"]["messages"]
        assert len(messages) == 4  # system + 2条历史 + 1条当前
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "上次的问题"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "上次的回答"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "追问"

    @patch("server.modules.ai.requests.post")
    def test_empty_history_still_works(self, mock_post, mock_session):
        """条件组合覆盖：历史为空时，只包含 system + 当前问题"""
        from server.modules.ai import _do_ask

        mock_session.ctx.db.messages.query_p2p.return_value = []

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "没有历史"}}]
        }
        mock_post.return_value = mock_response

        msg = {"question": "新问题", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        messages = mock_post.call_args[1]["json"]["messages"]
        assert len(messages) == 2  # system + 当前问题
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "新问题"


# ==================== 判定条件覆盖 & 路径覆盖：异常处理 ====================

class TestDoAskErrorHandling:
    """测试 _do_ask 异常处理（判定条件覆盖 + 路径覆盖）"""

    @patch("server.modules.ai.requests.post")
    def test_sends_error_on_api_timeout(self, mock_post, mock_session):
        """判定条件覆盖：API 超时时走 except 分支，发送 ERROR 消息"""
        from server.modules.ai import _do_ask

        mock_post.side_effect = Exception("Connection timeout")

        msg = {"question": "测试", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        assert mock_session.send.called
        call_args = mock_session.send.call_args[0][0]
        assert call_args["type"] == MT.ERROR
        assert "code" in call_args
        assert "message" in call_args

    @patch("server.modules.ai.requests.post")
    def test_does_not_crash_on_api_error(self, mock_post, mock_session):
        """路径覆盖：API 异常时线程不崩溃，不向外抛异常"""
        from server.modules.ai import _do_ask

        mock_post.side_effect = Exception("Boom!")

        try:
            _do_ask(mock_session, msg={"question": "测试", "ts": int(time.time())})
        except Exception:
            pytest.fail("_do_ask 不应该向外抛出异常")

    @patch("server.modules.ai.requests.post")
    def test_still_inserts_question_on_api_failure(self, mock_post, mock_session):
        """路径覆盖：即使 API 失败，提问也应已入库（在 API 调用之前执行）"""
        from server.modules.ai import _do_ask

        mock_post.side_effect = Exception("API Error")

        msg = {"question": "测试问题", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        mock_session.ctx.db.messages.insert.assert_any_call(
            1, 42, 1, None, "测试问题"
        )

    @patch("server.modules.ai.requests.post")
    def test_handles_http_error_status(self, mock_post, mock_session):
        """路径覆盖：API 返回非 200 状态码时发送错误"""
        from server.modules.ai import _do_ask

        import requests as real_requests
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = real_requests.HTTPError("401 Unauthorized")
        mock_post.return_value = mock_response

        msg = {"question": "测试", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        call_args = mock_session.send.call_args[0][0]
        assert call_args["type"] == MT.ERROR

    @patch("server.modules.ai.requests.post")
    def test_handles_malformed_api_response(self, mock_post, mock_session):
        """路径覆盖：API 返回格式异常时发送错误"""
        from server.modules.ai import _do_ask

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"no_choices": []}  # 缺少 choices 字段
        mock_post.return_value = mock_response

        msg = {"question": "测试", "ts": int(time.time())}
        _do_ask(mock_session, msg)

        call_args = mock_session.send.call_args[0][0]
        assert call_args["type"] == MT.ERROR
