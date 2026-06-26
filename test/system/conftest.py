"""系统测试共享 fixtures

启动真实 ChatServer（mock DB），通过真实 TCP socket 测试完整协议栈。

与集成测试的区别：
- 集成测试：直接调用 handler 函数测试组件协作
- 系统测试：通过 TCP socket 发送真实协议消息，测试完整网络栈
"""

import socket
import threading
import time
import hashlib
import os

import pytest
from unittest.mock import MagicMock

from common.crypto import CryptoUtil
from common.protocol import send_msg, recv_msg
from common.messages import MT
from server.core.context import ServerContext
from server.core.router import MessageRouter
from server.core.server import ChatServer
from server.modules import user, chat, friend, group, file, ai


# ════════════════════════════════════════════════════════════════
# 测试服务器
# ════════════════════════════════════════════════════════════════

class TestServer:
    """在随机端口启动的真实 ChatServer（仅 DB 为 mock）

    用法：
        ts = TestServer()
        ts.start()
        sock = ts.connect()        # 返回已连接的 socket
        ts.send_dict(sock, {...})  # 发送协议消息
        resp = ts.recv_dict(sock)  # 接收协议消息
        ts.stop()
    """

    __test__ = False  # 不是 pytest 测试类

    def __init__(self):
        self._crypto = CryptoUtil(b"system_test_key_16b")
        self._host = "127.0.0.1"
        self._port = self._find_free_port()
        self._srv_sock = None
        self._srv_thread = None
        self._running = False

        # 构建 mock DB
        self.db = MagicMock()
        self.db.users = MagicMock()
        self.db.messages = MagicMock()
        self.db.friends = MagicMock()
        self.db.files = MagicMock()
        self.db.ai_msg = MagicMock()
        self.db.friend_requests = MagicMock()
        self.db.groups = MagicMock()

        # 构建 ServerContext
        self.ctx = ServerContext.__new__(ServerContext)
        self.ctx.config = MagicMock()
        self.ctx.config.HOST = self._host
        self.ctx.config.PORT = self._port
        self.ctx.db = self.db
        self.ctx.crypto = self._crypto
        self.ctx.workers = MagicMock()
        self.ctx._disconnect_hooks = []
        from server.core.online import OnlineRegistry
        self.ctx.online = OnlineRegistry()

        # 构建 Router 并注册所有模块
        self.router = MessageRouter()
        for mod in (user, chat, friend, group, file, ai):
            mod.register(self.router, self.ctx)

        # 构建 ChatServer（不调用 serve_forever，手动管理）
        self._chat_srv = ChatServer(self.ctx, self.router)

    @staticmethod
    def _find_free_port():
        """找一个空闲端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @property
    def port(self):
        return self._port

    @property
    def crypto(self):
        return self._crypto

    def start(self):
        """启动服务器（后台线程监听）"""
        self._srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv_sock.bind((self._host, self._port))
        self._srv_sock.listen(16)
        self._srv_sock.settimeout(0.5)
        self._running = True

        def accept_loop():
            while self._running:
                try:
                    conn, addr = self._srv_sock.accept()
                    from server.core.client_handler import ClientHandler
                    ClientHandler(conn, addr, self.ctx, self.router).start()
                except socket.timeout:
                    continue
                except OSError:
                    break

        self._srv_thread = threading.Thread(target=accept_loop, daemon=True)
        self._srv_thread.start()
        time.sleep(0.05)  # 等待监听就绪

    def stop(self):
        """停止服务器"""
        self._running = False
        if self._srv_thread:
            self._srv_thread.join(timeout=2)
        if self._srv_sock:
            try:
                self._srv_sock.close()
            except OSError:
                pass

    def connect(self):
        """创建并返回一个已连接的 socket"""
        sock = socket.create_connection((self._host, self._port), timeout=3)
        return sock

    def send_dict(self, sock, msg: dict):
        """通过 socket 发送协议消息"""
        send_msg(sock, msg)

    def recv_dict(self, sock, timeout=2.0):
        """通过 socket 接收协议消息"""
        sock.settimeout(timeout)
        try:
            return recv_msg(sock)
        except socket.timeout:
            return None

    def disconnect(self, sock):
        """关闭连接"""
        try:
            sock.close()
        except OSError:
            pass

    # ── 便捷方法 ──

    def setup_user(self, uid=100, username="testuser", password="123456",
                   nickname="测试用户", online=False):
        """在 mock DB 中设置一个用户"""
        salt = os.urandom(16).hex()
        pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        self.db.users.get_by_username.return_value = {
            "user_id": uid, "username": username,
            "password_hash": pwd_hash, "salt": salt,
            "nickname": nickname,
        }
        self.db.users.get_by_id.return_value = {
            "user_id": uid, "username": username, "nickname": nickname,
        }
        return uid

    def setup_all_users(self, users):
        """设置全量用户列表"""
        self.db.users.get_all_users.return_value = users


# ════════════════════════════════════════════════════════════════
# pytest fixtures
# ════════════════════════════════════════════════════════════════

@pytest.fixture
def server():
    """启动一个测试服务器（function 级别，自动清理）"""
    ts = TestServer()
    ts.start()
    yield ts
    ts.stop()


@pytest.fixture
def client(server):
    """创建一个已连接的客户端 socket（自动清理）"""
    sock = server.connect()
    yield sock
    server.disconnect(sock)


# ════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════

def login(server, sock, username="testuser", password="123456"):
    """登录辅助：发送登录请求并返回响应"""
    server.send_dict(sock, {
        "type": MT.LOGIN,
        "username": username,
        "password": password,
    })
    return server.recv_dict(sock)


def register(server, sock, username, password, nickname=""):
    """注册辅助"""
    server.send_dict(sock, {
        "type": MT.REGISTER,
        "username": username,
        "password": password,
        "nickname": nickname,
    })
    return server.recv_dict(sock)


def send_chat(server, sock, to_id, content):
    """发送私聊消息"""
    server.send_dict(sock, {
        "type": MT.CHAT,
        "to": to_id,
        "content": content,
    })
    return server.recv_dict(sock)


def recv_all(server, sock, count=1, timeout=1.0):
    """接收多条消息"""
    results = []
    sock.settimeout(timeout)
    for _ in range(count):
        try:
            msg = recv_msg(sock)
            if msg is None:
                break
            results.append(msg)
        except socket.timeout:
            break
    return results
