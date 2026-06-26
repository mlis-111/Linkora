"""Friend 模块集成测试

测试好友模块与服务器框架的完整协作：
1. 好友申请流程（搜索用户 → 发起申请 → 通知接收方）
2. 同意申请流程（查找申请 → 双向加好友 → 刷新列表 → 通知）
3. 拒绝申请流程
4. 好友列表（含在线状态标注）
5. 删除好友（双向删除）
6. 备注设置
7. 完整好友生命周期（申请 → 同意 → 列表 → 删除）
"""

import pytest
from unittest.mock import MagicMock, call
from common.messages import MT
from server.modules.friend import (
    register as register_friend_module,
    handle_friend_add,
    handle_friend_agree,
    handle_friend_reject,
    handle_friend_list,
    handle_friend_remove,
    handle_friend_remark,
    handle_friend_req_list,
    handle_user_search,
)
from server.core.session import Session


# ════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════

def _make_online_handler():
    """创建一个 mock handler"""
    h = MagicMock()
    h.send = MagicMock()
    h.conn = MagicMock()
    return h


def _setup_target_user(ctx, uid=200, username="target_user", nickname="目标用户"):
    """配置目标用户查询 mock"""
    ctx.db.users.get_by_id.return_value = {
        "user_id": uid, "username": username, "nickname": nickname,
    }


def _setup_no_existing_friends(ctx):
    """配置：尚未添加任何好友"""
    ctx.db.friends.list_by_user.return_value = []
    ctx.db.friend_requests.find_reverse_pending.return_value = None


# ════════════════════════════════════════════════════════════════
# 模块注册测试
# ════════════════════════════════════════════════════════════════

class TestFriendModuleRegistration:
    """好友模块注册集成测试"""

    def test_registers_all_types(self, router, ctx):
        """注册所有好友消息类型"""
        register_friend_module(router, ctx)

        registered = set(router._handlers.keys())
        expected = {
            MT.FRIEND_ADD, MT.FRIEND_AGREE, MT.FRIEND_REJECT,
            MT.FRIEND_LIST, MT.FRIEND_REQ_LIST,
            MT.FRIEND_REMARK, MT.FRIEND_REMOVE,
            MT.USER_SEARCH,
        }
        missing = expected - registered
        assert not missing, f"缺少注册: {missing}"


# ════════════════════════════════════════════════════════════════
# 好友申请集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendAddIntegration:
    """好友申请完整流程集成测试"""

    def test_full_add_flow(self, ctx, session):
        """完整申请流程：查用户 → 查好友关系 → 创建申请 → 通知"""
        _setup_target_user(ctx)
        _setup_no_existing_friends(ctx)
        ctx.db.friend_requests.create.return_value = 1

        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "200"})

        # 1. 查询了目标用户
        ctx.db.users.get_by_id.assert_called_with(200)

        # 2. 创建了申请记录（不是直接加好友）
        ctx.db.friend_requests.create.assert_called_with(100, 200, "")

        # 3. 没有直接添加好友
        ctx.db.friends.add.assert_not_called()

        # 4. 返回成功响应
        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_ADD_RESP
        assert resp["ok"] is True
        assert "等待" in resp.get("message", "")

    def test_add_with_message(self, ctx, session):
        """带附言的申请"""
        _setup_target_user(ctx)
        _setup_no_existing_friends(ctx)

        handle_friend_add(session, {
            "type": MT.FRIEND_ADD,
            "target_id": "200",
            "message": "我是你的同学",
        })

        ctx.db.friend_requests.create.assert_called_with(100, 200, "我是你的同学")

    def test_add_self_rejected(self, session):
        """不能添加自己"""
        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "100"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "自己" in resp.get("reason", "")

    def test_add_nonexistent_user(self, ctx, session):
        """添加不存在的用户"""
        ctx.db.users.get_by_id.return_value = None

        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "999"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "不存在" in resp.get("reason", "")

    def test_add_already_friend(self, ctx, session):
        """对方已是好友"""
        _setup_target_user(ctx)
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target_user", "remark": ""}
        ]

        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "200"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "已是你的好友" in resp.get("reason", "")

    def test_add_pending_duplicate(self, ctx, session):
        """已有待处理申请时拒绝重复"""
        _setup_target_user(ctx)
        ctx.db.friends.list_by_user.return_value = []
        ctx.db.friend_requests.find_reverse_pending.return_value = {"id": 1}

        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "200"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False

    def test_add_notify_online_target(self, ctx, session):
        """目标用户在线时发送通知"""
        _setup_target_user(ctx)
        _setup_no_existing_friends(ctx)

        # 将目标用户加入在线表（使用真实 OnlineRegistry）
        target_handler = _make_online_handler()
        ctx.online.add(200, target_handler)

        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "200"})

        # 在线通知
        target_handler.send.assert_called()
        notify_msg = target_handler.send.call_args[0][0]
        assert notify_msg["type"] == MT.FRIEND_REQ_NOTIFY
        assert notify_msg["from_id"] == 100

    def test_add_empty_target_id(self, session):
        """空目标ID"""
        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": ""})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False


