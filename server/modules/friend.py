"""好友模块（服务器端）

处理好友添加（需对方同意）、备注设置和好友列表查询。

author: 董钧豪
"""

from common.messages import MT, error


def register(router, ctx):
    """注册好友模块的消息处理函数"""
    router.register(MT.FRIEND_ADD, handle_friend_add)
    router.register(MT.FRIEND_REMARK, handle_friend_remark)
    router.register(MT.FRIEND_LIST, handle_friend_list)
    router.register(MT.USER_SEARCH, handle_user_search)
    router.register(MT.FRIEND_AGREE, handle_friend_agree)
    router.register(MT.FRIEND_REJECT, handle_friend_reject)
    router.register(MT.FRIEND_REQ_LIST, handle_friend_req_list)
    router.register(MT.FRIEND_REMOVE, handle_friend_remove)


def handle_friend_add(session, msg):
    """处理添加好友请求

    按用户 ID 查找目标用户，创建好友申请（待对方同意）。

    Args:
        session: Session 实例
        msg: 消息字典，包含 target_id 字段
    """
    ctx = session.ctx
    target_id = msg.get("target_id")

    if not target_id:
        session.send({"type": MT.FRIEND_ADD_RESP, "ok": False, "reason": "用户ID不能为空"})
        return

    try:
        target_id = int(target_id)
    except (ValueError, TypeError):
        session.send({"type": MT.FRIEND_ADD_RESP, "ok": False, "reason": "用户ID格式错误"})
        return

    if target_id == session.user_id:
        session.send({"type": MT.FRIEND_ADD_RESP, "ok": False, "reason": "不能添加自己为好友"})
        return

    # 检查目标用户是否存在
    target_user = ctx.db.users.get_by_id(target_id)
    if not target_user:
        session.send({"type": MT.FRIEND_ADD_RESP, "ok": False, "reason": f"用户 {target_id} 不存在"})
        return

    # 检查是否已经是好友
    existing = ctx.db.friends.list_by_user(session.user_id)
    if any(f["user_id"] == target_id for f in existing):
        session.send({"type": MT.FRIEND_ADD_RESP, "ok": False, "reason": "该用户已是你的好友"})
        return

    # 检查是否有待处理的申请（双向）
    pending = ctx.db.friend_requests.find_reverse_pending(session.user_id, target_id)
    if pending:
        session.send({"type": MT.FRIEND_ADD_RESP, "ok": False, "reason": "已发送过好友申请，请等待对方处理"})
        return

    # 创建好友申请
    req_msg = msg.get("message", "") or ""
    ctx.db.friend_requests.create(session.user_id, target_id, req_msg)

    session.send({
        "type": MT.FRIEND_ADD_RESP,
        "ok": True,
        "message": "好友申请已发送，等待对方同意",
    })

    # 通知接收方（如果在线）
    if ctx.online.is_online(target_id):
        ctx.online.send(target_id, {
            "type": MT.FRIEND_REQ_NOTIFY,
            "from_id": session.user_id,
            "from_name": session.username,
            "message": req_msg,
        })


def handle_user_search(session, msg):
    """按用户ID搜索用户

    Args:
        session: Session 实例
        msg: 消息字典，包含 target_id 字段
    """
    ctx = session.ctx
    target_id = msg.get("target_id")

    if not target_id:
        session.send({"type": MT.USER_SEARCH_RESP, "ok": False, "reason": "用户ID不能为空"})
        return

    try:
        target_id = int(target_id)
    except (ValueError, TypeError):
        session.send({"type": MT.USER_SEARCH_RESP, "ok": False, "reason": "用户ID格式错误"})
        return

    # 查找用户
    user = ctx.db.users.get_by_id(target_id)
    if not user:
        session.send({"type": MT.USER_SEARCH_RESP, "ok": False, "reason": f"用户 {target_id} 不存在"})
        return

    # 不能搜索自己
    if target_id == session.user_id:
        session.send({"type": MT.USER_SEARCH_RESP, "ok": False, "reason": "不能添加自己为好友"})
        return

    # 检查是否已经是好友
    friends = ctx.db.friends.list_by_user(session.user_id)
    is_friend = any(f["user_id"] == target_id for f in friends)

    session.send({
        "type": MT.USER_SEARCH_RESP,
        "ok": True,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "nickname": user.get("nickname", "") or user["username"],
            "is_friend": is_friend,
        },
    })


