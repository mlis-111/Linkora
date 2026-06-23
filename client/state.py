class ClientState:
    """客户端全局状态"""

    def __init__(self):
        self.user_id = None
        self.username = None
        self.online_users = []  # 当前在线用户列表
        self.all_users = []     # 所有用户列表（从数据库获取）
        self.friends = []  # 由FriendPanel维护
