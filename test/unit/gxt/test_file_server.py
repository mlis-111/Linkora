"""
server/modules/file.py  单元测试（六种覆盖）

Author: gxt

覆盖类型说明：
  1. 语句覆盖 —— 每一行可执行语句至少执行一次
  2. 判定覆盖 —— 每个 if 的真/假分支各执行一次
  3. 条件覆盖 —— 每个布尔子表达式取真/假各一次
  4. 判定-条件覆盖 —— 判定覆盖 + 条件覆盖同时满足
  5. 条件组合覆盖 —— 多条件时所有组合都覆盖
  6. 路径覆盖 —— 所有可能的执行路径都覆盖

每个测试用例标注了覆盖类型 [C1]~[C6]
"""
import unittest
from unittest.mock import MagicMock


# ── 辅助函数 ────────────────────────────────────────────

def _session(user_id=1, username="test1"):
    s = MagicMock()
    s.user_id = user_id
    s.username = username
    return s


def _ctx(*, online=True, send_ok=True, insert_id=100):
    ctx = MagicMock()
    ctx.online.is_online.return_value = online
    ctx.online.send.return_value = send_ok
    ctx.db.files.insert.return_value = insert_id
    return ctx


def _bind(session, ctx):
    session.ctx = ctx


# ═══════════════════════════════════════════════════════════
# handle_file_req  判定点：target_id?  /  is_online?
#                   路径数：3
# ═══════════════════════════════════════════════════════════
class TestHandleFileReq(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    # ── 路径1：target_id 为 None → BAD_REQUEST ──────────
    def test_path1_target_none(self):
        """[C1][C2][C3][C4] target_id=None → BAD_REQUEST
        覆盖：target_id is None == True"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_file_req(s, {})
        err = s.send.call_args[0][0]
        self.assertEqual(err["code"], "BAD_REQUEST")

    # ── 路径2：target_id 存在 + 目标离线 → OFFLINE ──────
    def test_path2_target_offline(self):
        """[C1][C2][C3][C4] 目标不在线 → OFFLINE
        覆盖：target_id is None == False 且 is_online() == False"""
        s, c = _session(), _ctx(online=False)
        _bind(s, c)
        self.m.handle_file_req(s, {"to": 99})
        err = s.send.call_args[0][0]
        self.assertEqual(err["code"], "OFFLINE")
        # 离线时不应尝试新建 DB 记录或转发
        c.db.files.insert.assert_not_called()
        c.online.send.assert_not_called()

    # ── 路径3：正常 → 创建记录 + 转发 ───────────────────
    def test_path3_normal(self):
        """[C1][C2][C3][C4][C5][C6] 完整正常路径
        覆盖：target_id is None == False 且 is_online() == True
        file_id 回填 + from 回填 + 转发"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"to": 2, "file_name": "t.zip", "file_size": 65536}
        self.m.handle_file_req(s, msg)

        c.db.files.insert.assert_called_once_with(1, 2, "t.zip", 65536)
        self.assertEqual(msg["file_id"], 100)
        self.assertEqual(msg["from"], 1)
        c.online.send.assert_called_with(2, msg)

    # ── 条件组合：target_id=None 短路，不检查 is_online ──
    def test_short_circuit(self):
        """[C5] target_id=None 时不调用 is_online（短路）
        条件组合：(target_id=None, is_online 未被调用)"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_file_req(s, {})
        c.online.is_online.assert_not_called()


# ═══════════════════════════════════════════════════════════
# handle_file_resp  判定点：target_id?  /  send 成功?
#                   路径数：3
# ═══════════════════════════════════════════════════════════
class TestHandleFileResp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    def test_path1_target_none(self):
        """[C1][C2] target_id=None → BAD_REQUEST"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_file_resp(s, {})
        self.assertEqual(s.send.call_args[0][0]["code"], "BAD_REQUEST")

    def test_path2_normal_send_ok(self):
        """[C1][C2][C3] target 存在 + send 成功 → 静默完成
        覆盖：target_id is None == False 且 send() == True"""
        s, c = _session(user_id=2), _ctx(send_ok=True)
        _bind(s, c)
        msg = {"to": 1, "file_id": 100, "accept": True}
        self.m.handle_file_resp(s, msg)
        self.assertEqual(msg["from"], 2)
        c.online.send.assert_called_with(1, msg)
        # send 成功时不应再调用 session.send(error)
        s.send.assert_not_called()

    def test_path3_send_fail(self):
        """[C1][C2][C3] target 存在 + send 失败 → OFFLINE
        覆盖：target_id is None == False 且 send() == False"""
        s, c = _session(user_id=2), _ctx(send_ok=False)
        _bind(s, c)
        msg = {"to": 1, "file_id": 100, "accept": False}
        self.m.handle_file_resp(s, msg)
        err = s.send.call_args[0][0]
        self.assertEqual(err["code"], "OFFLINE")


# ═══════════════════════════════════════════════════════════
# handle_file_data  判定点：target_id?  /  send 成功?
#                   路径数：3（结构同 handle_file_resp）
# ═══════════════════════════════════════════════════════════
class TestHandleFileData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    def test_path1_target_none(self):
        """[C1][C2] target_id=None → BAD_REQUEST"""
        s, c = _session(), _ctx()
        _bind(s, c)
        self.m.handle_file_data(s, {})
        self.assertEqual(s.send.call_args[0][0]["code"], "BAD_REQUEST")

    def test_path2_normal(self):
        """[C2][C3][C6] 正常转发数据块"""
        s, c = _session(), _ctx(send_ok=True)
        _bind(s, c)
        msg = {"to": 2, "file_id": 100, "seq": 0, "data": "AAAA"}
        self.m.handle_file_data(s, msg)
        self.assertEqual(msg["from"], 1)
        c.online.send.assert_called_with(2, msg)
        s.send.assert_not_called()

    def test_path3_send_fail(self):
        """[C2][C3] send 失败 → OFFLINE"""
        s, c = _session(), _ctx(send_ok=False)
        _bind(s, c)
        msg = {"to": 2, "file_id": 100, "seq": 1, "data": "BBBB"}
        self.m.handle_file_data(s, msg)
        self.assertEqual(s.send.call_args[0][0]["code"], "OFFLINE")


# ═══════════════════════════════════════════════════════════
# handle_file_end  判定点：file_id?  /  status==1 or 2?  /  target_id?
#                   条件组合：file_id is (not) None × status(1,2,其他) × target_id is (not) None
#                   路径数：5
# ═══════════════════════════════════════════════════════════
class TestHandleFileEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    # ── 路径1：file_id✓ + status=1 + target✓ → update done + forward ──
    def test_path1_success_with_target(self):
        """[C1][C2][C4][C6] status=1, file_id 和 target 都存在
        条件组合：file_id not None=True, status==1=True, target not None=True"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"to": 2, "file_id": 100, "status": 1}
        self.m.handle_file_end(s, msg)
        c.db.files.update_status.assert_called_once_with(100, 1, done=True)
        c.online.send.assert_called_with(2, msg)

    # ── 路径2：file_id✓ + status=2 + target✓ → update done + forward ──
    def test_path2_failure_with_target(self):
        """[C2][C3][C5] status=2, file_id 和 target 都存在
        条件组合：file_id not None=True, status==2=True, target not None=True
        条件覆盖：status==1 为 False, status==2 为 True"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"to": 2, "file_id": 100, "status": 2}
        self.m.handle_file_end(s, msg)
        c.db.files.update_status.assert_called_once_with(100, 2, done=True)
        c.online.send.assert_called_with(2, msg)

    # ── 路径3：file_id=None + target✓ → 不更新 DB，只转发 ──
    def test_path3_no_file_id_with_target(self):
        """[C2][C3][C6] file_id 为空但有 target
        条件覆盖：file_id is not None == False
        条件组合：file_id=None, target not None=True"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"to": 2, "status": 1}
        self.m.handle_file_end(s, msg)
        c.db.files.update_status.assert_not_called()
        c.online.send.assert_called_with(2, msg)

    # ── 路径4：file_id✓ + target=None → 只更新 DB，不转发 ──
    def test_path4_with_file_id_no_target(self):
        """[C2][C3][C6] file_id 存在但无 target
        条件覆盖：target_id is not None == False
        条件组合：file_id not None=True, target_id=None"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"file_id": 100, "status": 1}
        self.m.handle_file_end(s, msg)
        c.db.files.update_status.assert_called_once_with(100, 1, done=True)
        c.online.send.assert_not_called()

    # ── 路径5：file_id=None + target=None → 什么都不做 ──
    def test_path5_both_none(self):
        """[C2][C5][C6] file_id 和 target 都为空
        条件组合：file_id=None, target_id=None → 两个 if 都跳过"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"status": 1}
        self.m.handle_file_end(s, msg)
        c.db.files.update_status.assert_not_called()
        c.online.send.assert_not_called()

    # ── done 判定：status=1 or 2 → done；status=3 → not done ──
    def test_done_when_status_3(self):
        """[C3][C5] status=3 时 done=False
        条件覆盖：status==1=False, status==2=False → done=False"""
        s, c = _session(), _ctx()
        _bind(s, c)
        msg = {"to": 2, "file_id": 100, "status": 3}
        self.m.handle_file_end(s, msg)
        c.db.files.update_status.assert_called_once_with(100, 3, done=False)


# ═══════════════════════════════════════════════════════════
# register —— 语句覆盖 + 判定覆盖
# ═══════════════════════════════════════════════════════════
class TestRegister(unittest.TestCase):

    def test_registers_four_types(self):
        """[C1][C2] register 注册 4 个消息类型，无遗漏"""
        from server.modules import file as m
        router, ctx = MagicMock(), MagicMock()
        m.register(router, ctx)
        self.assertEqual(router.register.call_count, 4)
        types = {c[0][0] for c in router.register.call_args_list}
        self.assertEqual(types, {"file_req", "file_resp", "file_data", "file_end"})


# ═══════════════════════════════════════════════════════════
# 覆盖率汇总
# ═══════════════════════════════════════════════════════════
#
#  C1 语句覆盖    ✅ 所有 4 个 handler 的每行语句（含 register）都被执行
#  C2 判定覆盖    ✅ 每个 if 的真/假分支均覆盖
#                     target_id is None        → True (path1), False (path2/3)
#                     is_online() == False     → True (path2), False (path3)
#                     send() == False          → True (path3), False (path2)
#                     file_id is not None      → True, False
#                     target_id is not None    → True, False
#  C3 条件覆盖    ✅ status==1: True/False; status==2: True/False
#  C4 判定-条件   ✅ 每个判定的条件在判定为真/假时各取一次（见各路径标注）
#  C5 条件组合    ✅ file_id(有/无) × target_id(有/无) 全部 4 种组合
#                     status(1/2/3) × file_id × target → 关键组合
#  C6 路径覆盖    ✅ 5 条独立执行路径全覆盖
#
#  测试用例数：17    全部通过 ✅
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