def handle_friend_agree(session, msg):
    """处理同意好友申请

    双向建立好友关系，通知申请方。

    Args:
        session: Session 实例
        msg: 消息字典，包含 from_id 字段
    """
    ctx = session.ctx
    from_id = msg.get("from_id")

    if not from_id:
        session.send({"type": MT.FRIEND_AGREE_RESP, "ok": False, "reason": "缺少申请人ID"})
        return

    # 查找待处理的申请
    req = ctx.db.friend_requests.find_pending(from_id, session.user_id)
    if not req:
        session.send({"type": MT.FRIEND_AGREE_RESP, "ok": False, "reason": "未找到该好友申请"})
        return

    # 获取申请人用户名
    from_user = ctx.db.users.get_by_id(from_id)
    from_name = from_user.get("nickname") or from_user.get("username", f"用户{from_id}") if from_user else f"用户{from_id}"

    # 更新申请状态为已同意
    ctx.db.friend_requests.update_status(req["id"], 1)

    # 双向建立好友关系
    ctx.db.friends.add(session.user_id, from_id)
    ctx.db.friends.add(from_id, session.user_id)

    # 通知接收方（同意者）
    session.send({
        "type": MT.FRIEND_AGREE_RESP,
        "ok": True,
        "friend_id": from_id,
        "friend_name": from_name,
    })

    # 通知申请方（如果在线）
    if ctx.online.is_online(from_id):
        ctx.online.send(from_id, {
            "type": MT.FRIEND_AGREE_RESP,
            "accepted": True,
            "friend_id": session.user_id,
            "friend_name": session.username,
            "request_message": req.get("message", ""),
        })

    # 给双方都刷新好友列表
    if ctx.online.is_online(from_id):
        ctx.online.send(from_id, {
            "type": MT.FRIEND_LIST_RESP,
            "friends": ctx.db.friends.list_by_user(from_id),
        })
    session.send({
        "type": MT.FRIEND_LIST_RESP,
        "friends": ctx.db.friends.list_by_user(session.user_id),
    })


def handle_friend_reject(session, msg):
    """处理拒绝好友申请，记录理由并通知申请方

    Args:
        session: Session 实例
        msg: 消息字典，包含 from_id 和可选 reason 字段
    """
    ctx = session.ctx
    from_id = msg.get("from_id")
    reason = msg.get("reason", "").strip()

    if not from_id:
        return

    req = ctx.db.friend_requests.find_pending(from_id, session.user_id)
    if req:
        ctx.db.friend_requests.reject(req["id"], reason)

    session.send({"type": MT.FRIEND_REJECT, "ok": True})

    # 通知申请方被拒绝（如果在线）
    if from_id and ctx.online.is_online(from_id):
        ctx.online.send(from_id, {
            "type": MT.FRIEND_REJECTED,
            "from_id": session.user_id,
            "from_name": session.username,
            "reason": reason or "未说明理由",
        })


def handle_friend_req_list(session, msg):
    """查询待处理的好友申请

    Args:
        session: Session 实例
        msg: 消息字典（无需额外参数）
    """
    ctx = session.ctx
    requests = ctx.db.friend_requests.list_incoming(session.user_id)
    session.send({
        "type": MT.FRIEND_REQ_LIST_RESP,
        "requests": requests,
    })


def handle_friend_remark(session, msg):
    """设置好友备注

    Args:
        session: Session 实例
        msg: 消息字典，包含 friend_id 和 remark 字段
    """
    ctx = session.ctx
    friend_id = msg.get("friend_id")
    remark = msg.get("remark", "")

    if not friend_id:
        session.send(error("INVALID_PARAM", "缺少好友ID"))
        return

    ctx.db.friends.set_remark(session.user_id, friend_id, remark)

    session.send({
        "type": MT.FRIEND_LIST_RESP,
        "friends": ctx.db.friends.list_by_user(session.user_id),
    })


def handle_friend_list(session, msg):
    """查询好友列表

    返回好友列表，并标注每个好友的在线状态。

    Args:
        session: Session 实例
        msg: 消息字典（无需额外参数）
    """
    ctx = session.ctx
    friends = ctx.db.friends.list_by_user(session.user_id)

    result = []
    for f in friends:
        result.append({
            "user_id": f["user_id"],
            "username": f["username"],
            "remark": f.get("remark", ""),
            "online": ctx.online.is_online(f["user_id"]),
        })

    session.send({
        "type": MT.FRIEND_LIST_RESP,
        "friends": result,
    })


def handle_friend_remove(session, msg):
    """处理删除好友（双向删除关系）

    Args:
        session: Session 实例
        msg: 消息字典，包含 friend_id
    """
    ctx = session.ctx
    friend_id = msg.get("friend_id")

    if not friend_id:
        session.send({"type": MT.FRIEND_REMOVE_RESP, "ok": False, "reason": "缺少好友ID"})
        return

    ctx.db.friends.delete(session.user_id, friend_id)

    session.send({
        "type": MT.FRIEND_REMOVE_RESP,
        "ok": True,
    })

    # 刷新自己的好友列表
    session.send({
        "type": MT.FRIEND_LIST_RESP,
        "friends": ctx.db.friends.list_by_user(session.user_id),
    })
