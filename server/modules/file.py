"""
文件传输模块
Author: gxt

发送流程：FILE_REQ → 校验在线 → 创建DB记录 → 转发给接收方
         FILE_RESP / FILE_DATA → 原样中转到对端
         FILE_END → 更新DB状态 → 转发
"""
from common.messages import MT, error


def register(router, ctx):
    """注册文件传输模块的消息处理函数"""
    router.register(MT.FILE_REQ, handle_file_req)
    router.register(MT.FILE_RESP, handle_file_resp)
    router.register(MT.FILE_DATA, handle_file_data)
    router.register(MT.FILE_END, handle_file_end)


def handle_file_req(session, msg):
    """处理文件传输请求

    1. 校验目标用户是否在线
    2. 在数据库创建文件传输记录
    3. 回填 file_id 并转发请求给接收方
    """
    ctx = session.ctx
    target_id = msg.get("to")

    if target_id is None:
        session.send(error("BAD_REQUEST", "缺少目标用户"))
        return

    if not ctx.online.is_online(target_id):
        session.send(error("OFFLINE", "对方不在线"))
        return

    file_id = ctx.db.files.insert(
        session.user_id, target_id,
        msg.get("file_name", ""),
        msg.get("file_size", 0)
    )

    msg["file_id"] = file_id
    msg["from"] = session.user_id
    ctx.online.send(target_id, msg)


def handle_file_resp(session, msg):
    """处理文件传输应答（接收方接受/拒绝）

    原样转发给发送方
    """
    ctx = session.ctx
    target_id = msg.get("to")

    if target_id is None:
        session.send(error("BAD_REQUEST", "缺少目标用户"))
        return

    msg["from"] = session.user_id
    if not ctx.online.send(target_id, msg):
        session.send(error("OFFLINE", "对方已离线"))


def handle_file_data(session, msg):
    """处理文件数据块

    原样转发给接收方
    """
    ctx = session.ctx
    target_id = msg.get("to")

    if target_id is None:
        session.send(error("BAD_REQUEST", "缺少目标用户"))
        return

    msg["from"] = session.user_id
    if not ctx.online.send(target_id, msg):
        session.send(error("OFFLINE", "对方已离线"))


def handle_file_end(session, msg):
    """处理文件传输结束

    1. 更新数据库中的文件传输记录状态
    2. 转发结束通知给对方
    """
    ctx = session.ctx
    target_id = msg.get("to")
    file_id = msg.get("file_id")
    status = msg.get("status", 1)

    # 更新数据库记录
    if file_id is not None:
        done = (status == 1 or status == 2)
        ctx.db.files.update_status(file_id, status, done=done)

    msg["from"] = session.user_id
    if target_id is not None:
        ctx.online.send(target_id, msg)
