"""Group 模块单元测试

覆盖内容:
1. 创建群聊成功（含邀请成员）
2. 加入公共群（选择加入）
3. 重复加入返回错误
4. 查询我的群列表
5. 邀请好友入群
6. 参数异常处理

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
    # GroupDAO 默认返回值
    ctx.db.groups.get_by_id.return_value = {"group_id": 1, "group_name": "公共聊天室", "owner_id": None}
    ctx.db.groups.is_member.return_value = False
    ctx.db.groups.create.return_value = 1
    ctx.db.groups.add_member.return_value = 1
    ctx.db.groups.list_by_user.return_value = []
    ctx.db.groups.list_available.return_value = []
    ctx.db.groups.list_members.return_value = []
    ctx.db.groups.list_member_ids.return_value = []
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
        """验证 group 模块注册了全部消息类型"""
        from server.modules import group
        router = MagicMock()
        ctx = MagicMock()
        group.register(router, ctx)
        assert router.register.call_count == 10
        types_registered = [call[0][0] for call in router.register.call_args_list]
        assert MT.GROUP_CREATE in types_registered
        assert MT.GROUP_JOIN in types_registered
        assert MT.GROUP_LIST in types_registered
        assert MT.GROUP_MEMBERS in types_registered
        assert MT.GROUP_INVITE in types_registered
        assert MT.GROUP_INFO in types_registered
        assert MT.GROUP_UPDATE_NAME in types_registered
        assert MT.GROUP_SET_REMARK in types_registered
        assert MT.GROUP_REMOVE_MEMBER in types_registered
        assert MT.GROUP_SET_ADMIN in types_registered


# ========== 创建群聊测试 ==========

class TestHandleCreate:
    """创建群聊处理测试"""

    def test_normal_create(self, mock_session, mock_ctx):
        """正常创建群聊（不带邀请）"""
        from server.modules.group import _handle_create
        _handle_create(mock_session, {"group_name": "测试群"})

        # 验证创建群聊
        mock_ctx.db.groups.create.assert_called_with("测试群", 100)

        # 验证创建者自动加入
        created_group_id = mock_ctx.db.groups.create.return_value
        mock_ctx.db.groups.add_member.assert_called_with(created_group_id, 100)

        # 验证响应
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_CREATE_RESP
        assert resp["ok"] == True
        assert resp["group_name"] == "测试群"

    def test_create_with_invitees(self, mock_session, mock_ctx):
        """创建群聊并邀请好友"""
        from server.modules.group import _handle_create
        _handle_create(mock_session, {"group_name": "好友群", "invitees": [200, 201]})

        # 验证邀请好友加入
        created_group_id = mock_ctx.db.groups.create.return_value
        # add_member 被调用 3 次：创建者 + 2 个好友
        assert mock_ctx.db.groups.add_member.call_count == 3

        # 验证响应包含 added 列表
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["added"] == [200, 201]

    def test_create_empty_name(self, mock_session):
        """空群名返回错误"""
        from server.modules.group import _handle_create
        _handle_create(mock_session, {"group_name": "  "})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "名称" in resp.get("message", "")

    def test_create_skip_self_in_invitees(self, mock_session, mock_ctx):
        """邀请列表包含自己时应跳过"""
        from server.modules.group import _handle_create
        _handle_create(mock_session, {"group_name": "群", "invitees": [100, 200]})

        # 创建者已在创建时加入，不应重复 add_member
        created_group_id = mock_ctx.db.groups.create.return_value
        # 应该只 add_member 100(创建时) 和 200(邀请)
        # 由于跳过自己，add_member 只调用 2 次（创建者 + 200）
        assert mock_ctx.db.groups.add_member.call_count == 2


# ========== 加入群聊测试 ==========

class TestHandleJoin:
    """加入群聊处理测试"""

    def test_normal_join(self, mock_session, mock_ctx):
        """正常加入公共群"""
        from server.modules.group import _handle_join
        _handle_join(mock_session, {"group_id": 1})

        mock_ctx.db.groups.add_member.assert_called_with(1, 100)
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_JOIN_RESP
        assert resp["ok"] == True
        assert resp["group_id"] == 1

    def test_join_already_member(self, mock_session, mock_ctx):
        """重复加入返回错误"""
        from server.modules.group import _handle_join
        mock_ctx.db.groups.is_member.return_value = True
        _handle_join(mock_session, {"group_id": 1})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "已在群中" in resp.get("message", "")

    def test_join_nonexistent_group(self, mock_session, mock_ctx):
        """加入不存在的群"""
        from server.modules.group import _handle_join
        mock_ctx.db.groups.get_by_id.return_value = None
        _handle_join(mock_session, {"group_id": 999})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不存在" in resp.get("message", "")

    def test_join_missing_id(self, mock_session):
        """缺少 group_id 返回错误"""
        from server.modules.group import _handle_join
        _handle_join(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 查询群列表测试 ==========

class TestHandleList:
    """群聊列表查询测试"""

    def test_list_my_groups(self, mock_session, mock_ctx):
        """查询我的群聊列表"""
        from server.modules.group import _handle_list
        mock_ctx.db.groups.list_by_user.return_value = [
            {"group_id": 1, "group_name": "公共聊天室", "owner_id": None, "joined_at": "2024-01-01"},
            {"group_id": 2, "group_name": "好友群", "owner_id": 100, "joined_at": "2024-01-02"},
        ]
        mock_ctx.db.groups.list_available.return_value = [
            {"group_id": 3, "group_name": "技术交流群"},
        ]

        _handle_list(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_LIST_RESP
        assert len(resp["my_groups"]) == 2
        assert len(resp["available"]) == 1
        assert resp["my_groups"][0]["group_id"] == 1
        assert resp["available"][0]["group_id"] == 3

    def test_list_empty(self, mock_session, mock_ctx):
        """没有群聊时返回空列表"""
        from server.modules.group import _handle_list
        _handle_list(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_LIST_RESP
        assert len(resp["my_groups"]) == 0
        assert len(resp["available"]) == 0


# ========== 群成员查询测试 ==========

class TestHandleMembers:
    """群成员查询测试"""

    def test_normal_members(self, mock_session, mock_ctx):
        """查询群成员列表"""
        from server.modules.group import _handle_members
        mock_ctx.db.groups.list_members.return_value = [
            {"user_id": 100, "username": "test_user", "nickname": ""},
            {"user_id": 200, "username": "friend1", "nickname": "好友1"},
        ]

        _handle_members(mock_session, {"group_id": 1})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_MEMBERS_RESP
        assert resp["group_id"] == 1
        assert len(resp["members"]) == 2

    def test_members_nonexistent_group(self, mock_session, mock_ctx):
        """查询不存在的群成员"""
        from server.modules.group import _handle_members
        mock_ctx.db.groups.get_by_id.return_value = None
        _handle_members(mock_session, {"group_id": 999})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 邀请好友测试 ==========

class TestHandleInvite:
    """邀请好友入群测试"""

    def test_normal_invite(self, mock_session, mock_ctx):
        """正常邀请好友"""
        from server.modules.group import _handle_invite
        mock_ctx.db.groups.is_member.side_effect = lambda gid, uid: uid == 100  # 只有创建者是成员
        mock_ctx.db.groups.add_member.return_value = 1

        _handle_invite(mock_session, {"group_id": 2, "invitees": [200, 201]})

        # 验证邀请
        assert mock_ctx.db.groups.add_member.call_count == 2
        mock_ctx.db.groups.add_member.assert_any_call(2, 200)
        mock_ctx.db.groups.add_member.assert_any_call(2, 201)

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == True

    def test_invite_not_member(self, mock_session, mock_ctx):
        """非群成员邀请返回错误"""
        from server.modules.group import _handle_invite
        mock_ctx.db.groups.is_member.return_value = False

        _handle_invite(mock_session, {"group_id": 2, "invitees": [200]})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不是该群成员" in resp.get("message", "")

    def test_invite_already_member(self, mock_session, mock_ctx):
        """邀请已在群中的用户"""
        from server.modules.group import _handle_invite
        mock_ctx.db.groups.is_member.side_effect = lambda gid, uid: uid in [100, 200]

        _handle_invite(mock_session, {"group_id": 2, "invitees": [200, 201]})

        # 200 已在群中，只有 201 被加入
        mock_ctx.db.groups.add_member.assert_called_once_with(2, 201)
        resp = mock_session.send.call_args[0][0]
        assert resp["skipped"] == [200]

    def test_invite_missing_params(self, mock_session):
        """缺少参数返回错误"""
        from server.modules.group import _handle_invite
        _handle_invite(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 群设置信息查询测试 ==========

class TestHandleInfoReq:
    """群设置信息查询测试"""

    def test_normal_info(self, mock_session, mock_ctx):
        """正常查询群设置信息"""
        from server.modules.group import _handle_info_req
        mock_ctx.db.groups.is_member.return_value = True
        mock_ctx.db.groups.list_members.return_value = [
            {"user_id": 100, "username": "owner", "nickname": "", "role": 1},
            {"user_id": 200, "username": "member1", "nickname": "成员1", "role": 0},
        ]
        mock_ctx.db.groups.get_role.return_value = 0
        mock_ctx.online.is_online.return_value = False

        _handle_info_req(mock_session, {"group_id": 2})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_INFO_RESP
        assert resp["group_id"] == 2
        assert resp["group_name"] == "公共聊天室"
        assert resp["owner_id"] is None
        assert resp["my_role"] == 0
        assert len(resp["members"]) == 2

    def test_info_nonexistent_group(self, mock_session, mock_ctx):
        """查询不存在的群"""
        from server.modules.group import _handle_info_req
        mock_ctx.db.groups.get_by_id.return_value = None
        _handle_info_req(mock_session, {"group_id": 999})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_info_not_member(self, mock_session, mock_ctx):
        """非群成员查询返回错误"""
        from server.modules.group import _handle_info_req
        mock_ctx.db.groups.is_member.return_value = False
        _handle_info_req(mock_session, {"group_id": 2})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_info_missing_id(self, mock_session):
        """缺少 group_id 返回错误"""
        from server.modules.group import _handle_info_req
        _handle_info_req(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 更新群名测试 ==========

class TestHandleUpdateName:
    """更新群名测试"""

    def test_owner_update_name(self, mock_session, mock_ctx):
        """群主更新群名"""
        from server.modules.group import _handle_update_name
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "旧名", "owner_id": 100
        }
        mock_ctx.db.groups.get_role.return_value = 0

        _handle_update_name(mock_session, {"group_id": 2, "group_name": "新群名"})

        mock_ctx.db.groups.update_name.assert_called_with(2, "新群名")
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == True

    def test_admin_update_name(self, mock_session, mock_ctx):
        """管理员更新群名"""
        from server.modules.group import _handle_update_name
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "旧名", "owner_id": 200  # 群主是别人
        }
        mock_ctx.db.groups.get_role.return_value = 1  # 当前用户是管理员

        _handle_update_name(mock_session, {"group_id": 2, "group_name": "新群名"})

        mock_ctx.db.groups.update_name.assert_called_with(2, "新群名")

    def test_member_cannot_update_name(self, mock_session, mock_ctx):
        """普通成员不能修改群名"""
        from server.modules.group import _handle_update_name
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "旧名", "owner_id": 200
        }
        mock_ctx.db.groups.get_role.return_value = 0  # 普通成员

        _handle_update_name(mock_session, {"group_id": 2, "group_name": "新群名"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "无权" in resp.get("message", "")

    def test_update_name_nonexistent(self, mock_session, mock_ctx):
        """不存在的群返回错误"""
        from server.modules.group import _handle_update_name
        mock_ctx.db.groups.get_by_id.return_value = None
        _handle_update_name(mock_session, {"group_id": 999, "group_name": "新名"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_update_name_empty(self, mock_session, mock_ctx):
        """空群名返回错误"""
        from server.modules.group import _handle_update_name
        _handle_update_name(mock_session, {"group_id": 2, "group_name": "  "})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 设置备注测试 ==========

class TestHandleSetRemark:
    """设置群个人备注测试"""

    def test_normal_set_remark(self, mock_session, mock_ctx):
        """正常设置备注"""
        from server.modules.group import _handle_set_remark
        mock_ctx.db.groups.is_member.return_value = True
        _handle_set_remark(mock_session, {"group_id": 2, "remark": "我的备注"})

        mock_ctx.db.groups.set_remark.assert_called_with(100, 2, "我的备注")
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == True

    def test_set_remark_not_member(self, mock_session, mock_ctx):
        """非群成员设置备注返回错误"""
        from server.modules.group import _handle_set_remark
        mock_ctx.db.groups.is_member.return_value = False
        _handle_set_remark(mock_session, {"group_id": 2, "remark": "备注"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_set_remark_missing_group_id(self, mock_session):
        """缺少群ID返回错误"""
        from server.modules.group import _handle_set_remark
        _handle_set_remark(mock_session, {"remark": "备注"})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 移除成员测试 ==========

class TestHandleRemoveMember:
    """移除群成员测试"""

    def test_owner_remove_member(self, mock_session, mock_ctx):
        """群主移除普通成员"""
        from server.modules.group import _handle_remove_member
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 100
        }
        mock_ctx.db.groups.get_role.return_value = 0

        _handle_remove_member(mock_session, {"group_id": 2, "target_id": 200})

        mock_ctx.db.groups.remove_member.assert_called_with(2, 200)
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == True

    def test_admin_remove_member(self, mock_session, mock_ctx):
        """管理员移除普通成员"""
        from server.modules.group import _handle_remove_member
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 200
        }
        # 当前用户(100)是管理员，目标(300)是普通成员
        mock_ctx.db.groups.get_role.side_effect = lambda gid, uid: 1 if uid == 100 else 0

        _handle_remove_member(mock_session, {"group_id": 2, "target_id": 300})

        mock_ctx.db.groups.remove_member.assert_called_with(2, 300)

    def test_remove_owner_forbidden(self, mock_session, mock_ctx):
        """不能移除群主"""
        from server.modules.group import _handle_remove_member
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 200
        }
        _handle_remove_member(mock_session, {"group_id": 2, "target_id": 200})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不能移除群主" in resp.get("message", "")

    def test_admin_cannot_remove_admin(self, mock_session, mock_ctx):
        """管理员不能移除其他管理员"""
        from server.modules.group import _handle_remove_member
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 300
        }
        mock_ctx.db.groups.get_role.side_effect = lambda gid, uid: 1 if uid == 100 else 1  # 双方都是管理员

        _handle_remove_member(mock_session, {"group_id": 2, "target_id": 200})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_remove_not_member(self, mock_session, mock_ctx):
        """不存在的群返回错误"""
        from server.modules.group import _handle_remove_member
        mock_ctx.db.groups.get_by_id.return_value = None
        _handle_remove_member(mock_session, {"group_id": 999, "target_id": 200})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_remove_not_authorized(self, mock_session, mock_ctx):
        """普通成员不能移除他人"""
        from server.modules.group import _handle_remove_member
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 300
        }
        mock_ctx.db.groups.get_role.return_value = 0  # 普通成员

        _handle_remove_member(mock_session, {"group_id": 2, "target_id": 200})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_remove_missing_params(self, mock_session):
        """缺少参数返回错误"""
        from server.modules.group import _handle_remove_member
        _handle_remove_member(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ========== 设置管理员测试 ==========

class TestHandleSetAdmin:
    """设置管理员测试"""

    def test_set_admin(self, mock_session, mock_ctx):
        """群主设置他人为管理员"""
        from server.modules.group import _handle_set_admin
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 100
        }
        mock_ctx.db.groups.is_member.return_value = True

        _handle_set_admin(mock_session, {"group_id": 2, "target_id": 200, "role": 1})

        mock_ctx.db.groups.set_role.assert_called_with(2, 200, 1)
        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["ok"] == True

    def test_cancel_admin(self, mock_session, mock_ctx):
        """群主取消管理员"""
        from server.modules.group import _handle_set_admin
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 100
        }
        mock_ctx.db.groups.is_member.return_value = True

        _handle_set_admin(mock_session, {"group_id": 2, "target_id": 200, "role": 0})

        mock_ctx.db.groups.set_role.assert_called_with(2, 200, 0)

    def test_set_admin_not_owner(self, mock_session, mock_ctx):
        """非群主不能设置管理员"""
        from server.modules.group import _handle_set_admin
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 200
        }
        _handle_set_admin(mock_session, {"group_id": 2, "target_id": 300, "role": 1})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_set_admin_on_self(self, mock_session, mock_ctx):
        """群主不能给自己设管理员"""
        from server.modules.group import _handle_set_admin
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 100
        }
        _handle_set_admin(mock_session, {"group_id": 2, "target_id": 100, "role": 1})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_set_admin_not_member(self, mock_session, mock_ctx):
        """目标不是群成员返回错误"""
        from server.modules.group import _handle_set_admin
        mock_ctx.db.groups.get_by_id.return_value = {
            "group_id": 2, "group_name": "测试群", "owner_id": 100
        }
        mock_ctx.db.groups.is_member.return_value = False
        _handle_set_admin(mock_session, {"group_id": 2, "target_id": 999, "role": 1})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_set_admin_nonexistent_group(self, mock_session, mock_ctx):
        """不存在的群返回错误"""
        from server.modules.group import _handle_set_admin
        mock_ctx.db.groups.get_by_id.return_value = None
        _handle_set_admin(mock_session, {"group_id": 999, "target_id": 200, "role": 1})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_set_admin_missing_params(self, mock_session):
        """缺少参数返回错误"""
        from server.modules.group import _handle_set_admin
        _handle_set_admin(mock_session, {})

        mock_session.send.assert_called()
        resp = mock_session.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
