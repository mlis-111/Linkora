"""群聊管理模块（服务器端）

处理群聊的创建、加入、查询、邀请等功能。

author: 董钧豪
"""

import time
from common.messages import MT, error


def register(router, ctx):
    """注册群聊管理模块的消息处理函数

    Args:
        router: MessageRouter 实例
        ctx: ServerContext 实例
    """
    router.register(MT.GROUP_CREATE, _handle_create)
    router.register(MT.GROUP_JOIN, _handle_join)
    router.register(MT.GROUP_LIST, _handle_list)
    router.register(MT.GROUP_MEMBERS, _handle_members)
    router.register(MT.GROUP_INVITE, _handle_invite)
    router.register(MT.GROUP_INFO, _handle_info_req)
    router.register(MT.GROUP_UPDATE_NAME, _handle_update_name)
    router.register(MT.GROUP_SET_REMARK, _handle_set_remark)
    router.register(MT.GROUP_REMOVE_MEMBER, _handle_remove_member)
    router.register(MT.GROUP_SET_ADMIN, _handle_set_admin)


def _handle_create(session, msg):
    """处理创建群聊

    流程：
        1. 生成唯一的群聊ID
        2. 创建群聊记录
        3. 将创建者加入群聊
        4. 如果有被邀请成员，一并加入

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_name, invitees（可选）
    """
    ctx = session.ctx
    owner_id = session.user_id
    group_name = msg.get("group_name", "").strip()
    invitees = msg.get("invitees", [])  # [user_id, ...]

    if not group_name:
        session.send(error("INVALID_PARAM", "群聊名称不能为空"))
        return

    group_id = ctx.db.groups.create(group_name, owner_id)
    ctx.db.groups.add_member(group_id, owner_id)

    # 邀请成员
    added = []
    for uid in invitees:
        if uid == owner_id:
            continue
        affected = ctx.db.groups.add_member(group_id, uid)
        if affected > 0:
            added.append(uid)

    session.send({
        "type": MT.GROUP_CREATE_RESP,
        "ok": True,
        "group_id": group_id,
        "group_name": group_name,
        "added": added,
    })

    # 通知被邀请的成员（带上 group_name，确保受邀者界面正确显示群名）
    if added:
        ctx.online.broadcast_to({
            "type": MT.GROUP_INVITE,
            "group_id": group_id,
            "group_name": group_name,
            "invited_by": owner_id,
        }, added)


