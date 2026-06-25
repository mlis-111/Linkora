"""
server/modules/file.py 单元测试 —— 缓冲中转版
Author: gxt
"""
import unittest, tempfile, os, base64
from unittest.mock import MagicMock


def _session(uid=1):
    s = MagicMock()
    s.user_id = uid
    return s


def _ctx():
    c = MagicMock()
    c.online.is_online.return_value = True
    c.online.send.return_value = True
    c.db.files.insert.return_value = 100
    return c


def _bind(s, c):
    s.ctx = c


def _buf(file_id=100):
    from server.modules import file as m
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".buf")
    m._file_buffers[file_id] = {
        "fh": tmp, "path": tmp.name,
        "from_id": 1, "to_id": 2,
        "file_name": "t.zip", "file_size": 100,
        "done": False,
    }
    return m._file_buffers[file_id]


class TestHandleFileReq(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    def setUp(self):
        self.m._file_buffers.clear()

    def test_target_none(self):
        s, c = _session(), _ctx(); _bind(s, c)
        self.m.handle_file_req(s, {})
        self.assertEqual(s.send.call_args[0][0]["code"], "BAD_REQUEST")

    def test_target_offline(self):
        s, c = _session(), _ctx()
        c.online.is_online.return_value = False; _bind(s, c)
        self.m.handle_file_req(s, {"to": 99})
        self.assertEqual(s.send.call_args[0][0]["code"], "OFFLINE")

    def test_normal(self):
        s, c = _session(), _ctx(); _bind(s, c)
        self.m.handle_file_req(s, {"to": 2, "file_name": "t.zip",
                                   "file_size": 100})
        c.db.files.insert.assert_called_once()
        ack = s.send.call_args[0][0]
        self.assertEqual(ack["type"], "file_req_ack")
        self.assertEqual(ack["file_id"], 100)
        self.assertIn(100, self.m._file_buffers)
        self.m._file_buffers[100]["fh"].close()
        os.unlink(self.m._file_buffers[100]["path"])


class TestHandleFileData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    def setUp(self):
        self.m._file_buffers.clear()

    def test_no_buffer(self):
        s, c = _session(), _ctx(); _bind(s, c)
        self.m.handle_file_data(s, {"file_id": 999, "data": "AAAA"})

    def test_writes(self):
        s, c = _session(), _ctx(); _bind(s, c)
        buf = _buf(100)
        data = b"hello"
        self.m.handle_file_data(s, {"file_id": 100,
                                    "data": base64.b64encode(data).decode()})
        buf["fh"].close()
        with open(buf["path"], "rb") as f:
            self.assertEqual(f.read(), data)
        os.unlink(buf["path"])


class TestHandleFileEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    def setUp(self):
        self.m._file_buffers.clear()

    def test_no_buffer(self):
        s, c = _session(), _ctx(); _bind(s, c)
        self.m.handle_file_end(s, {"file_id": 999})

    def test_normal(self):
        s, c = _session(), _ctx(); _bind(s, c)
        buf = _buf(100)
        buf["fh"].write(b"t"); buf["fh"].close()
        self.m.handle_file_end(s, {"file_id": 100, "status": 1})
        c.db.files.update_status.assert_called()
        c.online.send.assert_called()
        os.unlink(buf["path"])


class TestHandleFileResp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.modules import file as m
        cls.m = m

    def setUp(self):
        self.m._file_buffers.clear()

    def test_no_buffer(self):
        s, c = _session(2), _ctx(); _bind(s, c)
        self.m.handle_file_resp(s, {"file_id": 999, "accept": True})

    def test_accept(self):
        s, c = _session(2), _ctx(); _bind(s, c)
        buf = _buf(100)
        buf["fh"].write(b"data"); buf["fh"].close(); buf["done"] = True
        self.m.handle_file_resp(s, {"file_id": 100, "accept": True})
        self.assertNotIn(100, self.m._file_buffers)
        # 应通知发送方已接受
        c.online.send.assert_any_call(1, {
            "type": "file_status", "file_id": 100, "status": "accepted"})

    def test_reject(self):
        s, c = _session(2), _ctx(); _bind(s, c)
        buf = _buf(100)
        buf["fh"].write(b"x"); buf["fh"].close()
        self.m.handle_file_resp(s, {"file_id": 100, "accept": False})
        c.db.files.update_status.assert_called_with(100, 2, done=True)
        self.assertNotIn(100, self.m._file_buffers)
        # 应通知发送方已拒绝
        c.online.send.assert_any_call(1, {
            "type": "file_status", "file_id": 100, "status": "rejected"})


class TestRegister(unittest.TestCase):
    def test_four_types(self):
        from server.modules import file as m
        r, c = MagicMock(), MagicMock()
        m.register(r, c)
        self.assertEqual(r.register.call_count, 4)


if __name__ == "__main__":
    unittest.main()
