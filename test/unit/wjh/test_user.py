"""
server/modules/user.py 单元测试 — wjh

测试覆盖：
  1. 正常流程（正确登录、注册成功、SHA256 和 MD5 兼容）
  2. 异常流程（用户不存在、密码错误、已在线、用户名已存在）
  3. 空值处理（空用户名、空密码）
  4. 边界条件（SHA256 哈希格式 64 位 hex）
  5. 兼容性（MD5 预置账号兼容）
  6. 集成往返（注册后登录验证）

@author 武家辉
"""
import unittest
import hashlib
from unittest.mock import MagicMock


def _session(uid=None):
    s = MagicMock()
    s.user_id = uid
    return s


def _ctx():
    c = MagicMock()
    c.online = MagicMock()
    c.online.is_online.return_value = False
    c.online.online_ids.return_value = []
    c.db.users.get_by_username.return_value = None
    c.db.users.exists.return_value = False
    c.db.users.insert_user.return_value = 42
    c.db.users.get_all_users.return_value = []
    return c


def _bind(s, c):
    s.ctx = c


def _make_user_row(uid=1, username="testuser", password="test123",
                   hash_len=64, salt="abcdef1234567890abcdef1234567890"):
    """创建模拟用户数据库行

    Args:
        hash_len: 64=SHA256, 32=MD5（预置账号格式）
    """
    if hash_len == 64:
        pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    else:
        pwd_hash = hashlib.md5(password.encode()).hexdigest()
    return {
        "user_id": uid,
        "username": username,
        "password_hash": pwd_hash,
        "salt": salt,
        "nickname": username,
        "is_ai_bot": 0,
    }


# ═══════════════════════════════════════════
# _verify_password
# ═══════════════════════════════════════════

class TestVerifyPassword(unittest.TestCase):
    """测试 _verify_password 密码校验函数"""

    @classmethod
    def setUpClass(cls):
        from server.modules import user as m
        cls.m = m

    # ── 1. 正常流程 ──

    def test_sha256_correct(self):
        """SHA256 格式：正确密码返回 True"""
        row = _make_user_row(hash_len=64)
        self.assertTrue(self.m._verify_password("test123", row["password_hash"], row["salt"]))

    def test_md5_correct(self):
        """MD5 格式：正确密码返回 True（兼容预置账号）"""
        row = _make_user_row(hash_len=32)
        self.assertTrue(self.m._verify_password("test123", row["password_hash"], row["salt"]))

    # ── 2. 异常流程 ──

    def test_sha256_wrong(self):
        """SHA256 格式：错误密码返回 False"""
        row = _make_user_row(hash_len=64)
        self.assertFalse(self.m._verify_password("wrongpass", row["password_hash"], row["salt"]))

    def test_md5_wrong(self):
        """MD5 格式：错误密码返回 False"""
        row = _make_user_row(hash_len=32)
        self.assertFalse(self.m._verify_password("wrongpass", row["password_hash"], row["salt"]))

    # ── 3. 空值处理 ──

    def test_sha256_empty_password(self):
        """SHA256 格式：空密码返回 False"""
        row = _make_user_row(hash_len=64, password="realpwd")
        self.assertFalse(self.m._verify_password("", row["password_hash"], row["salt"]))

    def test_md5_empty_password(self):
        """MD5 格式：空密码返回 False"""
        row = _make_user_row(hash_len=32, password="realpwd")
        self.assertFalse(self.m._verify_password("", row["password_hash"], row["salt"]))


# ═══════════════════════════════════════════
# handle_login
# ═══════════════════════════════════════════

