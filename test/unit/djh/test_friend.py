"""Friend 模块单元测试

覆盖内容:
1. 正常添加好友（申请模式）
2. 异常添加（自己/不存在/已好友/已申请）
3. 同意好友申请
4. 拒绝好友申请
5. 查询待处理申请
6. 设置备注
7. 好友列表查询（含在线状态）

author: 董钧豪
"""

import pytest
from unittest.mock import MagicMock
from common.messages import MT


# ========== Fixtures ==========

@pytest.fixture
def mock_ctx():
    """创建 Mock ServerContext"""
    ctx = MagicMock()
    ctx.db.users.get_by_id.return_value = {"user_id": 200, "username": "target_user"}
    ctx.db.friends.list_by_user.return_value = []
    ctx.db.friend_requests.find_reverse_pending.return_value = None
    ctx.db.friend_requests.create.return_value = 1
    ctx.online.is_online.return_value = False
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
        """验证注册全部消息类型"""
        from server.modules import friend
        router = MagicMock()
        ctx = MagicMock()
        friend.register(router, ctx)
        # 新增 FRIEND_REMOVE handler
        assert router.register.call_count == 7
        types = [call[0][0] for call in router.register.call_args_list]
        assert MT.FRIEND_ADD in types
        assert MT.FRIEND_REMARK in types
        assert MT.FRIEND_LIST in types
        assert MT.FRIEND_AGREE in types
        assert MT.FRIEND_REJECT in types
        assert MT.FRIEND_REQ_LIST in types
        assert MT.FRIEND_REMOVE in types


# ========== 添加好友测试 ==========

