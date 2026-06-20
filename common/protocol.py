import json
import struct

HEADER = 4


def send_msg(sock, msg: dict):
    """发送一条消息（4字节长度前缀 + JSON消息体）"""
    data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_msg(sock):
    """接收一条完整消息；连接关闭返回 None"""
    header = _recv_exactly(sock, HEADER)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    body = _recv_exactly(sock, length)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


def _recv_exactly(sock, n):
    """精确接收n字节数据"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