class TestHandleLogin(unittest.TestCase):
    """测试 handle_login 登录处理函数"""

    @classmethod
    def setUpClass(cls):
        from server.modules import user as m
        cls.m = m

    # ── 1. 正常流程 ──

    def test_login_success_sha256(self):
        """SHA256 正确密码登录 → ok=True，绑定用户、加入在线表、广播上线"""
        s, c = _session(), _ctx()
        row = _make_user_row(uid=5, username="alice", password="pass456", hash_len=64)
        c.db.users.get_by_username.return_value = row
        c.online.online_ids.return_value = [5]
        _bind(s, c)
        self.m.handle_login(s, {"username": "alice", "password": "pass456"})

        resp = s.send.call_args[0][0]
        self.assertEqual(resp["type"], "login_resp")
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["user_id"], 5)
        self.assertIn("online_users", resp)
        s.bind_user.assert_called_once_with(5, "alice")
        c.online.add.assert_called_once()
        c.online.broadcast.assert_called_once()

    def test_login_success_md5_compat(self):
        """MD5 预置账号登录 → ok=True（兼容 init.sql 格式）"""
        s, c = _session(), _ctx()
        row = _make_user_row(uid=10, username="test1", password="test1", hash_len=32)
        c.db.users.get_by_username.return_value = row
        _bind(s, c)
        self.m.handle_login(s, {"username": "test1", "password": "test1"})
        self.assertTrue(s.send.call_args[0][0]["ok"])

    # ── 2. 异常流程 ──

    def test_user_not_found(self):
        """用户不存在 → ok=False, reason="用户不存在" """
        s, c = _session(), _ctx()
        c.db.users.get_by_username.return_value = None
        _bind(s, c)
        self.m.handle_login(s, {"username": "nobody", "password": "pwd"})
        resp = s.send.call_args[0][0]
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["reason"], "用户不存在")

    def test_wrong_password(self):
        """密码错误 → ok=False, reason="密码错误" """
        s, c = _session(), _ctx()
        row = _make_user_row(hash_len=64, password="correctpwd")
        c.db.users.get_by_username.return_value = row
        _bind(s, c)
        self.m.handle_login(s, {"username": "testuser", "password": "wrongpwd"})
        resp = s.send.call_args[0][0]
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["reason"], "密码错误")

    def test_already_online(self):
        """用户已在线 → ok=False, reason="用户已在线" """
        s, c = _session(), _ctx()
        row = _make_user_row(hash_len=64, password="test123")
        c.db.users.get_by_username.return_value = row
        c.online.is_online.return_value = True
        _bind(s, c)
        self.m.handle_login(s, {"username": "testuser", "password": "test123"})
        resp = s.send.call_args[0][0]
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["reason"], "用户已在线")

    # ── 3. 空值处理 ──

    def test_login_empty_username(self):
        """用户名为空 → 查不到用户 → ok=False"""
        s, c = _session(), _ctx()
        c.db.users.get_by_username.return_value = None
        _bind(s, c)
        self.m.handle_login(s, {"username": "", "password": "pwd"})
        self.assertFalse(s.send.call_args[0][0]["ok"])

    def test_login_empty_password(self):
        """密码为空 → 校验失败 → ok=False"""
        s, c = _session(), _ctx()
        row = _make_user_row(hash_len=64, password="realpwd")
        c.db.users.get_by_username.return_value = row
        _bind(s, c)
        self.m.handle_login(s, {"username": "testuser", "password": ""})
        self.assertFalse(s.send.call_args[0][0]["ok"])


# ═══════════════════════════════════════════
# handle_register
# ═══════════════════════════════════════════

