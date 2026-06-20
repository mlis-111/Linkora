class ClientState:
    """客户端全局状态"""

    def __init__(self):
        self.user_id = None
        self.username = None
        self.online_users = []  # 由MainWindow维护
        self.friends = []  # 由FriendPanel维护
