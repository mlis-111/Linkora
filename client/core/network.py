import socket
import threading
from PyQt5.QtCore import QObject, pyqtSignal
from common.protocol import send_msg, recv_msg


class NetworkClient(QObject):
    _msg_signal = pyqtSignal(dict)   # 内部用，接收线程→主线程

    def __init__(self, host, port):
        super().__init__()
        self._host = host
        self._port = port
        self._sock = None
        self._send_lock = threading.Lock()
        self._subs = {}              # type -> [callback]，接口与原方案完全一致

        self._msg_signal.connect(self._dispatch)

    def connect(self):
        self._sock = socket.create_connection((self._host, self._port))
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def on(self, msg_type, callback):
        """接口与原方案完全一致，各面板照常调用"""
        self._subs.setdefault(msg_type, []).append(callback)

    def send(self, msg: dict):
        """接口与原方案完全一致"""
        with self._send_lock:
            send_msg(self._sock, msg)

    def _recv_loop(self):
        while True:
            msg = recv_msg(self._sock)
            if msg is None:
                self._msg_signal.emit({"type": "__disconnected__"})
                break
            self._msg_signal.emit(msg)   # 线程安全切回主线程

    def _dispatch(self, msg: dict):
        for cb in self._subs.get(msg.get("type"), []):
            cb(msg)
