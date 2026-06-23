from server.db.base_dao import BaseDAO


class UserDAO(BaseDAO):
    """用户数据访问对象"""

    def get_by_username(self, username):
        """根据用户名查询用户

        Args:
            username: 用户名

        Returns:
            dict or None: 用户信息
        """
        return self._query_one("SELECT * FROM user WHERE username=%s", (username,))

    def get_by_id(self, user_id):
        """根据用户ID查询用户

        Args:
            user_id: 用户ID

        Returns:
            dict or None: 用户信息
        """
        return self._query_one("SELECT * FROM user WHERE user_id=%s", (user_id,))

    def get_all_users(self):
        """获取所有用户列表

        Returns:
            list: 所有用户信息列表
        """
        return self._query("SELECT user_id, username, nickname FROM user", ())

    def exists(self, username):
        """判断用户名是否存在

        Args:
            username: 用户名

        Returns:
            bool: 是否存在
        """
        return self.get_by_username(username) is not None

    def insert_user(self, username, password_hash, salt, nickname, is_ai_bot=0):
        """插入新用户

        Args:
            username: 用户名
            password_hash: 密码哈希
            salt: 盐值
            nickname: 昵称
            is_ai_bot: 是否为AI机器人

        Returns:
            int: 新用户的user_id
        """
        return self._execute(
            "INSERT INTO user(username,password_hash,salt,nickname,is_ai_bot)"
            " VALUES(%s,%s,%s,%s,%s)",
            (username, password_hash, salt, nickname, is_ai_bot)
        )


class MessageDAO(BaseDAO):
    """消息数据访问对象"""

    def insert(self, msg_type, sender_id, receiver_id, room_id, content):
        """插入消息记录

        Args:
            msg_type: 消息类型（1=私聊, 2=群聊）
            sender_id: 发送者ID
            receiver_id: 接收者ID（群聊时为None）
            room_id: 房间ID（私聊时为None）
            content: 消息内容（明文）

        Returns:
            int: 消息ID
        """
        return self._execute(
            "INSERT INTO message(msg_type,sender_id,receiver_id,room_id,content)"
            " VALUES(%s,%s,%s,%s,%s)",
            (msg_type, sender_id, receiver_id, room_id, content)
        )

    def query_p2p(self, uid_a, uid_b, limit=200):
        """查询两人私聊历史

        Args:
            uid_a: 用户A的ID
            uid_b: 用户B的ID
            limit: 返回消息数量限制

        Returns:
            list: 消息列表
        """
        return self._query(
            "SELECT * FROM message WHERE msg_type=1 AND "
            "((sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)) "
            "ORDER BY sent_at ASC LIMIT %s",
            (uid_a, uid_b, uid_b, uid_a, limit)
        )

    def query_room(self, room_id, limit=200):
        """查询群聊历史

        Args:
            room_id: 房间ID
            limit: 返回消息数量限制

        Returns:
            list: 消息列表
        """
        return self._query(
            "SELECT * FROM message WHERE msg_type=2 AND room_id=%s "
            "ORDER BY sent_at ASC LIMIT %s",
            (room_id, limit)
        )


class FriendDAO(BaseDAO):
    """好友关系数据访问对象"""

    def add(self, user_id, friend_id, remark=None):
        """添加好友关系

        Args:
            user_id: 用户ID
            friend_id: 好友ID
            remark: 备注

        Returns:
            int: 影响行数
        """
        return self._execute(
            "INSERT IGNORE INTO friend(user_id,friend_id,remark) VALUES(%s,%s,%s)",
            (user_id, friend_id, remark)
        )

    def set_remark(self, user_id, friend_id, remark):
        """设置好友备注

        Args:
            user_id: 用户ID
            friend_id: 好友ID
            remark: 备注
        """
        self._execute(
            "UPDATE friend SET remark=%s WHERE user_id=%s AND friend_id=%s",
            (remark, user_id, friend_id)
        )

    def list_by_user(self, user_id):
        """查询用户的好友列表

        Args:
            user_id: 用户ID

        Returns:
            list: 好友列表
        """
        return self._query(
            "SELECT f.friend_id AS user_id, u.username, f.remark "
            "FROM friend f JOIN user u ON u.user_id=f.friend_id WHERE f.user_id=%s",
            (user_id,)
        )


class FileDAO(BaseDAO):
    """文件传输记录数据访问对象"""

    def insert(self, sender_id, receiver_id, file_name, file_size, status=0):
        """创建文件传输记录

        Args:
            sender_id: 发送者ID
            receiver_id: 接收者ID
            file_name: 文件名
            file_size: 文件大小
            status: 状态（0=传输中, 1=成功, 2=失败）

        Returns:
            int: 文件记录ID
        """
        return self._execute(
            "INSERT INTO file_record(sender_id,receiver_id,file_name,file_size,status)"
            " VALUES(%s,%s,%s,%s,%s)",
            (sender_id, receiver_id, file_name, file_size, status)
        )

    def update_status(self, file_id, status, done=False):
        """更新文件传输状态

        Args:
            file_id: 文件记录ID
            status: 状态（0=传输中, 1=成功, 2=失败）
            done: 是否完成（更新transferred_at）
        """
        if done:
            sql = "UPDATE file_record SET status=%s, transferred_at=NOW() WHERE file_id=%s"
        else:
            sql = "UPDATE file_record SET status=%s WHERE file_id=%s"
        self._execute(sql, (status, file_id))
