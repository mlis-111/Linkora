import socket
from server.core.client_handler import ClientHandler


class ChatServer:
    """TCP服务器"""

    def __init__(self, ctx, router):
        """初始化服务器

        Args:
            ctx: ServerContext实例
            router: MessageRouter实例
        """
        self.ctx = ctx
        self.router = router

    def serve_forever(self):
        """启动服务器（阻塞）"""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.ctx.config.HOST, self.ctx.config.PORT))
        srv.listen(64)
        print(f"服务器启动成功，监听端口 {self.ctx.config.PORT}")
        while True:
            conn, addr = srv.accept()
            ClientHandler(conn, addr, self.ctx, self.router).start()