# ════════════════════════════════════════════════════════════════
# 用户搜索集成测试
# ════════════════════════════════════════════════════════════════

class TestUserSearchIntegration:
    """用户搜索集成测试"""

    def test_search_by_id(self, ctx, session):
        """按用户ID搜索（数字字符串自动解析为int）"""
        ctx.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "target", "nickname": "目标用户",
        }
        ctx.db.friends.list_by_user.return_value = []

        handle_user_search(session, {"target_id": "200"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.USER_SEARCH_RESP
        assert resp["ok"] is True
        assert resp["user"]["user_id"] == 200

    def test_search_by_username(self, ctx, session):
        """按用户名搜索（非数字字符串）"""
        ctx.db.users.get_by_id.return_value = None  # parseInt 失败走用户名查询
        ctx.db.users.get_by_username.return_value = {
            "user_id": 300, "username": "target_user", "nickname": "目标",
        }
        ctx.db.friends.list_by_user.return_value = []

        handle_user_search(session, {"target_id": "target_user"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.USER_SEARCH_RESP
        assert resp["ok"] is True
        assert resp["user"]["user_id"] == 300

    def test_search_by_nickname(self, ctx, session):
        """按昵称搜索（用户名找不到时尝试昵称）"""
        ctx.db.users.get_by_id.return_value = None
        ctx.db.users.get_by_username.return_value = None
        ctx.db.users.get_by_nickname.return_value = {
            "user_id": 400, "username": "user4", "nickname": "昵称搜索目标",
        }
        ctx.db.friends.list_by_user.return_value = []

        handle_user_search(session, {"target_id": "昵称搜索目标"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.USER_SEARCH_RESP
        assert resp["ok"] is True
        assert resp["user"]["user_id"] == 400

    def test_search_not_found(self, ctx, session):
        """搜索不到用户"""
        ctx.db.users.get_by_id.return_value = None
        ctx.db.users.get_by_username.return_value = None
        ctx.db.users.get_by_nickname.return_value = None

        handle_user_search(session, {"target_id": "nobody"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "未找到" in resp.get("reason", "")

    def test_search_cannot_be_self(self, ctx, session):
        """不能搜索自己"""
        ctx.db.users.get_by_id.return_value = {
            "user_id": 100, "username": "test_user", "nickname": "测试用户",
        }
        ctx.db.friends.list_by_user.return_value = []

        handle_user_search(session, {"target_id": "100"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False
        assert "自己" in resp.get("reason", "")

    def test_search_is_friend_flag(self, ctx, session):
        """搜索结果标注是否已是好友"""
        ctx.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "target", "nickname": "目标",
        }
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target", "remark": ""}
        ]

        handle_user_search(session, {"target_id": "200"})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is True
        assert resp["user"]["is_friend"] is True


# ════════════════════════════════════════════════════════════════
# 同意申请集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendAgreeIntegration:
    """同意好友申请完整流程集成测试"""

    def test_full_agree_flow(self, ctx, session):
        """完整同意流程：查申请 → 双向加好友 → 更新状态 → 刷新列表 → 通知"""
        ctx.db.friend_requests.find_pending.return_value = {"id": 1, "from_id": 200}
        ctx.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "applicant", "nickname": "申请人",
        }
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "new_friend", "remark": ""},
        ]

        handle_friend_agree(session, {"type": MT.FRIEND_AGREE, "from_id": 200})

        # 1. 双向加好友
        ctx.db.friends.add.assert_any_call(100, 200)
        ctx.db.friends.add.assert_any_call(200, 100)

        # 2. 更新申请状态为已同意（1）
        ctx.db.friend_requests.update_status.assert_called_with(1, 1)

        # 3. 返回同意响应
        calls = session._handler.send.call_args_list
        agree_resp = calls[0][0][0]
        assert agree_resp["type"] == MT.FRIEND_AGREE_RESP
        assert agree_resp["ok"] is True

    def test_agree_no_pending_request(self, ctx, session):
        """没有待处理申请"""
        ctx.db.friend_requests.find_pending.return_value = None

        handle_friend_agree(session, {"type": MT.FRIEND_AGREE, "from_id": 200})

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is False

    def test_agree_notifies_requester(self, ctx, session):
        """同意后通知申请发起方（如果在线）"""
        ctx.db.friend_requests.find_pending.return_value = {"id": 1, "from_id": 200}
        ctx.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "applicant", "nickname": "申请人",
        }
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "new_friend", "remark": ""},
        ]

        # 将申请人加入在线表
        applicant_handler = _make_online_handler()
        ctx.online.add(200, applicant_handler)

        handle_friend_agree(session, {"type": MT.FRIEND_AGREE, "from_id": 200})

        # 通知了申请方
        applicant_send_calls = [c[0][0] for c in applicant_handler.send.call_args_list]
        agree_notify = [m for m in applicant_send_calls
                        if m.get("type") == MT.FRIEND_AGREE_RESP and m.get("accepted")]
        assert len(agree_notify) > 0


# ════════════════════════════════════════════════════════════════
# 拒绝申请集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendRejectIntegration:
    """拒绝好友申请完整流程集成测试"""

    def test_full_reject_flow(self, ctx, session):
        """完整拒绝流程"""
        ctx.db.friend_requests.find_pending.return_value = {"id": 1}

        handle_friend_reject(session, {"type": MT.FRIEND_REJECT, "from_id": 200})

        ctx.db.friend_requests.reject.assert_called_with(1, "")

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_REJECT
        assert resp["ok"] is True

    def test_reject_with_reason(self, ctx, session):
        """带理由的拒绝"""
        ctx.db.friend_requests.find_pending.return_value = {"id": 1}

        handle_friend_reject(session, {
            "type": MT.FRIEND_REJECT,
            "from_id": 200,
            "reason": "不认识",
        })

        ctx.db.friend_requests.reject.assert_called_with(1, "不认识")

    def test_reject_notifies_online_applicant(self, ctx, session):
        """拒绝后通知申请方（在线时）"""
        ctx.db.friend_requests.find_pending.return_value = {"id": 1}

        applicant_handler = _make_online_handler()
        ctx.online.add(200, applicant_handler)

        handle_friend_reject(session, {
            "type": MT.FRIEND_REJECT,
            "from_id": 200,
            "reason": "不认识",
        })

        # 通知了申请方
        applicant_handler.send.assert_called()
        notify_msg = applicant_handler.send.call_args[0][0]
        assert notify_msg["type"] == MT.FRIEND_REJECTED


# ════════════════════════════════════════════════════════════════
# 好友列表集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendListIntegration:
    """好友列表查询集成测试"""

    def test_list_with_online_status(self, ctx, session):
        """好友列表标注在线状态"""
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "online_friend", "remark": ""},
            {"user_id": 201, "username": "offline_friend", "remark": "备注名"},
        ]
        # 将 200 加入在线表
        online_handler = _make_online_handler()
        ctx.online.add(200, online_handler)

        handle_friend_list(session, {"type": MT.FRIEND_LIST})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_LIST_RESP

        online_f = next(f for f in resp["friends"] if f["user_id"] == 200)
        offline_f = next(f for f in resp["friends"] if f["user_id"] == 201)
        assert online_f["online"] is True
        assert offline_f["online"] is False

    def test_empty_list(self, ctx, session):
        """空好友列表"""
        ctx.db.friends.list_by_user.return_value = []

        handle_friend_list(session, {"type": MT.FRIEND_LIST})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_LIST_RESP
        assert len(resp["friends"]) == 0