class TestHandleFriendAdd:
    """添加好友处理测试（申请模式）"""

    def test_normal_add(self, mock_session, mock_ctx):
        """正常发起好友申请"""
        from server.modules.friend import handle_friend_add
        handle_friend_add(mock_session, {"target_id": "200"})

        # 验证按 ID 查询目标用户
        mock_ctx.db.users.get_by_id.assert_called_with(200)

        # 验证创建好友申请（不是直接加好友）
        mock_ctx.db.friend_requests.create.assert_called_with(100, 200, "")
        mock_ctx.db.friends.add.assert_not_called()

        # 验证响应
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_ADD_RESP
        assert resp["ok"] == True
        assert "等待对方同意" in resp.get("message", "")

    def test_add_self(self, mock_session):
        """不能添加自己为好友"""
        from server.modules.friend import handle_friend_add
        handle_friend_add(mock_session, {"target_id": "100"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == False
        assert "自己" in resp.get("reason", "")

    def test_add_nonexistent(self, mock_session, mock_ctx):
        """添加不存在的用户"""
        from server.modules.friend import handle_friend_add
        mock_ctx.db.users.get_by_id.return_value = None
        handle_friend_add(mock_session, {"target_id": "999"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == False
        assert "不存在" in resp.get("reason", "")

    def test_add_duplicate(self, mock_session, mock_ctx):
        """添加已是好友的用户"""
        from server.modules.friend import handle_friend_add
        mock_ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target_user"}
        ]
        handle_friend_add(mock_session, {"target_id": "200"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == False
        assert "已是你的好友" in resp.get("reason", "")

    def test_add_pending(self, mock_session, mock_ctx):
        """重复发起申请"""
        from server.modules.friend import handle_friend_add
        mock_ctx.db.friend_requests.find_reverse_pending.return_value = {"id": 1}
        handle_friend_add(mock_session, {"target_id": "200"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == False

    def test_add_empty_id(self, mock_session):
        """空 ID 返回错误"""
        from server.modules.friend import handle_friend_add
        handle_friend_add(mock_session, {"target_id": ""})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == False

    def test_add_notify_target(self, mock_session, mock_ctx):
        """申请时通知接收方（如果在线）"""
        from server.modules.friend import handle_friend_add
        mock_ctx.online.is_online.return_value = True
        handle_friend_add(mock_session, {"target_id": "200"})

        mock_ctx.online.send.assert_called()
        call_args = mock_ctx.online.send.call_args[0]
        assert call_args[0] == 200  # 发给 target
        assert call_args[1]["type"] == MT.FRIEND_REQ_NOTIFY


# ========== 同意好友申请测试 ==========

class TestHandleFriendAgree:
    """同意好友申请处理测试"""

    def test_normal_agree(self, mock_session, mock_ctx):
        """正常同意申请，双向加好友"""
        from server.modules.friend import handle_friend_agree
        mock_ctx.db.friend_requests.find_pending.return_value = {"id": 1, "from_id": 200}
        mock_ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target_user", "remark": ""},
        ]
        handle_friend_agree(mock_session, {"from_id": 200})

        # 验证更新申请状态
        mock_ctx.db.friend_requests.update_status.assert_called_with(1, 1)
        # 验证双向添加好友
        mock_ctx.db.friends.add.assert_any_call(100, 200)
        mock_ctx.db.friends.add.assert_any_call(200, 100)
        # 验证响应
        resp = mock_session.send.call_args_list[0][0][0]
        assert resp["type"] == MT.FRIEND_AGREE_RESP
        assert resp["ok"] == True

    def test_agree_no_request(self, mock_session, mock_ctx):
        """同意不存在的申请"""
        from server.modules.friend import handle_friend_agree
        mock_ctx.db.friend_requests.find_pending.return_value = None
        handle_friend_agree(mock_session, {"from_id": 200})

        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == False


# ========== 拒绝好友申请测试 ==========

class TestHandleFriendReject:
    """拒绝好友申请处理测试"""

    def test_normal_reject(self, mock_session, mock_ctx):
        """正常拒绝申请"""
        from server.modules.friend import handle_friend_reject
        mock_ctx.db.friend_requests.find_pending.return_value = {"id": 1}
        handle_friend_reject(mock_session, {"from_id": 200})

        mock_ctx.db.friend_requests.reject.assert_called_with(1, "")


# ========== 查询待处理申请测试 ==========

class TestHandleFriendReqList:
    """待处理申请查询测试"""

    def test_normal_list(self, mock_session, mock_ctx):
        """查询待处理申请列表"""
        from server.modules.friend import handle_friend_req_list
        mock_ctx.db.friend_requests.list_incoming.return_value = [
            {"id": 1, "from_id": 200, "username": "applicant", "nickname": ""},
        ]
        handle_friend_req_list(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_REQ_LIST_RESP
        assert len(resp["requests"]) == 1


# ========== 设置备注测试 ==========

class TestHandleFriendRemark:
    """设置备注处理测试"""

    def test_normal_remark(self, mock_session, mock_ctx):
        """正常设置备注"""
        from server.modules.friend import handle_friend_remark
        mock_ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "target_user", "remark": "备注名"}
        ]
        handle_friend_remark(mock_session, {"friend_id": 200, "remark": "新备注"})

        mock_ctx.db.friends.set_remark.assert_called_with(100, 200, "新备注")
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_LIST_RESP

    def test_missing_friend_id(self, mock_session):
        """缺少好友ID返回错误"""
        from server.modules.friend import handle_friend_remark
        handle_friend_remark(mock_session, {"remark": "备注"})
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 好友列表测试 ==========

class TestHandleFriendList:
    """好友列表查询测试"""

    def test_normal_list(self, mock_session, mock_ctx):
        """正常查询好友列表"""
        from server.modules.friend import handle_friend_list
        mock_ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "friend1", "remark": ""},
            {"user_id": 201, "username": "friend2", "remark": "备注名"},
        ]
        handle_friend_list(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_LIST_RESP
        assert len(resp["friends"]) == 2
        for f in resp["friends"]:
            assert "online" in f

    def test_empty_list(self, mock_session, mock_ctx):
        """空好友列表"""
        from server.modules.friend import handle_friend_list
        mock_ctx.db.friends.list_by_user.return_value = []
        handle_friend_list(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert len(resp["friends"]) == 0

    def test_online_status(self, mock_session, mock_ctx):
        """好友在线状态标注"""
        from server.modules.friend import handle_friend_list
        mock_ctx.db.friends.list_by_user.return_value = [
            {"user_id": 200, "username": "online_friend", "remark": ""},
            {"user_id": 201, "username": "offline_friend", "remark": ""},
        ]
        mock_ctx.online.is_online.side_effect = lambda uid: uid == 200

        handle_friend_list(mock_session, {})
        resp = mock_session.send.call_args[0][0]

        online_f = next(f for f in resp["friends"] if f["user_id"] == 200)
        offline_f = next(f for f in resp["friends"] if f["user_id"] == 201)
        assert online_f["online"] == True
        assert offline_f["online"] == False


class TestHandleRemove:
    """删除好友"""

    def test_normal_remove(self, mock_session, mock_ctx):
        """正常删除好友"""
        from server.modules.friend import handle_friend_remove
        mock_ctx.db.friends.delete.return_value = 1
        handle_friend_remove(mock_session, {"friend_id": 200})

        mock_ctx.db.friends.delete.assert_called_with(100, 200)
        mock_session.send.assert_called()
        calls = mock_session.send.call_args_list
        # 第一次调用是删除结果，第二次是刷新好友列表
        assert calls[0][0][0]["type"] == MT.FRIEND_REMOVE_RESP
        assert calls[0][0][0]["ok"] == True

    def test_remove_missing_id(self, mock_session, mock_ctx):
        """缺少好友ID"""
        from server.modules.friend import handle_friend_remove
        handle_friend_remove(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.FRIEND_REMOVE_RESP
        assert resp["ok"] == False
        assert "好友ID" in resp["reason"]