class TestHandleRegister(unittest.TestCase):
    """测试 handle_register 注册处理函数"""

    @classmethod
    def setUpClass(cls):
        from server.modules import user as m
        cls.m = m

    # ── 1. 正常流程 ──

    def test_register_success(self):
        """正常注册 → ok=True, insert_user 被正确调用"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_register(s, {"username": "newuser", "password": "mypassword"})

        resp = s.send.call_args[0][0]
        self.assertTrue(resp["ok"])
        c.db.users.insert_user.assert_called_once()
        args = c.db.users.insert_user.call_args[0]
        self.assertEqual(args[0], "newuser")  # username
        self.assertEqual(len(args[1]), 64)     # SHA256 hash = 64 hex chars
        self.assertEqual(len(args[2]), 32)     # 16 bytes salt → 32 hex chars

    # ── 2. 异常流程 ──

    def test_register_username_exists(self):
        """用户名已存在 → ok=False, reason="用户名已存在" """
        s, c = _session(), _ctx()
        c.db.users.exists.return_value = True
        _bind(s, c)
        self.m.handle_register(s, {"username": "existing", "password": "test123"})
        resp = s.send.call_args[0][0]
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["reason"], "用户名已存在")

    # ── 3. 空值处理 ──

    def test_register_empty_username(self):
        """用户名为空（含空格）→ ok=False"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_register(s, {"username": "  ", "password": "test123"})
        self.assertFalse(s.send.call_args[0][0]["ok"])

    def test_register_empty_password(self):
        """密码为空 → ok=False"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_register(s, {"username": "newuser", "password": ""})
        self.assertFalse(s.send.call_args[0][0]["ok"])

    # ── 6. 集成往返 ──

    def test_register_then_login(self):
        """注册后的账号可以用同一密码成功登录（注册→登录往返）"""
        s_reg, c = _session(), _ctx()
        _bind(s_reg, c)
        self.m.handle_register(s_reg, {"username": "roundtrip", "password": "secret123"})

        # 提取 insert_user 写入的参数
        args = c.db.users.insert_user.call_args[0]
        saved_hash, saved_salt = args[1], args[2]

        # 模拟登录：get_by_username 返回刚注册的数据
        s_login = _session()
        c.db.users.get_by_username.return_value = {
            "user_id": 99, "username": "roundtrip",
            "password_hash": saved_hash, "salt": saved_salt,
            "nickname": "roundtrip", "is_ai_bot": 0,
        }
        _bind(s_login, c)
        self.m.handle_login(s_login, {"username": "roundtrip", "password": "secret123"})
        self.assertTrue(s_login.send.call_args[0][0]["ok"])
        self.assertEqual(s_login.send.call_args[0][0]["user_id"], 99)


# ═══════════════════════════════════════════
# on_disconnect
# ═══════════════════════════════════════════

class TestOnDisconnect(unittest.TestCase):
    """测试 on_disconnect 断开清理函数"""

    @classmethod
    def setUpClass(cls):
        from server.modules import user as m
        cls.m = m

    def test_disconnect_with_user(self):
        """已登录用户断开 → 广播 USER_LIST 更新下线列表"""
        s, c = _session(), _ctx()
        c.online.online_ids.return_value = []
        _bind(s, c)
        s.user_id = 5
        self.m.on_disconnect(s)
        c.online.broadcast.assert_called_once()
        payload = c.online.broadcast.call_args[0][0]
        self.assertEqual(payload["type"], "user_list")

    def test_disconnect_no_user(self):
        """未登录用户断开 → 不广播"""
        s, c = _session(), _ctx()
        _bind(s, c)
        s.user_id = None
        self.m.on_disconnect(s)
        c.online.broadcast.assert_not_called()


# ═══════════════════════════════════════════
# _snapshot
# ═══════════════════════════════════════════

class TestSnapshot(unittest.TestCase):
    """测试 _snapshot 和 _all_users_snapshot"""

    @classmethod
    def setUpClass(cls):
        from server.modules import user as m
        cls.m = m

    def test_snapshot_empty(self):
        """在线表为空 → 返回空列表"""
        c = _ctx()
        c.online.online_ids.return_value = []
        self.assertEqual(self.m._snapshot(c), [])

    def test_snapshot_with_users(self):
        """在线表有用户 → 返回正确的用户列表"""
        c = _ctx()
        c.online.online_ids.return_value = [1, 2]

        def get_by_id(uid):
            return {"user_id": uid, "username": f"user{uid}", "nickname": f"User{uid}"}
        c.db.users.get_by_id.side_effect = get_by_id

        result = self.m._snapshot(c)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["user_id"], 1)
        self.assertEqual(result[1]["username"], "user2")

    def test_all_users_snapshot(self):
        """获取所有用户列表"""
        c = _ctx()
        c.db.users.get_all_users.return_value = [
            {"user_id": 1, "username": "alice", "nickname": "Alice"},
            {"user_id": 2, "username": "bob", "nickname": "Bob"},
        ]
        result = self.m._all_users_snapshot(c)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["username"], "alice")


if __name__ == "__main__":
    unittest.main()
