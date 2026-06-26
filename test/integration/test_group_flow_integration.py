"""Group 模块集成测试

测试群聊模块与服务器框架的完整协作：
1. 创建群聊（创建 → 加入创建者 → 邀请成员 → 通知）
2. 加入群聊（查群 → 校验重复 → 加入）
3. 群列表查询（我的群 + 可加入的群）
4. 群成员查询
5. 邀请成员入群（校验权限 → 加入 → 通知）
6. 群信息查询（成员 + 在线状态 + 角色）
7. 群名修改（权限校验 → 更新 → 广播 → 系统消息）
8. 移除成员（权限分层 → 通知）
9. 设置管理员（仅群主）
10. 完整群聊生命周期
"""

import pytest
from unittest.mock import MagicMock, call, patch
from common.messages import MT
from server.modules.group import register as register_group_module
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


def _setup_group_db(ctx, group_id=1, group_name="测试群", owner_id=100):
    """配置群聊相关 DB mock"""
    ctx.db.groups.get_by_id.return_value = {
        "group_id": group_id,
        "group_name": group_name,
        "owner_id": owner_id,
    }
    ctx.db.groups.create.return_value = group_id
    ctx.db.groups.add_member.return_value = 1
    ctx.db.groups.is_member.return_value = True
    ctx.db.groups.list_member_ids.return_value = [100, 200, 300]
    ctx.db.groups.list_members.return_value = [
        {"user_id": 100, "username": "owner", "nickname": "群主", "role": 0, "remark": ""},
        {"user_id": 200, "username": "friend_user", "nickname": "好友", "role": 0, "remark": ""},
    ]
    ctx.db.groups.list_by_user.return_value = [
        {"group_id": group_id, "group_name": group_name, "owner_id": owner_id,
         "remark": "", "joined_at": "2024-01-01 10:00:00"},
    ]
    ctx.db.groups.list_available.return_value = []
    ctx.db.groups.get_role.return_value = 0
    # 用 MagicMock 包装 broadcast/broadcast_to，以便断言调用
    if not isinstance(ctx.online.broadcast, MagicMock):
        ctx.online.broadcast = MagicMock(wraps=ctx.online.broadcast)
    if not isinstance(ctx.online.broadcast_to, MagicMock):
        ctx.online.broadcast_to = MagicMock(wraps=ctx.online.broadcast_to)


# ════════════════════════════════════════════════════════════════
# 模块注册测试
# ════════════════════════════════════════════════════════════════

class TestGroupModuleRegistration:
    """群聊模块注册集成测试"""

    def test_registers_all_types(self, router, ctx):
        """注册所有群聊消息类型"""
        register_group_module(router, ctx)

        registered = set(router._handlers.keys())
        expected = {
            MT.GROUP_CREATE, MT.GROUP_JOIN, MT.GROUP_LIST,
            MT.GROUP_MEMBERS, MT.GROUP_INVITE, MT.GROUP_INFO,
            MT.GROUP_UPDATE_NAME, MT.GROUP_SET_REMARK,
            MT.GROUP_REMOVE_MEMBER, MT.GROUP_SET_ADMIN,
        }
        missing = expected - registered
        assert not missing, f"缺少注册: {missing}"


