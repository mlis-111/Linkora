class Session:
    """每连接会话对象"""

    def __init__(self, ctx, handler):
        """初始化会话

        Args:
            ctx: ServerContext实例
            handler: ClientHandler实例
        """
        self.ctx = ctx
        self._handler = handler
        self.user_id = None  # 登录前为 None
        self.username = None

    def send(self, msg):
        """向本连接发送消息

        Args:
            msg: 消息字典
        """
        self._handler.send(msg)

    def bind_user(self, user_id, username):
        """登录时绑定用户

        Args:
            user_id: 用户ID
            username: 用户名
        """
        self.user_id = user_id
        self.username = username
