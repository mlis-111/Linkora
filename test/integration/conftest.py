"""集成测试共享 fixtures

提供真实组件实例（仅 mock 数据库层），
用于测试各模块之间的交互协作。

集成测试范围：
- Protocol + Crypto 编解码联动
- MessageRouter + 业务模块路由分发
- ServerContext 依赖注入
- OnlineRegistry 线程安全在线管理
- 多模块联合流程（登录→聊天→好友→群组）
"""

import pytest
from unittest.mock import MagicMock
from common.crypto import CryptoUtil
from common.messages import MT
from server.core.context import ServerContext
from server.core.router import MessageRouter
from server.core.online import OnlineRegistry
from server.core.session import Session


# ════════════════════════════════════════════════════════════════
# 基础组件 fixtures
# ════════════════════════════════════════════════════════════════

@pytest.fixture
def crypto():
    """真实 CryptoUtil 实例（16字节密钥）"""
    return CryptoUtil(b"test_key_16bytes")


@pytest.fixture
def online_registry():
    """真实 OnlineRegistry 实例（线程安全在线表）"""
    return OnlineRegistry()


@pytest.fixture
def router():
    """真实 MessageRouter 实例"""
    return MessageRouter()


@pytest.fixture
def mock_db():
    """Mock 数据库 DAO 集合

    返回一个嵌套 MagicMock，模拟 ServerContext._DB 结构。
    各测试可按需配置具体 DAO 方法的返回值。
    """
    db = MagicMock()
    db.users = MagicMock()
    db.messages = MagicMock()
    db.friends = MagicMock()
    db.files = MagicMock()
    db.ai_msg = MagicMock()
    db.friend_requests = MagicMock()
    db.groups = MagicMock()
    return db


@pytest.fixture
def ctx(mock_db, online_registry, crypto):
    """真实 ServerContext 实例（仅 DB 为 mock）"""
    context = ServerContext.__new__(ServerContext)
    context.config = MagicMock()
    context.config.HOST = "127.0.0.1"
    context.config.PORT = 9999
    context.db = mock_db
    context.online = online_registry
    context.crypto = crypto
    context.workers = MagicMock()
    context._disconnect_hooks = []
    return context


@pytest.fixture
def mock_handler():
    """Mock ClientHandler（用于 Session 的 _handler 引用）"""
    handler = MagicMock()
    handler.send = MagicMock()
    handler.conn = MagicMock()
    return handler


@pytest.fixture
def session(ctx, mock_handler):
    """创建一个已绑定用户的 Session"""
    s = Session(ctx, mock_handler)
    s.bind_user(100, "test_user")
    return s


@pytest.fixture
def unbound_session(ctx, mock_handler):
    """创建一个未绑定用户的 Session"""
    return Session(ctx, mock_handler)


@pytest.fixture
def second_handler():
    """第二个 mock ClientHandler（模拟另一个在线用户）"""
    handler = MagicMock()
    handler.send = MagicMock()
    handler.conn = MagicMock()
    return handler


@pytest.fixture
def second_session(ctx, second_handler):
    """第二个已绑定用户的 Session（模拟用户200）"""
    s = Session(ctx, second_handler)
    s.bind_user(200, "friend_user")
    # 将第二个用户加入在线表
    ctx.online.add(200, second_handler)
    return s


# ════════════════════════════════════════════════════════════════
# 消息辅助函数
# ════════════════════════════════════════════════════════════════

def assert_response_ok(session, expected_type=None):
    """断言最后一个 send 调用返回的是成功响应

    Args:
        session: mock session
        expected_type: 期望的消息类型（可选）
    """
    assert session._handler.send.called
    resp = session._handler.send.call_args[0][0]
    if expected_type:
        assert resp.get("type") == expected_type, f"期望 {expected_type}，实际 {resp.get('type')}"
    assert resp.get("ok", True) != False, f"响应标记为失败: {resp}"
    return resp


def assert_response_error(session, expected_type=MT.ERROR):
    """断言最后一个 send 调用返回的是错误响应

    Args:
        session: mock session
        expected_type: 期望的消息类型
    """
    assert session._handler.send.called
    resp = session._handler.send.call_args[0][0]
    assert resp.get("type") == expected_type or resp.get("ok") == False, \
        f"期望错误响应，实际: {resp}"
    return resp


def last_call(session):
    """获取最后一个 send 调用的参数"""
    assert session._handler.send.called, "session.send() 未被调用"
    return session._handler.send.call_args[0][0]


def all_calls(session):
    """获取所有 send 调用的参数列表"""
    return [c[0][0] for c in session._handler.send.call_args_list]
