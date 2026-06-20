import socket
import threading
from common.protocol import send_msg, recv_msg


class NetworkClient:
    """网络客户端（收发线程 + 订阅分发 + GUI线程编组）"""

    def __init__(self, host, port, tk_root):
        """初始化网络客户端

        Args:
            host: 服务器地址
            port: 服务器端口
            tk_root: Tkinter根窗口
        """
        self._host = host
        self._port = port
        self._root = tk_root
        self._sock = None
        self._send_lock = threading.Lock()
        self._subs = {}  # type -> [callback]

    def connect(self):
        """连接服务器并启动接收线程"""
        self._sock = socket.create_connection((self._host, self._port))
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def on(self, msg_type, callback):
        """订阅消息类型

        Args:
            msg_type: 消息类型
            callback: 回调函数
        """
        self._subs.setdefault(msg_type, []).append(callback)

    def send(self, msg):
        """发送消息（线程安全）

        Args:
            msg: 消息字典
        """
        with self._send_lock:
            send_msg(self._sock, msg)

    def _recv_loop(self):
        """接收线程主循环"""
        while True:
            msg = recv_msg(self._sock)
            if msg is None:
                self._root.after(0, self._emit, {"type": "__disconnected__"})
                break
            self._root.after(0, self._emit, msg)

    def _emit(self, msg):
        """分发消息给订阅者（已在GUI线程）

        Args:
            msg: 消息字典
        """
        for cb in self._subs.get(msg.get("type"), []):
            try:
                cb(msg)
            except Exception as e:
                print(f"回调错误: {e}")