# ════════════════════════════════════════════════════════════════
# 删除好友集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendRemoveIntegration:
    """删除好友集成测试"""

    def test_full_remove_flow(self, ctx, session):
        """完整删除流程：双向删除 → 刷新列表"""
        ctx.db.friends.delete.return_value = 1
        ctx.db.friends.list_by_user.return_value = []

        handle_friend_remove(session, {"type": MT.FRIEND_REMOVE, "friend_id": 200})

        # 双向删除
        ctx.db.friends.delete.assert_called_with(100, 200)

        # 返回删除结果
        calls = session._handler.send.call_args_list
        remove_resp = calls[0][0][0]
        assert remove_resp["type"] == MT.FRIEND_REMOVE_RESP
        assert remove_resp["ok"] is True

    def test_remove_missing_id(self, session):
        """缺少好友ID"""
        handle_friend_remove(session, {"type": MT.FRIEND_REMOVE})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_REMOVE_RESP
        assert resp["ok"] is False


# ════════════════════════════════════════════════════════════════
# 备注设置集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendRemarkIntegration:
    """好友备注集成测试"""

    def test_set_remark(self, ctx, session):
        """设置备注后刷新好友列表"""
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target", "remark": "新备注"},
        ]

        handle_friend_remark(session, {
            "type": MT.FRIEND_REMARK,
            "friend_id": 200,
            "remark": "新备注",
        })

        ctx.db.friends.set_remark.assert_called_with(100, 200, "新备注")

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_LIST_RESP

    def test_remark_missing_friend_id(self, session):
        """缺少好友ID"""
        handle_friend_remark(session, {
            "type": MT.FRIEND_REMARK,
            "remark": "备注",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ════════════════════════════════════════════════════════════════
# 完整好友生命周期测试
# ════════════════════════════════════════════════════════════════

class TestFriendFullLifecycle:
    """好友完整生命周期：申请 → 同意 → 列表 → 删除"""

    def test_full_lifecycle(self, ctx, session):
        """模拟申请 → 同意 → 列表 → 删除 的完整流程"""
        # === Phase 1: 发起申请 ===
        ctx.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "target", "nickname": "目标用户",
        }
        ctx.db.friends.list_by_user.return_value = []
        ctx.db.friend_requests.find_reverse_pending.return_value = None
        ctx.db.friend_requests.create.return_value = 1

        handle_friend_add(session, {"type": MT.FRIEND_ADD, "target_id": "200"})

        add_resp = session._handler.send.call_args_list[-1][0][0]
        assert add_resp["type"] == MT.FRIEND_ADD_RESP
        assert add_resp["ok"] is True

        # === Phase 2: 对方同意（用200用户的视角） ===
        second_handler = MagicMock()
        second_handler.send = MagicMock()
        second_handler.conn = MagicMock()
        target_session = Session(ctx, second_handler)
        target_session.bind_user(200, "target")

        ctx.db.friend_requests.find_pending.return_value = {"id": 1, "from_id": 100}
        ctx.db.users.get_by_id.return_value = {
            "user_id": 100, "username": "test_user", "nickname": "测试用户",
        }
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 100, "username": "test_user", "remark": ""},
        ]
        ctx.db.friends.add.reset_mock()

        handle_friend_agree(target_session, {"type": MT.FRIEND_AGREE, "from_id": 100})

        # 双向加好友
        ctx.db.friends.add.assert_any_call(200, 100)
        ctx.db.friends.add.assert_any_call(100, 200)

        agree_resp = target_session._handler.send.call_args_list[0][0][0]
        assert agree_resp["type"] == MT.FRIEND_AGREE_RESP
        assert agree_resp["ok"] is True

        # === Phase 3: 查看好友列表 ===
        ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target", "remark": ""},
        ]

        handle_friend_list(session, {"type": MT.FRIEND_LIST})

        list_resp = session._handler.send.call_args_list[-1][0][0]
        assert list_resp["type"] == MT.FRIEND_LIST_RESP
        assert len(list_resp["friends"]) == 1
        assert list_resp["friends"][0]["user_id"] == 200

        # === Phase 4: 删除好友 ===
        ctx.db.friends.delete.return_value = 1

        handle_friend_remove(session, {"type": MT.FRIEND_REMOVE, "friend_id": 200})

        ctx.db.friends.delete.assert_called_with(100, 200)


