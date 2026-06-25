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

    def get_by_nickname(self, nickname):
        return self._query_one("SELECT * FROM user WHERE nickname=%s", (nickname,))

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

    def delete(self, user_id, friend_id):
        """删除好友关系（双向）

        Args:
            user_id: 用户ID
            friend_id: 好友ID

        Returns:
            int: 影响行数
        """
        return self._execute(
            "DELETE FROM friend WHERE (user_id=%s AND friend_id=%s) OR (user_id=%s AND friend_id=%s)",
            (user_id, friend_id, friend_id, user_id)
        )

# /////////////////////////////////////////////////////////////////////////////////////////
class GroupDAO(BaseDAO):
    """群聊数据访问对象"""

    def create(self, group_name, owner_id):
        """创建群聊，自动生成 group_id

        Args:
            group_name: 群聊名称
            owner_id: 创建者ID

        Returns:
            int: 自动生成的 group_id
        """
        return self._execute(
            "INSERT INTO chat_group(group_name,owner_id) VALUES(%s,%s)",
            (group_name, owner_id)
        )

    def get_by_id(self, group_id):
        """根据群聊ID查询群聊信息

        Args:
            group_id: 群聊ID

        Returns:
            dict or None: 群聊信息
        """
        return self._query_one(
            "SELECT * FROM chat_group WHERE group_id=%s",
            (group_id,)
        )

    def add_member(self, group_id, user_id):
        """添加群成员

        Args:
            group_id: 群聊ID
            user_id: 用户ID

        Returns:
            int: 影响行数
        """
        return self._execute(
            "INSERT IGNORE INTO group_member(group_id,user_id) VALUES(%s,%s)",
            (group_id, user_id)
        )

    def remove_member(self, group_id, user_id):
        """移除群成员

        Args:
            group_id: 群聊ID
            user_id: 用户ID

        Returns:
            int: 影响行数
        """
        return self._execute(
            "DELETE FROM group_member WHERE group_id=%s AND user_id=%s",
            (group_id, user_id)
        )

    def is_member(self, group_id, user_id):
        """判断用户是否为群成员

        Args:
            group_id: 群聊ID
            user_id: 用户ID

        Returns:
            bool: 是否为成员
        """
        row = self._query_one(
            "SELECT 1 FROM group_member WHERE group_id=%s AND user_id=%s",
            (group_id, user_id)
        )
        return row is not None

    def list_by_user(self, user_id):
        """查询用户加入的所有群聊

        Args:
            user_id: 用户ID

        Returns:
            list: 群聊信息列表（含未读数占位）
        """
        return self._query(
            "SELECT g.group_id, g.group_name, g.owner_id, "
            "gm.remark, "
            "CAST(gm.joined_at AS CHAR) AS joined_at "
            "FROM chat_group g JOIN group_member gm ON g.group_id=gm.group_id "
            "WHERE gm.user_id=%s ORDER BY gm.joined_at DESC",
            (user_id,)
        )

    def list_available(self, user_id):
        """查询用户尚未加入的群聊（用于选择加入）

        Args:
            user_id: 用户ID

        Returns:
            list: 可加入的群聊列表
        """
        return self._query(
            "SELECT g.group_id, g.group_name FROM chat_group g "
            "WHERE g.group_id NOT IN "
            "(SELECT gm.group_id FROM group_member gm WHERE gm.user_id=%s) "
            "ORDER BY g.created_at ASC",
            (user_id,)
        )

    def list_members(self, group_id):
        """查询群成员列表

        Args:
            group_id: 群聊ID

        Returns:
            list: 成员信息列表
        """
        return self._query(
            "SELECT u.user_id, u.username, u.nickname, gm.role, gm.remark "
            "FROM group_member gm JOIN user u ON u.user_id=gm.user_id "
            "WHERE gm.group_id=%s",
            (group_id,)
        )

    def list_member_ids(self, group_id):
        """查询群成员ID列表（用于广播）

        Args:
            group_id: 群聊ID

        Returns:
            list: 成员user_id列表
        """
        rows = self._query(
            "SELECT user_id FROM group_member WHERE group_id=%s",
            (group_id,)
        )
        return [r["user_id"] for r in rows]

    def update_name(self, group_id, new_name):
        """更新群聊名称

        Args:
            group_id: 群聊ID
            new_name: 新群名

        Returns:
            int: 影响行数
        """
        return self._execute(
            "UPDATE chat_group SET group_name=%s WHERE group_id=%s",
            (new_name, group_id)
        )

    def set_remark(self, user_id, group_id, remark):
        """设置用户对群聊的个人备注

        Args:
            user_id: 用户ID
            group_id: 群聊ID
            remark: 备注内容
        """
        self._execute(
            "UPDATE group_member SET remark=%s WHERE user_id=%s AND group_id=%s",
            (remark, user_id, group_id)
        )

    def set_role(self, group_id, user_id, role):
        """设置群成员角色

        Args:
            group_id: 群聊ID
            user_id: 用户ID
            role: 角色（0=成员, 1=管理员）
        """
        self._execute(
            "UPDATE group_member SET role=%s WHERE group_id=%s AND user_id=%s",
            (role, group_id, user_id)
        )

    def get_role(self, group_id, user_id):
        """查询用户在群中的角色

        Args:
            group_id: 群聊ID
            user_id: 用户ID

        Returns:
            int: 角色（0=成员, 1=管理员），非成员返回0
        """
        row = self._query_one(
            "SELECT role FROM group_member WHERE group_id=%s AND user_id=%s",
            (group_id, user_id)
        )
        return row["role"] if row else 0


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