def _handle_join(session, msg):
    """处理加入群聊

    不能重复加入，已在群中则返回错误。

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    user_id = session.user_id

    if not group_id:
        session.send(error("INVALID_PARAM", "缺少群聊ID"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    if ctx.db.groups.is_member(group_id, user_id):
        session.send(error("ALREADY_MEMBER", "你已在群中"))
        return

    ctx.db.groups.add_member(group_id, user_id)

    session.send({
        "type": MT.GROUP_JOIN_RESP,
        "ok": True,
        "group_id": group_id,
        "group_name": group.get("group_name", ""),
    })


def _handle_list(session, msg):
    """处理群聊列表查询

    返回用户已加入的群聊列表和可加入的群聊列表。

    Args:
        session: Session 实例
        msg: 消息字典（无特殊字段）
    """
    ctx = session.ctx
    user_id = session.user_id

    my_groups = ctx.db.groups.list_by_user(user_id)
    available = ctx.db.groups.list_available(user_id)

    session.send({
        "type": MT.GROUP_LIST_RESP,
        "my_groups": my_groups,
        "available": available,
    })


def _handle_members(session, msg):
    """处理群成员列表查询

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)

    if not group_id:
        session.send(error("INVALID_PARAM", "缺少群聊ID"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    members = ctx.db.groups.list_members(group_id)
    session.send({
        "type": MT.GROUP_MEMBERS_RESP,
        "group_id": group_id,
        "group_name": group.get("group_name", ""),
        "members": members,
    })


def _handle_invite(session, msg):
    """处理邀请好友入群

    只能由群成员邀请，不能邀请已在群中的用户。

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id, invitees（[user_id, ...]）
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    invitees = msg.get("invitees", [])
    user_id = session.user_id

    if not group_id or not invitees:
        session.send(error("INVALID_PARAM", "缺少群聊ID或邀请列表"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    if not ctx.db.groups.is_member(group_id, user_id):
        session.send(error("NOT_MEMBER", "你不是该群成员，无法邀请"))
        return

    added = []
    skipped = []
    for uid in invitees:
        if ctx.db.groups.is_member(group_id, uid):
            skipped.append(uid)
            continue
        affected = ctx.db.groups.add_member(group_id, uid)
        if affected > 0:
            added.append(uid)
        else:
            skipped.append(uid)

    session.send({
        "type": MT.GROUP_INVITE,
        "ok": True,
        "group_id": group_id,
        "added": added,
        "skipped": skipped,
    })

    # 通知被邀请的新成员（带上 group_name）
    if added:
        ctx.online.broadcast_to({
            "type": MT.GROUP_INVITE,
            "group_id": group_id,
            "group_name": group.get("group_name", ""),
            "invited_by": user_id,
        }, added)


def _handle_info_req(session, msg):
    """查询群设置信息

    返回群信息、成员列表（含角色和在线状态）、当前用户的角色。

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    user_id = session.user_id

    if not group_id:
        session.send(error("INVALID_PARAM", "缺少群聊ID"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    if not ctx.db.groups.is_member(group_id, user_id):
        session.send(error("NOT_MEMBER", "你不是该群成员"))
        return

    # 获取成员列表并标注在线状态
    members = ctx.db.groups.list_members(group_id)
    member_list = []
    my_remark = ""
    for m in members:
        is_current = m["user_id"] == user_id
        if is_current:
            my_remark = m.get("remark", "") or ""
        member_list.append({
            "user_id": m["user_id"],
            "username": m["username"],
            "nickname": m.get("nickname", ""),
            "role": m.get("role", 0),
            "online": ctx.online.is_online(m["user_id"]),
        })

    # 当前用户的角色
    my_role = ctx.db.groups.get_role(group_id, user_id)

    session.send({
        "type": MT.GROUP_INFO_RESP,
        "group_id": group_id,
        "group_name": group.get("group_name", ""),
        "owner_id": group.get("owner_id"),
        "my_role": my_role,
        "my_remark": my_remark,
        "members": member_list,
    })


def _handle_update_name(session, msg):
    """更新群聊名称（群主或管理员可操作）

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id, group_name
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    new_name = msg.get("group_name", "").strip()
    user_id = session.user_id

    if not group_id or not new_name:
        session.send(error("INVALID_PARAM", "参数不完整"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    # 校验权限：群主或管理员
    is_owner = group.get("owner_id") == user_id
    is_admin = ctx.db.groups.get_role(group_id, user_id) == 1
    if not is_owner and not is_admin:
        session.send(error("FORBIDDEN", "无权修改群名"))
        return

    old_name = group.get("group_name", "")
    ctx.db.groups.update_name(group_id, new_name)

    session.send({
        "type": MT.GROUP_UPDATE_NAME,
        "ok": True,
        "group_id": group_id,
        "group_name": new_name,
    })

    # 广播群名变更给所有在线群成员
    member_ids = ctx.db.groups.list_member_ids(group_id)
    ctx.online.broadcast_to({
        "type": MT.GROUP_NAME_UPDATED,
        "group_id": group_id,
        "group_name": new_name,
        "updated_by": user_id,
    }, member_ids)

    # 在群聊中插入一条系统消息
    sys_content = f"{session.username} 已将群名改为 {new_name}"
    ctx.db.messages.insert(2, 0, None, group_id, sys_content)
    encrypted_sys = ctx.crypto.encrypt(sys_content)
    ctx.online.broadcast_to({
        "type": MT.ROOM_CHAT,
        "room_id": group_id,
        "from": 0,
        "content": encrypted_sys,
        "ts": int(time.time()),
    }, member_ids)


def _handle_set_remark(session, msg):
    """设置用户对群聊的个人备注

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id, remark
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    remark = msg.get("remark", "").strip()
    user_id = session.user_id

    if not group_id:
        session.send(error("INVALID_PARAM", "缺少群聊ID"))
        return

    # 校验自己是否为群成员
    if not ctx.db.groups.is_member(group_id, user_id):
        session.send(error("NOT_MEMBER", "你不是该群成员"))
        return

    ctx.db.groups.set_remark(user_id, group_id, remark)

    session.send({
        "type": MT.GROUP_SET_REMARK,
        "ok": True,
    })


def _handle_remove_member(session, msg):
    """移除群成员（群主或管理员可操作）

    管理员不能移除其他管理员和群主，仅群主可移除管理员。

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id, target_id
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    target_id = msg.get("target_id")
    user_id = session.user_id

    if not group_id or not target_id:
        session.send(error("INVALID_PARAM", "参数不完整"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    # 不能移除群主
    if target_id == group.get("owner_id"):
        session.send(error("FORBIDDEN", "不能移除群主"))
        return

    # 校验权限
    is_owner = group.get("owner_id") == user_id
    is_admin = ctx.db.groups.get_role(group_id, user_id) == 1
    if not is_owner and not is_admin:
        session.send(error("FORBIDDEN", "无权移除成员"))
        return

    # 管理员不能移除其他管理员
    target_role = ctx.db.groups.get_role(group_id, target_id)
    if not is_owner and target_role == 1:
        session.send(error("FORBIDDEN", "无权移除管理员"))
        return

    ctx.db.groups.remove_member(group_id, target_id)

    session.send({
        "type": MT.GROUP_REMOVE_MEMBER,
        "ok": True,
        "group_id": group_id,
        "target_id": target_id,
    })

    # 通知被移除者（如果在线）
    ctx.online.send(target_id, {
        "type": MT.GROUP_REMOVE_MEMBER,
        "group_id": group_id,
        "removed_by": user_id,
    })


def _handle_set_admin(session, msg):
    """设置/取消管理员（仅群主可操作）

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id, target_id, role（1=设为管理员, 0=取消管理员）
    """
    ctx = session.ctx
    group_id = msg.get("group_id", 0)
    target_id = msg.get("target_id")
    new_role = msg.get("role", 0)
    user_id = session.user_id

    if not group_id or not target_id:
        session.send(error("INVALID_PARAM", "参数不完整"))
        return

    group = ctx.db.groups.get_by_id(group_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    # 仅群主可操作
    if group.get("owner_id") != user_id:
        session.send(error("FORBIDDEN", "仅群主可设置管理员"))
        return

    # 不能操作群主自己
    if target_id == user_id:
        session.send(error("INVALID_PARAM", "不能修改群主角色"))
        return

    # 目标必须是群成员
    if not ctx.db.groups.is_member(group_id, target_id):
        session.send(error("NOT_MEMBER", "该用户不是群成员"))
        return

    ctx.db.groups.set_role(group_id, target_id, new_role)

    session.send({
        "type": MT.GROUP_SET_ADMIN,
        "ok": True,
        "group_id": group_id,
        "target_id": target_id,
        "role": new_role,
    })
