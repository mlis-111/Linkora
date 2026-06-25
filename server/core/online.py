import threading


class OnlineRegistry:
    """在线连接表（线程安全）"""

    def __init__(self):
        self._lock = threading.RLock()
        self._by_uid = {}  # user_id -> ClientHandler

    def add(self, user_id, handler):
        """用户上线

        Args:
            user_id: 用户ID
            handler: ClientHandler实例
        """
        with self._lock:
            self._by_uid[user_id] = handler

    def remove(self, user_id):
        """用户下线

        Args:
            user_id: 用户ID
        """
        with self._lock:
            self._by_uid.pop(user_id, None)

    def is_online(self, user_id):
        """检查用户是否在线

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否在线
        """
        with self._lock:
            return user_id in self._by_uid

    def online_ids(self):
        """获取所有在线用户ID列表

        Returns:
            list: 在线用户ID列表
        """
        with self._lock:
            return list(self._by_uid.keys())

    def send(self, user_id, msg):
        """发送消息给指定用户

        Args:
            user_id: 用户ID
            msg: 消息字典

        Returns:
            bool: 是否发送成功（用户是否在线）
        """
        with self._lock:
            h = self._by_uid.get(user_id)
        if h:
            h.send(msg)
            return True
        return False

    def broadcast(self, msg, exclude=None):
        """广播消息给所有在线用户

        Args:
            msg: 消息字典
            exclude: 排除的用户ID（可选）
        """
        with self._lock:
            targets = list(self._by_uid.items())
        for uid, h in targets:
            if uid != exclude:
                h.send(msg)

    def broadcast_to(self, msg, user_ids):
        """广播消息给指定ID列表中的在线用户

        Args:
            msg: 消息字典
            user_ids: 用户ID列表
        """
        with self._lock:
            for uid in user_ids:
                h = self._by_uid.get(uid)
                if h:
                    h.send(msg)