class AIMessageDAO(BaseDAO):
    """AI 对话消息 DAO —— 不影响 message 表原有操作，独立管理 AI 历史"""

    def insert(self, msg_type, sender_id, receiver_id, content, conv_id):
        """插入 AI 消息（带 conv_id）"""
        return self._execute(
            "INSERT INTO message(msg_type,sender_id,receiver_id,room_id,content,conv_id)"
            " VALUES(%s,%s,%s,NULL,%s,%s)",
            (msg_type, sender_id, receiver_id, content, conv_id)
        )

    def query_by_conv(self, conv_id):
        """查询指定 conv_id 的所有消息"""
        return self._query(
            "SELECT * FROM message WHERE conv_id=%s ORDER BY sent_at ASC",
            (conv_id,)
        )

    def list_conv_ids(self, user_id):
        """列出用户所有 AI 对话 conv_id（按最近消息倒序）"""
        rows = self._query(
            "SELECT conv_id, MAX(sent_at) AS last_ts FROM message "
            "WHERE conv_id IS NOT NULL AND (sender_id=%s OR receiver_id=%s) "
            "GROUP BY conv_id ORDER BY last_ts DESC",
            (user_id, user_id)
        )
        return [r["conv_id"] for r in rows]

    def delete_by_conv(self, conv_id):
        """删除指定 conv_id 的所有消息"""
        return self._execute(
            "DELETE FROM message WHERE conv_id=%s",
            (conv_id,)
class FriendRequestDAO(BaseDAO):
    """好友申请数据访问对象"""

    def create(self, from_id, to_id, message=""):
        """创建好友申请

        Args:
            from_id: 申请人ID
            to_id: 接收人ID
            message: 申请附言

        Returns:
            int: 申请记录ID
        """
        return self._execute(
            "INSERT INTO friend_request(from_id,to_id,message,status) VALUES(%s,%s,%s,0)",
            (from_id, to_id, message)
        )

    def find_pending(self, from_id, to_id):
        """查询两人间是否有待处理的申请

        Returns:
            dict or None: 申请记录
        """
        return self._query_one(
            "SELECT * FROM friend_request WHERE from_id=%s AND to_id=%s AND status=0",
            (from_id, to_id)
        )

    def find_reverse_pending(self, uid_a, uid_b):
        """查询双向是否有待处理的申请（A申请B 或 B申请A）

        Returns:
            dict or None: 申请记录
        """
        return self._query_one(
            "SELECT * FROM friend_request WHERE ((from_id=%s AND to_id=%s) OR (from_id=%s AND to_id=%s)) AND status=0",
            (uid_a, uid_b, uid_b, uid_a)
        )

    def list_incoming(self, user_id):
        """查询收到的申请（含待处理、已同意、已拒绝）"""
        return self._query(
            "SELECT r.id, r.from_id, r.message, r.status, r.reject_reason, "
            "u.username, u.nickname "
            "FROM friend_request r JOIN user u ON u.user_id=r.from_id "
            "WHERE r.to_id=%s ORDER BY r.created_at DESC",
            (user_id,)
        )

    def list_outgoing(self, user_id):
        """查询发出的申请（含目标用户名称）"""
        return self._query(
            "SELECT r.id, r.to_id AS target_id, r.message, r.status, r.reject_reason, "
            "u.username, u.nickname "
            "FROM friend_request r JOIN user u ON u.user_id=r.to_id "
            "WHERE r.from_id=%s ORDER BY r.created_at DESC",
            (user_id,)
        )

    def update_status(self, req_id, status):
        """更新申请状态

        Args:
            req_id: 申请记录ID
            status: 新状态（1=已同意 2=已拒绝）
        """
        self._execute(
            "UPDATE friend_request SET status=%s WHERE id=%s",
            (status, req_id)
        )

    def reject(self, req_id, reason=""):
        """拒绝申请，记录理由

        Args:
            req_id: 申请记录ID
            reason: 拒绝理由
        """
        self._execute(
            "UPDATE friend_request SET status=2, reject_reason=%s WHERE id=%s",
            (reason, req_id)
        )
