"""聊天模块（服务器端）

处理私聊、公共聊天室消息和历史记录查询。
消息内容在网络上传输时为 AES 密文，入库前解密为明文存储，
查询历史时再加密后返回，保持端到端加密语义。

author: 董钧豪
"""

import time
from common.messages import MT, PUBLIC_ROOM_ID, error


def register(router, ctx):
    """注册聊天模块的消息处理函数

    Args:
        router: MessageRouter 实例
        ctx: ServerContext 实例
    """
    router.register(MT.CHAT, handle_chat)
    router.register(MT.ROOM_CHAT, handle_room_chat)
    router.register(MT.HISTORY_REQ, handle_history)


def handle_chat(session, msg):
    """处理私聊消息

    流程：
        1. 解密消息内容
        2. 明文入库
        3. 原样转发密文给接收方
        4. 接收方不在线时给发送方提示

    Args:
        session: Session 实例
        msg: 消息字典，包含 from/to/content/ts 字段
    """
    ctx = session.ctx
    sender_id = session.user_id
    target_id = msg.get("to")
    cipher_content = msg.get("content", "")

    # 参数校验
    if not target_id:
        session.send(error("INVALID_PARAM", "缺少接收方"))
        return
    if not cipher_content:
        session.send(error("INVALID_PARAM", "消息内容不能为空"))
        return

    # 解密内容，入库
    plain_content = ctx.crypto.decrypt(cipher_content)
    ctx.db.messages.insert(1, sender_id, target_id, None, plain_content)

    # 添加发送方标识和时间戳
    msg["from"] = sender_id
    msg["ts"] = msg.get("ts", int(time.time()))

    # 尝试转发给接收方
    if not ctx.online.send(target_id, msg):
        # 接收方不在线，告知发送方
        session.send(error("OFFLINE", "对方不在线"))


def handle_room_chat(session, msg):
    """处理群聊消息

    流程：
        1. 校验消息中携带 room_id
        2. 校验发送方是否为该群成员
        3. 解密消息内容
        4. 明文入库
        5. 广播密文给群内所有在线成员（包括发送方自己）

    Args:
        session: Session 实例
        msg: 消息字典，包含 room_id/content/ts 字段
    """
    ctx = session.ctx
    room_id = msg.get("room_id", 0)
    cipher_content = msg.get("content", "")

    if not room_id:
        session.send(error("INVALID_PARAM", "缺少群聊ID"))
        return
    if not cipher_content:
        session.send(error("INVALID_PARAM", "消息内容不能为空"))
        return

    # 校验群聊是否存在
    group = ctx.db.groups.get_by_id(room_id)
    if not group:
        session.send(error("NOT_FOUND", "群聊不存在"))
        return

    # 校验发送方是否为群成员
    if not ctx.db.groups.is_member(room_id, session.user_id):
        session.send(error("NOT_MEMBER", "你不是该群成员"))
        return

    # 解密内容，入库
    plain_content = ctx.crypto.decrypt(cipher_content)
    ctx.db.messages.insert(2, session.user_id, None, room_id, plain_content)

    # 添加发送方标识和时间戳
    msg["from"] = session.user_id
    msg["ts"] = msg.get("ts", int(time.time()))

    # 广播给群内所有在线成员
    member_ids = ctx.db.groups.list_member_ids(room_id)
    ctx.online.broadcast_to(msg, member_ids)


def handle_history(session, msg):
    """处理历史记录查询

    根据 scope 参数查询私聊或群聊历史记录，
    将每条记录的 content 加密后返回。

    Args:
        session: Session 实例
        msg: 消息字典，包含 scope/target/room_id 字段
    """
    ctx = session.ctx
    scope = msg.get("scope", "")
    records = []

    if scope == "p2p":
        # 私聊历史：查询当前用户与 target 之间的消息
        target_id = msg.get("target")
        if not target_id:
            session.send(error("INVALID_PARAM", "缺少查询目标"))
            return
        rows = ctx.db.messages.query_p2p(session.user_id, target_id)
        for row in rows:
            records.append({
                "from": row["sender_id"],
                "to": row["receiver_id"],
                "content": ctx.crypto.encrypt(row["content"]),
                "ts": str(row["sent_at"]) if row.get("sent_at") else "",
            })

    elif scope == "room":
        # 群聊历史：查询指定房间的消息
        room_id = msg.get("room_id", PUBLIC_ROOM_ID)
        rows = ctx.db.messages.query_room(room_id)
        for row in rows:
            records.append({
                "from": row["sender_id"],
                "to": row["receiver_id"] or 0,
                "content": ctx.crypto.encrypt(row["content"]),
                "ts": str(row["sent_at"]) if row.get("sent_at") else "",
            })

    else:
        session.send(error("INVALID_PARAM", f"不支持的查询范围: {scope}"))
        return

    session.send({
        "type": MT.HISTORY_RESP,
        "scope": scope,
        "records": records,
    })