# ════════════════════════════════════════════════════════════════
# Router 分发集成测试
# ════════════════════════════════════════════════════════════════

class TestFriendRouterIntegration:
    """通过 Router 分发好友消息的集成测试"""

    def test_friend_add_via_router(self, router, ctx, session):
        """通过 Router dispatch FRIEND_ADD 消息"""
        register_friend_module(router, ctx)
        _setup_target_user(ctx)
        _setup_no_existing_friends(ctx)

        router.dispatch(session, {"type": MT.FRIEND_ADD, "target_id": "200"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_ADD_RESP
        assert resp["ok"] is True

    def test_friend_list_via_router(self, router, ctx, session):
        """通过 Router dispatch FRIEND_LIST 消息"""
        register_friend_module(router, ctx)
        ctx.db.friends.list_by_user.return_value = []

        router.dispatch(session, {"type": MT.FRIEND_LIST})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_LIST_RESP

    def test_user_search_via_router(self, router, ctx, session):
        """通过 Router dispatch USER_SEARCH 消息"""
        register_friend_module(router, ctx)
        ctx.db.users.get_by_id.return_value = {
            "user_id": 200, "username": "target", "nickname": "目标",
        }
        ctx.db.friends.list_by_user.return_value = []

        router.dispatch(session, {"type": MT.USER_SEARCH, "target_id": "200"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.USER_SEARCH_RESP
        assert resp["ok"] is True