# ════════════════════════════════════════════════════════════════
# 创建群聊集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupCreateIntegration:
    """创建群聊完整流程集成测试"""

    def test_full_create_flow(self, ctx, session):
        """完整创建流程：创建 → 加入创建者 → 响应"""
        ctx.db.groups.create.return_value = 100

        from server.modules.group import _handle_create
        _handle_create(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "学习小组",
        })

        # 1. 创建群聊记录
        ctx.db.groups.create.assert_called_with("学习小组", 100)

        # 2. 创建者自动加入
        ctx.db.groups.add_member.assert_any_call(100, 100)

        # 3. 返回成功响应
        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_CREATE_RESP
        assert resp["ok"] is True
        assert resp["group_id"] == 100
        assert resp["group_name"] == "学习小组"

    def test_create_with_invitees(self, ctx, session):
        """创建群聊时邀请成员"""
        ctx.db.groups.create.return_value = 100
        ctx.db.groups.add_member.return_value = 1
        # 包装 broadcast_to 以便断言
        ctx.online.broadcast_to = MagicMock(wraps=ctx.online.broadcast_to)

        from server.modules.group import _handle_create
        _handle_create(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "项目组",
            "invitees": [200, 300, 400],
        })

        # 验证所有受邀者都被加入
        add_member_calls = ctx.db.groups.add_member.call_args_list
        added_uids = [c[0][1] for c in add_member_calls]
        assert 100 in added_uids  # 创建者
        assert 200 in added_uids
        assert 300 in added_uids
        assert 400 in added_uids

        # 通知了被邀请的成员（broadcast_to 被调用）
        ctx.online.broadcast_to.assert_called()
        broadcast_msg = ctx.online.broadcast_to.call_args[0][0]
        assert broadcast_msg["type"] == MT.GROUP_INVITE
        assert broadcast_msg["group_name"] == "项目组"

    def test_create_empty_name(self, session):
        """群名为空"""
        from server.modules.group import _handle_create
        _handle_create(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不能为空" in resp.get("message", "")

    def test_create_whitespace_name(self, session):
        """群名为空格"""
        from server.modules.group import _handle_create
        _handle_create(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "   ",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_create_skips_owner_in_invitees(self, ctx, session):
        """受邀者中包含创建者自己时跳过"""
        ctx.db.groups.create.return_value = 100
        ctx.db.groups.add_member.return_value = 1

        from server.modules.group import _handle_create
        _handle_create(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "群",
            "invitees": [100, 200],  # 100 是创建者自己
        })

        # 创建者只被 add_member 一次
        add_100_calls = [c for c in ctx.db.groups.add_member.call_args_list
                         if c[0][1] == 100]
        assert len(add_100_calls) == 1


# ════════════════════════════════════════════════════════════════
# 加入群聊集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupJoinIntegration:
    """加入群聊完整流程集成测试"""

    def test_full_join_flow(self, ctx, session):
        """完整加入流程：查群 → 校验成员 → 加入 → 响应"""
        _setup_group_db(ctx)
        ctx.db.groups.is_member.return_value = False  # 尚未加入

        from server.modules.group import _handle_join
        _handle_join(session, {"type": MT.GROUP_JOIN, "group_id": 1})

        ctx.db.groups.add_member.assert_called_with(1, 100)

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_JOIN_RESP
        assert resp["ok"] is True
        assert resp["group_id"] == 1
        assert resp["group_name"] == "测试群"

    def test_join_missing_group_id(self, session):
        """缺少群聊ID"""
        from server.modules.group import _handle_join
        _handle_join(session, {"type": MT.GROUP_JOIN})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_join_nonexistent_group(self, ctx, session):
        """群聊不存在"""
        ctx.db.groups.get_by_id.return_value = None

        from server.modules.group import _handle_join
        _handle_join(session, {"type": MT.GROUP_JOIN, "group_id": 999})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不存在" in resp.get("message", "")

    def test_join_already_member(self, ctx, session):
        """已在群中"""
        _setup_group_db(ctx)
        ctx.db.groups.is_member.return_value = True

        from server.modules.group import _handle_join
        _handle_join(session, {"type": MT.GROUP_JOIN, "group_id": 1})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "已在群中" in resp.get("message", "")


# ════════════════════════════════════════════════════════════════
# 群列表查询集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupListIntegration:
    """群聊列表查询集成测试"""

    def test_list_my_and_available(self, ctx, session):
        """返回我的群和可加入的群"""
        ctx.db.groups.list_by_user.return_value = [
            {"group_id": 1, "group_name": "我的群", "owner_id": 100,
             "remark": "", "joined_at": "2024-01-01"},
        ]
        ctx.db.groups.list_available.return_value = [
            {"group_id": 2, "group_name": "可加入群"},
        ]

        from server.modules.group import _handle_list
        _handle_list(session, {"type": MT.GROUP_LIST})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_LIST_RESP
        assert len(resp["my_groups"]) == 1
        assert resp["my_groups"][0]["group_name"] == "我的群"
        assert len(resp["available"]) == 1
        assert resp["available"][0]["group_name"] == "可加入群"

    def test_empty_lists(self, ctx, session):
        """空列表"""
        ctx.db.groups.list_by_user.return_value = []
        ctx.db.groups.list_available.return_value = []

        from server.modules.group import _handle_list
        _handle_list(session, {"type": MT.GROUP_LIST})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_LIST_RESP
        assert len(resp["my_groups"]) == 0
        assert len(resp["available"]) == 0


# ════════════════════════════════════════════════════════════════
# 群成员查询集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupMembersIntegration:
    """群成员查询集成测试"""

    def test_members_list(self, ctx, session):
        """查询群成员列表"""
        _setup_group_db(ctx)

        from server.modules.group import _handle_members
        _handle_members(session, {"type": MT.GROUP_MEMBERS, "group_id": 1})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_MEMBERS_RESP
        assert resp["group_id"] == 1
        assert len(resp["members"]) == 2

    def test_members_missing_group_id(self, session):
        """缺少群聊ID"""
        from server.modules.group import _handle_members
        _handle_members(session, {"type": MT.GROUP_MEMBERS})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ════════════════════════════════════════════════════════════════
# 邀请成员集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupInviteIntegration:
    """邀请成员入群集成测试"""

    def test_invite_members(self, ctx, session):
        """邀请新成员：跳过已在群成员，添加新成员，通知"""
        _setup_group_db(ctx)
        # 用户100（session）和用户200 已在群中，300 不在群中
        ctx.db.groups.is_member.side_effect = lambda gid, uid: uid in (100, 200)

        from server.modules.group import _handle_invite
        _handle_invite(session, {
            "type": MT.GROUP_INVITE,
            "group_id": 1,
            "invitees": [200, 300],  # 200 已在群，300 新加入
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is True
        assert resp["added"] == [300]
        assert resp["skipped"] == [200]

    def test_invite_non_member_cannot_invite(self, ctx, session):
        """非群成员不能邀请"""
        _setup_group_db(ctx)
        ctx.db.groups.is_member.return_value = False

        from server.modules.group import _handle_invite
        _handle_invite(session, {
            "type": MT.GROUP_INVITE,
            "group_id": 1,
            "invitees": [300],
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不是该群成员" in resp.get("message", "")

    def test_invite_missing_params(self, session):
        """缺少参数"""
        from server.modules.group import _handle_invite
        _handle_invite(session, {"type": MT.GROUP_INVITE})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR


# ════════════════════════════════════════════════════════════════
# 群信息查询集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupInfoIntegration:
    """群信息查询集成测试"""

    def test_info_with_online_status(self, ctx, session):
        """群信息包含成员在线状态和角色"""
        _setup_group_db(ctx)
        # 将用户 200 加入在线表（使用真实 OnlineRegistry）
        online_handler = _make_online_handler()
        ctx.online.add(200, online_handler)

        from server.modules.group import _handle_info_req
        _handle_info_req(session, {"type": MT.GROUP_INFO, "group_id": 1})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_INFO_RESP
        assert resp["group_name"] == "测试群"
        assert resp["owner_id"] == 100
        assert len(resp["members"]) == 2

        # 在线状态标注
        owner = next(m for m in resp["members"] if m["user_id"] == 100)
        friend = next(m for m in resp["members"] if m["user_id"] == 200)
        assert owner["online"] is False
        assert friend["online"] is True

    def test_info_not_member(self, ctx, session):
        """非成员查询被拒绝"""
        _setup_group_db(ctx)
        ctx.db.groups.is_member.return_value = False

        from server.modules.group import _handle_info_req
        _handle_info_req(session, {"type": MT.GROUP_INFO, "group_id": 1})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不是该群成员" in resp.get("message", "")


# ════════════════════════════════════════════════════════════════
# 群名修改集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupUpdateNameIntegration:
    """群名修改集成测试"""

    def test_owner_can_update_name(self, ctx, session):
        """群主可以修改群名"""
        _setup_group_db(ctx, owner_id=100)
        ctx.db.groups.update_name.return_value = 1

        from server.modules.group import _handle_update_name
        _handle_update_name(session, {
            "type": MT.GROUP_UPDATE_NAME,
            "group_id": 1,
            "group_name": "新群名",
        })

        ctx.db.groups.update_name.assert_called_with(1, "新群名")

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_UPDATE_NAME
        assert resp["ok"] is True
        assert resp["group_name"] == "新群名"

        # 广播给所有群成员
        ctx.online.broadcast_to.assert_called()

        # 插入系统消息
        ctx.db.messages.insert.assert_called()

    def test_admin_can_update_name(self, ctx, session):
        """管理员也可以修改群名"""
        _setup_group_db(ctx, owner_id=200)  # 群主是200
        ctx.db.groups.get_role.return_value = 1  # 当前用户100是管理员

        from server.modules.group import _handle_update_name
        _handle_update_name(session, {
            "type": MT.GROUP_UPDATE_NAME,
            "group_id": 1,
            "group_name": "管理员改的群名",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is True

    def test_normal_member_cannot_update_name(self, ctx, session):
        """普通成员不能修改群名"""
        _setup_group_db(ctx, owner_id=200)
        ctx.db.groups.get_role.return_value = 0

        from server.modules.group import _handle_update_name
        _handle_update_name(session, {
            "type": MT.GROUP_UPDATE_NAME,
            "group_id": 1,
            "group_name": "想改名",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "无权" in resp.get("message", "")


# ════════════════════════════════════════════════════════════════
# 移除成员集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupRemoveMemberIntegration:
    """移除成员集成测试"""

    def test_owner_can_remove_member(self, ctx, session):
        """群主可以移除普通成员"""
        _setup_group_db(ctx, owner_id=100)
        ctx.db.groups.get_role.side_effect = lambda gid, uid: 0 if uid == 200 else 0

        from server.modules.group import _handle_remove_member
        _handle_remove_member(session, {
            "type": MT.GROUP_REMOVE_MEMBER,
            "group_id": 1,
            "target_id": 200,
        })

        ctx.db.groups.remove_member.assert_called_with(1, 200)

        resp = session._handler.send.call_args[0][0]
        assert resp["ok"] is True

    def test_cannot_remove_owner(self, ctx, session):
        """不能移除群主"""
        _setup_group_db(ctx, owner_id=200)

        from server.modules.group import _handle_remove_member
        _handle_remove_member(session, {
            "type": MT.GROUP_REMOVE_MEMBER,
            "group_id": 1,
            "target_id": 200,
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "群主" in resp.get("message", "")

    def test_self_leave(self, ctx, session):
        """自己退出群聊"""
        _setup_group_db(ctx, owner_id=200)
        ctx.db.groups.list_member_ids.return_value = [200]

        from server.modules.group import _handle_remove_member
        _handle_remove_member(session, {
            "type": MT.GROUP_REMOVE_MEMBER,
            "group_id": 1,
            "target_id": 100,  # 自己退出
        })

        ctx.db.groups.remove_member.assert_called_with(1, 100)

        resp = session._handler.send.call_args_list[0][0][0]
        assert resp["ok"] is True

    def test_admin_cannot_remove_admin(self, ctx, session):
        """管理员不能移除其他管理员"""
        _setup_group_db(ctx, owner_id=300)  # 群主是300
        ctx.db.groups.get_role.side_effect = lambda gid, uid: 1 if uid in (100, 200) else 0

        from server.modules.group import _handle_remove_member
        _handle_remove_member(session, {
            "type": MT.GROUP_REMOVE_MEMBER,
            "group_id": 1,
            "target_id": 200,  # 200 也是管理员
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "无权" in resp.get("message", "") or "管理员" in resp.get("message", "")


# ════════════════════════════════════════════════════════════════
# 设置管理员集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupSetAdminIntegration:
    """设置管理员集成测试"""

    def test_owner_sets_admin(self, ctx, session):
        """群主设置管理员"""
        _setup_group_db(ctx, owner_id=100)
        ctx.db.groups.is_member.return_value = True

        from server.modules.group import _handle_set_admin
        _handle_set_admin(session, {
            "type": MT.GROUP_SET_ADMIN,
            "group_id": 1,
            "target_id": 200,
            "role": 1,
        })

        ctx.db.groups.set_role.assert_called_with(1, 200, 1)

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_SET_ADMIN
        assert resp["ok"] is True
        assert resp["role"] == 1

    def test_non_owner_cannot_set_admin(self, ctx, session):
        """非群主不能设置管理员"""
        _setup_group_db(ctx, owner_id=200)

        from server.modules.group import _handle_set_admin
        _handle_set_admin(session, {
            "type": MT.GROUP_SET_ADMIN,
            "group_id": 1,
            "target_id": 300,
            "role": 1,
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "仅群主" in resp.get("message", "")

    def test_cannot_set_owner_role(self, ctx, session):
        """不能修改群主自己的角色"""
        _setup_group_db(ctx, owner_id=100)

        from server.modules.group import _handle_set_admin
        _handle_set_admin(session, {
            "type": MT.GROUP_SET_ADMIN,
            "group_id": 1,
            "target_id": 100,  # 群主自己
            "role": 1,
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_target_not_member(self, ctx, session):
        """目标用户不是群成员"""
        _setup_group_db(ctx, owner_id=100)
        ctx.db.groups.is_member.return_value = False

        from server.modules.group import _handle_set_admin
        _handle_set_admin(session, {
            "type": MT.GROUP_SET_ADMIN,
            "group_id": 1,
            "target_id": 999,
            "role": 1,
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "不是群成员" in resp.get("message", "")


# ════════════════════════════════════════════════════════════════
# 完整群聊生命周期测试
# ════════════════════════════════════════════════════════════════

class TestGroupFullLifecycle:
    """群聊完整生命周期：创建 → 加入 → 邀请 → 查成员 → 改名 → 移除"""

    def test_full_lifecycle(self, ctx, session):
        """模拟群聊完整生命周期"""
        from server.modules.group import (
            _handle_create, _handle_join, _handle_invite,
            _handle_members, _handle_update_name, _handle_remove_member,
        )

        # === Phase 1: 创建群聊 ===
        ctx.db.groups.create.return_value = 100
        ctx.db.groups.add_member.return_value = 1

        _handle_create(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "项目协作组",
        })

        create_resp = session._handler.send.call_args_list[-1][0][0]
        assert create_resp["type"] == MT.GROUP_CREATE_RESP
        assert create_resp["ok"] is True
        group_id = create_resp["group_id"]

        # === Phase 2: 其他用户加入 ===
        second_handler = MagicMock()
        second_handler.send = MagicMock()
        second_handler.conn = MagicMock()
        second_s = Session(ctx, second_handler)
        second_s.bind_user(200, "friend_user")

        ctx.db.groups.get_by_id.return_value = {
            "group_id": group_id, "group_name": "项目协作组", "owner_id": 100,
        }
        ctx.db.groups.is_member.return_value = False
        ctx.db.groups.add_member.reset_mock()

        _handle_join(second_s, {"type": MT.GROUP_JOIN, "group_id": group_id})

        join_resp = second_s._handler.send.call_args_list[-1][0][0]
        assert join_resp["type"] == MT.GROUP_JOIN_RESP
        assert join_resp["ok"] is True

        # === Phase 3: 邀请更多成员 ===
        ctx.db.groups.is_member.side_effect = lambda gid, uid: uid in (100, 200)
        ctx.db.groups.add_member.reset_mock()

        _handle_invite(session, {
            "type": MT.GROUP_INVITE,
            "group_id": group_id,
            "invitees": [300, 400],
        })

        invite_resp = session._handler.send.call_args_list[-1][0][0]
        assert invite_resp["ok"] is True
        assert 300 in invite_resp["added"]
        assert 400 in invite_resp["added"]

        # === Phase 4: 查询群成员 ===
        ctx.db.groups.list_members.return_value = [
            {"user_id": 100, "username": "owner", "nickname": "群主", "role": 0, "remark": ""},
            {"user_id": 200, "username": "friend_user", "nickname": "好友", "role": 0, "remark": ""},
            {"user_id": 300, "username": "user3", "nickname": "用户3", "role": 0, "remark": ""},
            {"user_id": 400, "username": "user4", "nickname": "用户4", "role": 0, "remark": ""},
        ]

        _handle_members(session, {"type": MT.GROUP_MEMBERS, "group_id": group_id})

        members_resp = session._handler.send.call_args_list[-1][0][0]
        assert len(members_resp["members"]) == 4

        # === Phase 5: 改名 ===
        ctx.db.groups.get_by_id.return_value = {
            "group_id": group_id, "group_name": "项目协作组", "owner_id": 100,
        }
        ctx.db.groups.list_member_ids.return_value = [100, 200, 300, 400]

        _handle_update_name(session, {
            "type": MT.GROUP_UPDATE_NAME,
            "group_id": group_id,
            "group_name": "重构项目协作组",
        })

        name_resp = session._handler.send.call_args_list[-1][0][0]
        assert name_resp["ok"] is True
        assert name_resp["group_name"] == "重构项目协作组"

        # === Phase 6: 移除成员 ===
        ctx.db.groups.get_role.side_effect = lambda gid, uid: 0

        _handle_remove_member(session, {
            "type": MT.GROUP_REMOVE_MEMBER,
            "group_id": group_id,
            "target_id": 400,
        })

        remove_resp = session._handler.send.call_args_list[-1][0][0]
        assert remove_resp["ok"] is True


# ════════════════════════════════════════════════════════════════
# Router 分发集成测试
# ════════════════════════════════════════════════════════════════

class TestGroupRouterIntegration:
    """通过 Router 分发群聊消息的集成测试"""

    def test_create_via_router(self, router, ctx, session):
        """通过 Router dispatch GROUP_CREATE 消息"""
        register_group_module(router, ctx)
        ctx.db.groups.create.return_value = 100
        ctx.db.groups.add_member.return_value = 1

        router.dispatch(session, {
            "type": MT.GROUP_CREATE,
            "group_name": "路由测试群",
        })

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_CREATE_RESP
        assert resp["ok"] is True

    def test_list_via_router(self, router, ctx, session):
        """通过 Router dispatch GROUP_LIST 消息"""
        register_group_module(router, ctx)
        ctx.db.groups.list_by_user.return_value = []
        ctx.db.groups.list_available.return_value = []

        router.dispatch(session, {"type": MT.GROUP_LIST})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_LIST_RESP

    def test_join_via_router(self, router, ctx, session):
        """通过 Router dispatch GROUP_JOIN 消息"""
        register_group_module(router, ctx)
        _setup_group_db(ctx)
        ctx.db.groups.is_member.return_value = False

        router.dispatch(session, {"type": MT.GROUP_JOIN, "group_id": 1})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.GROUP_JOIN_RESP
        assert resp["ok"] is True
