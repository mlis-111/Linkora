from concurrent.futures import ThreadPoolExecutor
from server.db.daos import (UserDAO, MessageDAO, FriendDAO, FileDAO,
                             AIMessageDAO)
from server.core.online import OnlineRegistry


class _DB:
    """数据库访问对象集合"""

    def __init__(self, pool):
        self.users = UserDAO(pool)
        self.messages = MessageDAO(pool)
        self.friends = FriendDAO(pool)
        self.files = FileDAO(pool)
        self.ai_msg = AIMessageDAO(pool)


class ServerContext:
    """服务器全局上下文（依赖注入容器）"""

    def __init__(self, config, pool, crypto):
        """初始化上下文

        Args:
            config: Config实例
            pool: DBPool实例
            crypto: CryptoUtil实例
        """
        self.config = config
        self.db = _DB(pool)
        self.online = OnlineRegistry()
        self.crypto = crypto
        self.workers = ThreadPoolExecutor(max_workers=4)
        self._disconnect_hooks = []

    def on_disconnect(self, fn):
        """注册断开连接钩子

        Args:
            fn: 钩子函数，签名为 fn(session)
        """
        self._disconnect_hooks.append(fn)

    def fire_disconnect(self, session):
        """触发所有断开连接钩子

        Args:
            session: Session实例
        """
        for fn in self._disconnect_hooks:
            try:
                fn(session)
            except Exception:
                pass
