"""群聊管理模块（服务器端）

处理群聊的创建、加入、查询、邀请等功能。

author: 董钧豪
"""

import uuid
from common.messages import MT, error


def _generate_group_id():
    """生成唯一群聊ID，格式：g_xxxxxx（8位十六进制）"""
    return "g_" + uuid.uuid4().hex[:8]


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

    group_id = _generate_group_id()
    ctx.db.groups.create(group_id, group_name, owner_id)
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


def _handle_join(session, msg):
    """处理加入群聊

    不能重复加入，已在群中则返回错误。

    Args:
        session: Session 实例
        msg: 消息字典，包含 group_id
    """
    ctx = session.ctx
    group_id = msg.get("group_id", "")
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
    group_id = msg.get("group_id", "")

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
    group_id = msg.get("group_id", "")
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
