from common.messages import MT


def register(router, ctx):
    """注册用户模块的消息处理函数

    Args:
        router: MessageRouter实例
        ctx: ServerContext实例
    """
    router.register(MT.LOGIN, handle_login)
    router.register(MT.REGISTER, handle_register)
    ctx.on_disconnect(on_disconnect)


def _snapshot(ctx):
    """获取在线用户快照

    Args:
        ctx: ServerContext实例

    Returns:
        list: 在线用户列表
    """
    out = []
    for uid in ctx.online.online_ids():
        u = ctx.db.users.get_by_id(uid)
        if u:
            out.append({
                "user_id": uid,
                "username": u["username"],
                "nickname": u.get("nickname") or u["username"]
            })
    return out


def _all_users_snapshot(ctx):
    """获取所有用户列表（用于好友列表显示）

    Args:
        ctx: ServerContext实例

    Returns:
        list: 所有用户列表
    """
    users = ctx.db.users.get_all_users()
    out = []
    for u in users:
        out.append({
            "user_id": u["user_id"],
            "username": u["username"],
            "nickname": u.get("nickname") or u["username"]
        })
    return out


def handle_login(session, msg):
    """处理登录请求（阶段0冒烟桩：不校验密码）

    Args:
        session: Session实例
        msg: 消息字典
    """
    ctx = session.ctx
    username = msg.get("username", "")

    # 查询用户是否存在
    row = ctx.db.users.get_by_username(username)
    if not row:
        session.send({
            "type": MT.LOGIN_RESP,
            "ok": False,
            "reason": "用户不存在"
        })
        return

    uid = row["user_id"]

    # 检查是否已在线
    if ctx.online.is_online(uid):
        session.send({
            "type": MT.LOGIN_RESP,
            "ok": False,
            "reason": "用户已在线"
        })
        return

    # 绑定用户并加入在线表
    session.bind_user(uid, row["username"])
    ctx.online.add(uid, session._handler)

    # 获取在线用户快照
    snap = _snapshot(ctx)
    all_users = _all_users_snapshot(ctx)  # 获取所有用户

    # 回复登录成功
    session.send({
        "type": MT.LOGIN_RESP,
        "ok": True,
        "user_id": uid,
        "nickname": row.get("nickname") or row["username"],
        "online_users": snap,
        "all_users": all_users  # 添加所有用户列表
    })

    # 广播用户上线
    ctx.online.broadcast({
        "type": MT.USER_LIST,
        "online_users": snap
    })


def handle_register(session, msg):
    """处理注册请求（阶段0冒烟桩：直接返回成功）

    Args:
        session: Session实例
        msg: 消息字典
    """
    session.send({
        "type": MT.REGISTER_RESP,
        "ok": True
    })


def on_disconnect(session):
    """处理用户断开连接

    Args:
        session: Session实例
    """
    if session.user_id is None:
        return

    # 广播用户下线
    snap = _snapshot(session.ctx)
    session.ctx.online.broadcast({
        "type": MT.USER_LIST,
        "online_users": snap
    })
