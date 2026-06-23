"""
文件传输模块 —— 服务端缓冲中转
Author: gxt

流程：
  发送方 → FILE_REQ → 服务端创建记录+临时缓冲，回 ACK（不转发给接收方）
  发送方 → FILE_DATA → 服务端写入缓冲（不转发）
  发送方 → FILE_END → 服务端关闭缓冲 → 通知接收方 FILE_REQ
  接收方 → FILE_RESP(accept) → 服务端从缓冲读取 → 转发给接收方 → 清理
"""
import os
import tempfile
from common.messages import MT, error

# 文件缓冲: file_id -> {fh, path, from_id, to_id, file_name, file_size, seq}
_file_buffers = {}


def register(router, ctx):
    router.register(MT.FILE_REQ, handle_file_req)
    router.register("file_accept", handle_file_resp)
    router.register(MT.FILE_DATA, handle_file_data)
    router.register(MT.FILE_END, handle_file_end)


def _ack(session, file_id):
    session.send({"type": "file_req_ack", "file_id": file_id})


def handle_file_req(session, msg):
    """发送方请求传输 → 创建 DB 记录 + 缓冲文件，不转发给接收方"""
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
        msg.get("file_name", ""), msg.get("file_size", 0))

    # 创建临时缓冲文件
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".buf")
    _file_buffers[file_id] = {
        "fh": tmp, "path": tmp.name,
        "from_id": session.user_id, "to_id": target_id,
        "file_name": msg.get("file_name", ""),
        "file_size": msg.get("file_size", 0),
        "done": False,
    }

    _ack(session, file_id)


def handle_file_data(session, msg):
    """发送方数据块 → 写入缓冲，不转发"""
    file_id = msg.get("file_id")
    buf = _file_buffers.get(file_id)
    if buf is None:
        return
    try:
        import base64
        raw = base64.b64decode(msg.get("data", ""))
        buf["fh"].write(raw)
    except Exception:
        pass


def handle_file_end(session, msg):
    """发送方传完 → 关闭缓冲 + 通知接收方"""
    ctx = session.ctx
    file_id = msg.get("file_id")
    buf = _file_buffers.get(file_id)
    if buf is None:
        return

    buf["fh"].close()
    buf["done"] = True

    # 更新 DB
    ctx.db.files.update_status(file_id, msg.get("status", 1), done=True)

    # 通知接收方（此时才转发 FILE_REQ）
    target_id = buf["to_id"]
    ctx.online.send(target_id, {
        "type": MT.FILE_REQ,
        "file_id": file_id,
        "from": buf["from_id"],
        "file_name": buf["file_name"],
        "file_size": buf["file_size"],
    })


def handle_file_resp(session, msg):
    """接收方应答 → 接受：转发缓冲数据 → 拒绝：清理缓冲"""
    ctx = session.ctx
    file_id = msg.get("file_id")
    buf = _file_buffers.pop(file_id, None)
    if buf is None:
        return

    if msg.get("accept"):
        target_id = session.user_id
        CHUNK = 64 * 1024
        import base64
        try:
            with open(buf["path"], "rb") as fh:
                seq = 0
                while True:
                    data = fh.read(CHUNK)
                    if not data:
                        break
                    ctx.online.send(target_id, {
                        "type": MT.FILE_DATA,
                        "file_id": file_id,
                        "from": buf["from_id"],
                        "seq": seq,
                        "data": base64.b64encode(data).decode("ascii"),
                    })
                    seq += 1
        except OSError:
            pass
        ctx.online.send(target_id, {
            "type": MT.FILE_END,
            "file_id": file_id,
            "from": buf["from_id"],
            "status": 1,
        })
        # 通知发送方：对方已接受
        ctx.online.send(buf["from_id"], {
            "type": "file_status", "file_id": file_id,
            "status": "accepted",
        })
    else:
        ctx.db.files.update_status(file_id, 2, done=True)
        # 通知发送方：对方已拒绝
        ctx.online.send(buf["from_id"], {
            "type": "file_status", "file_id": file_id,
            "status": "rejected",
        })

    # 清理临时文件
    try:
        os.remove(buf["path"])
    except OSError:
        pass
