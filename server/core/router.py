from common.messages import error


class MessageRouter:
    """注册式消息路由"""

    def __init__(self):
        self._handlers = {}

    def register(self, msg_type, fn):
        """注册消息处理函数

        Args:
            msg_type: 消息类型
            fn: 处理函数，签名为 fn(session, msg)

        Raises:
            ValueError: 消息类型重复注册
        """
        if msg_type in self._handlers:
            raise ValueError(f"消息类型重复注册: {msg_type}")
        self._handlers[msg_type] = fn

    def dispatch(self, session, msg):
        fn = self._handlers.get(msg.get("type"))
        if fn is None:
            session.send(error("UNKNOWN_TYPE", f"未知消息类型: {msg.get('type')}"))
            return
        fn(session, msg)
