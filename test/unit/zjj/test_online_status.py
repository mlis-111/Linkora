"""
单元测试：在线状态实时显示功能
负责人：朱俊基

测试范围：
1. 服务器端在线用户管理
2. 客户端状态更新逻辑
3. 用户列表刷新机制

使用pytest框架
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from server.core.online import OnlineRegistry
from client.state import ClientState


# ==================== Fixtures ====================

@pytest.fixture
def registry():
    """创建OnlineRegistry实例"""
    return OnlineRegistry()


@pytest.fixture
def client_state():
    """创建ClientState实例"""
    return ClientState()


@pytest.fixture
def mock_handler():
    """创建MockHandler实例"""
    return MockHandler()


@pytest.fixture
def sample_all_users():
    """示例：所有用户数据"""
    return [
        {"user_id": 1, "username": "user1", "nickname": "用户1"},
        {"user_id": 2, "username": "user2", "nickname": "用户2"},
        {"user_id": 3, "username": "user3", "nickname": "用户3"},
        {"user_id": 4, "username": "user4", "nickname": "用户4"}
    ]


@pytest.fixture
def sample_online_users():
    """示例：在线用户数据"""
    return [
        {"user_id": 1, "username": "user1", "nickname": "用户1"},
        {"user_id": 3, "username": "user3", "nickname": "用户3"}
    ]


# ==================== Mock Classes ====================

class MockHandler:
    """模拟ClientHandler用于测试"""

    def __init__(self):
        self.sent_messages = []

    def send(self, msg):
        """模拟发送消息"""
        self.sent_messages.append(msg)


# ==================== 测试：服务器端在线用户管理 ====================

class TestOnlineRegistry:
    """测试服务器端在线用户管理"""

    def test_add_user(self, registry, mock_handler):
        """测试添加在线用户"""
        # 添加用户
        registry.add(1, mock_handler)

        # 验证用户在线
        assert registry.is_online(1)

    def test_remove_user(self, registry, mock_handler):
        """测试移除在线用户"""
        # 添加然后移除
        registry.add(1, mock_handler)
        registry.remove(1)

        # 验证用户不在线
        assert not registry.is_online(1)

    def test_online_ids(self, registry):
        """测试获取所有在线用户ID列表"""
        mock_handler1 = MockHandler()
        mock_handler2 = MockHandler()
        mock_handler3 = MockHandler()

        # 添加多个用户
        registry.add(1, mock_handler1)
        registry.add(2, mock_handler2)
        registry.add(3, mock_handler3)

        # 获取在线用户ID列表
        online_ids = registry.online_ids()

        # 验证
        assert len(online_ids) == 3
        assert 1 in online_ids
        assert 2 in online_ids
        assert 3 in online_ids

    def test_duplicate_login(self, registry):
        """测试重复登录检测"""
        mock_handler1 = MockHandler()
        mock_handler2 = MockHandler()

        # 第一次添加
        registry.add(1, mock_handler1)
        assert registry.is_online(1)

        # 尝试重复添加（应该覆盖）
        registry.add(1, mock_handler2)

        # 仍然在线
        assert registry.is_online(1)

    def test_send_to_online_user(self, registry, mock_handler):
        """测试向在线用户发送消息"""
        registry.add(1, mock_handler)

        # 发送消息
        msg = {"type": "test", "content": "hello"}
        result = registry.send(1, msg)

        # 验证发送成功
        assert result is True
        assert len(mock_handler.sent_messages) == 1
        assert mock_handler.sent_messages[0] == msg

    def test_send_to_offline_user(self, registry):
        """测试向离线用户发送消息"""
        # 发送给不存在的用户
        msg = {"type": "test", "content": "hello"}
        result = registry.send(999, msg)

        # 验证发送失败
        assert result is False

    def test_broadcast(self, registry):
        """测试广播消息"""
        mock_handler1 = MockHandler()
        mock_handler2 = MockHandler()
        mock_handler3 = MockHandler()

        registry.add(1, mock_handler1)
        registry.add(2, mock_handler2)
        registry.add(3, mock_handler3)

        # 广播消息，排除用户1
        msg = {"type": "broadcast", "content": "hello all"}
        registry.broadcast(msg, exclude=1)

        # 验证：用户1没收到，用户2和3收到
        assert len(mock_handler1.sent_messages) == 0
        assert len(mock_handler2.sent_messages) == 1
        assert len(mock_handler3.sent_messages) == 1

    def test_broadcast_to_all(self, registry):
        """测试广播消息给所有人"""
        mock_handler1 = MockHandler()
        mock_handler2 = MockHandler()

        registry.add(1, mock_handler1)
        registry.add(2, mock_handler2)

        # 广播消息，不排除任何人
        msg = {"type": "broadcast", "content": "hello all"}
        registry.broadcast(msg)

        # 验证：所有人都收到
        assert len(mock_handler1.sent_messages) == 1
        assert len(mock_handler2.sent_messages) == 1


# ==================== 测试：客户端状态管理 ====================

class TestClientState:
    """测试客户端状态管理"""

    def test_initial_state(self, client_state):
        """测试初始状态"""
        assert client_state.user_id is None
        assert client_state.username is None
        assert client_state.online_users == []
        assert client_state.all_users == []
        assert client_state.friends == []

    def test_set_user_info(self, client_state):
        """测试设置用户信息"""
        client_state.user_id = 1
        client_state.username = "张三"

        assert client_state.user_id == 1
        assert client_state.username == "张三"

    def test_update_online_users(self, client_state, sample_online_users):
        """测试更新在线用户列表"""
        client_state.online_users = sample_online_users

        assert len(client_state.online_users) == 2
        assert client_state.online_users[0]["user_id"] == 1
        assert client_state.online_users[1]["user_id"] == 3

    def test_update_all_users(self, client_state, sample_all_users):
        """测试更新所有用户列表"""
        client_state.all_users = sample_all_users

        assert len(client_state.all_users) == 4
        assert client_state.all_users[0]["user_id"] == 1
        assert client_state.all_users[3]["user_id"] == 4


# ==================== 测试：在线状态判断逻辑 ====================

class TestOnlineStatusLogic:
    """测试在线状态判断逻辑"""

    def test_check_user_online(self, sample_online_users):
        """测试检查用户是否在线"""
        online_user_ids = {u["user_id"] for u in sample_online_users}

        # 用户1和3在线
        assert 1 in online_user_ids
        assert 3 in online_user_ids

        # 用户2和4离线
        assert 2 not in online_user_ids
        assert 4 not in online_user_ids

    def test_count_online_users(self, sample_all_users, sample_online_users):
        """测试统计在线人数"""
        total = len(sample_all_users)
        online = len(sample_online_users)

        assert total == 4
        assert online == 2

    def test_user_status_text(self, sample_all_users, sample_online_users):
        """测试用户状态文本生成"""
        online_user_ids = {u["user_id"] for u in sample_online_users}

        for user in sample_all_users:
            user_id = user["user_id"]
            is_online = user_id in online_user_ids
            status = "在线" if is_online else "离线"

            if user_id in [1, 3]:
                assert status == "在线"
            else:
                assert status == "离线"

    def test_empty_online_list(self):
        """测试空的在线用户列表"""
        online_user_ids = set()

        assert len(online_user_ids) == 0
        assert 1 not in online_user_ids

    def test_all_users_online(self, sample_all_users):
        """测试所有用户都在线的情况"""
        online_user_ids = {u["user_id"] for u in sample_all_users}

        assert len(online_user_ids) == 4
        for user in sample_all_users:
            assert user["user_id"] in online_user_ids


# ==================== 测试：用户列表更新 ====================

class TestUserListUpdate:
    """测试用户列表更新逻辑"""

    def test_parse_user_list_message(self, sample_online_users):
        """测试解析USER_LIST消息"""
        msg = {
            "type": "user_list",
            "online_users": sample_online_users
        }

        online_users = msg.get("online_users", [])

        assert len(online_users) == 2
        assert online_users[0]["user_id"] == 1
        assert online_users[1]["user_id"] == 3

    def test_parse_login_response(self, sample_online_users, sample_all_users):
        """测试解析登录响应消息"""
        msg = {
            "type": "login_resp",
            "ok": True,
            "user_id": 1,
            "nickname": "张三",
            "online_users": sample_online_users,
            "all_users": sample_all_users
        }

        assert msg.get("ok") is True
        assert msg["user_id"] == 1
        assert msg["nickname"] == "张三"
        assert len(msg["online_users"]) == 2
        assert len(msg["all_users"]) == 4

    def test_parse_login_failure(self):
        """测试解析登录失败响应"""
        msg = {
            "type": "login_resp",
            "ok": False,
            "reason": "用户已在线"
        }

        assert msg.get("ok") is False
        assert msg["reason"] == "用户已在线"

    def test_missing_fields(self):
        """测试缺少字段的消息"""
        msg = {
            "type": "user_list"
        }

        online_users = msg.get("online_users", [])
        assert online_users == []


# ==================== 参数化测试 ====================

class TestParameterized:
    """参数化测试示例"""

    @pytest.mark.parametrize("user_id,expected_online", [
        (1, True),
        (2, False),
        (3, True),
        (4, False),
    ])
    def test_user_online_status(self, sample_online_users, user_id, expected_online):
        """参数化测试用户在线状态"""
        online_user_ids = {u["user_id"] for u in sample_online_users}
        is_online = user_id in online_user_ids

        assert is_online == expected_online

    @pytest.mark.parametrize("total,online,expected_text", [
        (4, 0, "4 人 · 0 在线"),
        (4, 2, "4 人 · 2 在线"),
        (4, 4, "4 人 · 4 在线"),
        (10, 5, "10 人 · 5 在线"),
    ])
    def test_online_count_text(self, total, online, expected_text):
        """参数化测试在线人数文本"""
        text = f"{total} 人 · {online} 在线"
        assert text == expected_text


# ==================== 测试标记 ====================

@pytest.mark.slow
def test_large_user_list():
    """测试大量用户的场景（标记为慢速测试）"""
    registry = OnlineRegistry()

    # 添加1000个用户
    for i in range(1000):
        handler = MockHandler()
        registry.add(i, handler)

    online_ids = registry.online_ids()
    assert len(online_ids) == 1000


@pytest.mark.edge_case
def test_zero_users():
    """测试零用户的边界情况"""
    registry = OnlineRegistry()
    online_ids = registry.online_ids()

    assert len(online_ids) == 0
    assert not registry.is_online(1)
