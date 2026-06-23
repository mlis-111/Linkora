"""
用户管理模块 — 武家辉

处理用户注册、登录、登出以及断开连接清理。
遵守 common/messages.py 中定义的消息契约。

@author 武家辉
"""

import hashlib
import os

from common.messages import MT


def _verify_password(input_password: str, stored_hash: str, salt: str) -> bool:
    """校验密码，兼容 MD5（预置账号）和 SHA256（新注册用户）

    Args:
        input_password: 用户输入的明文密码
        stored_hash: 数据库中存储的 hash 值
        salt: 数据库中存储的盐值

    Returns:
        bool: 密码是否匹配
    """
    if len(stored_hash) == 64:
        # SHA256: hash = sha256(salt + password)
        return hashlib.sha256((salt + input_password).encode()).hexdigest() == stored_hash
    # 兼容 init.sql 预置账号的 MD5 格式
    return hashlib.md5(input_password.encode()).hexdigest() == stored_hash


def register(router, ctx):
    """注册用户模块的消息处理函数

    Args:
        router: MessageRouter实例
        ctx: ServerContext实例
    """
    router.register(MT.LOGIN, handle_login)
    router.register(MT.REGISTER, handle_register)
    router.register(MT.LOGOUT, handle_logout)
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
    """处理登录请求

    校验流程：用户存在 → 密码验证(SHA256/MD5兼容) → 防重复登录 → 上线广播

    Args:
        session: Session实例
        msg: 消息字典，需包含 username, password
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

    # 校验密码
    if not _verify_password(msg.get("password", ""), row["password_hash"], row["salt"]):
        session.send({
            "type": MT.LOGIN_RESP,
            "ok": False,
            "reason": "密码错误"
        })
        return

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
    """处理注册请求

    校验流程：非空校验 → 用户名查重 → 生成 salt → SHA256 哈希 → 写入数据库

    Args:
        session: Session实例
        msg: 消息字典，需包含 username, password
    """
    ctx = session.ctx
    username = msg.get("username", "").strip()
    password = msg.get("password", "")

    # 非空校验
    if not username or not password:
        session.send({
            "type": MT.REGISTER_RESP,
            "ok": False,
            "reason": "用户名和密码不能为空"
        })
        return

    # 用户名已存在
    if ctx.db.users.exists(username):
        session.send({
            "type": MT.REGISTER_RESP,
            "ok": False,
            "reason": "用户名已存在"
        })
        return

    # 生成 salt + SHA256 哈希
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()

    # 插入数据库
    ctx.db.users.insert_user(username, pwd_hash, salt, nickname=username, is_ai_bot=0)

    # 返回成功
    session.send({
        "type": MT.REGISTER_RESP,
        "ok": True
    })


def handle_logout(session, msg):
    """处理登出请求

    流程：从在线表移除 → 广播下线通知 → 关闭连接

    Args:
        session: Session实例
        msg: 消息字典
    """
    ctx = session.ctx
    uid = session.user_id
    if uid is None:
        return

    # 从在线表移除
    ctx.online.remove(uid)

    # 广播用户下线
    snap = _snapshot(ctx)
    ctx.online.broadcast({
        "type": MT.USER_LIST,
        "online_users": snap
    })

    # 关闭连接（会触发 ClientHandler._cleanup，但 uid 已移除所以不会重复广播）
    try:
        session._handler.conn.close()
    except OSError:
        pass


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
