import socket
import threading
import logging
from common.protocol import send_msg, recv_msg
from common.messages import error
from server.core.session import Session


class ClientHandler(threading.Thread):
    """每连接一线程的处理器"""

    def __init__(self, conn, addr, ctx, router):
        """初始化处理器

        Args:
            conn: socket连接
            addr: 客户端地址
            ctx: ServerContext实例
            router: MessageRouter实例
        """
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.ctx = ctx
        self.router = router
        self.session = Session(ctx, self)
        self._send_lock = threading.Lock()

    def send(self, msg):
        """发送消息（线程安全）

        Args:
            msg: 消息字典
        """
        with self._send_lock:
            try:
                send_msg(self.conn, msg)
            except OSError:
                pass

    def run(self):
        """线程主循环"""
        try:
            while True:
                msg = recv_msg(self.conn)
                if msg is None:
                    break
                try:
                    self.router.dispatch(self.session, msg)
                except Exception:
                    logging.exception("handler error")
                    self.send(error("SERVER_ERROR", "服务器处理异常"))
        except OSError:
            pass
        finally:
            self._cleanup()

    def _cleanup(self):
        """清理连接"""
        if self.session.user_id is not None:
            self.ctx.online.remove(self.session.user_id)
            self.ctx.fire_disconnect(self.session)
        try:
            self.conn.close()
        except OSError:
            pass
