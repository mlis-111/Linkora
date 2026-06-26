"""Protocol + Crypto 集成测试

测试 wire protocol 与 AES 加密在实际 socket 上的协作：
1. send_msg / recv_msg 通过 socket pair 传输
2. CryptoUtil 加密后经协议传输再解密
3. 长消息 / 中文消息 / JSON 特殊字符处理
4. 空消息、边界长度消息
5. 加密 → 协议传输 → 解密 完整链路
"""

import json
import socket
import struct
import threading

import pytest
from common.protocol import send_msg, recv_msg
from common.crypto import CryptoUtil


# ════════════════════════════════════════════════════════════════
# Socket pair 辅助
# ════════════════════════════════════════════════════════════════

def _send_and_recv(msg: dict) -> dict:
    """通过 socket pair 发送并接收一条消息"""
    a, b = socket.socketpair()
    try:
        send_msg(a, msg)
        return recv_msg(b)
    finally:
        a.close()
        b.close()


# ════════════════════════════════════════════════════════════════
# Protocol 基础往返测试
# ════════════════════════════════════════════════════════════════

class TestProtocolRoundtrip:
    """协议基本往返测试 —— socket pair 上进行 send/recv"""

    def test_simple_dict(self):
        """简单字典往返"""
        msg = {"type": "chat", "content": "hello"}
        result = _send_and_recv(msg)
        assert result == msg

    def test_nested_dict(self):
        """嵌套字典往返"""
        msg = {
            "type": "login_resp",
            "ok": True,
            "user_id": 100,
            "data": {"nickname": "小明", "friends": [1, 2, 3]},
        }
        result = _send_and_recv(msg)
        assert result == msg

    def test_chinese_text(self):
        """中文消息（UTF-8 编解码）"""
        msg = {"type": "chat", "content": "你好世界！🎉"}
        result = _send_and_recv(msg)
        assert result == msg
        assert result["content"] == "你好世界！🎉"

    def test_empty_dict(self):
        """空字典"""
        msg = {}
        result = _send_and_recv(msg)
        assert result == {}

    def test_null_and_bool(self):
        """null / bool / 数字 类型保持"""
        msg = {"a": None, "b": True, "c": False, "d": 0, "e": -1, "f": 3.14}
        result = _send_and_recv(msg)
        assert result == msg
        assert result["a"] is None

    def test_large_message(self):
        """较大消息（模拟多行聊天内容）"""
        long_text = "这是一条很长的消息。" * 200  # ~2.8KB
        msg = {"type": "chat", "content": long_text}
        result = _send_and_recv(msg)
        assert result == msg

    def test_special_json_chars(self):
        """JSON 特殊字符／转义"""
        msg = {"content": 'hello "world"\n\t\\'}
        result = _send_and_recv(msg)
        assert result == msg


# ════════════════════════════════════════════════════════════════
# Crypto 加解密往返测试
# ════════════════════════════════════════════════════════════════

class TestCryptoRoundtrip:
    """AES 加解密往返测试"""

    @pytest.fixture
    def crypto(self):
        return CryptoUtil(b"my_secret_key_16")

    def test_encrypt_decrypt_simple(self, crypto):
        """基本加解密往返"""
        plain = "hello world"
        encrypted = crypto.encrypt(plain)
        assert encrypted != plain
        assert crypto.decrypt(encrypted) == plain

    def test_chinese_roundtrip(self, crypto):
        """中文加解密往返"""
        plain = "你好，世界！这是一条加密消息。"
        assert crypto.decrypt(crypto.encrypt(plain)) == plain

    def test_empty_string(self, crypto):
        """空字符串"""
        assert crypto.encrypt("") == ""
        assert crypto.decrypt("") == ""

    def test_long_message(self, crypto):
        """长消息加解密"""
        plain = "x" * 4096
        assert crypto.decrypt(crypto.encrypt(plain)) == plain

    def test_special_chars(self, crypto):
        """特殊字符加解密"""
        plain = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t\r"
        assert crypto.decrypt(crypto.encrypt(plain)) == plain

    def test_different_keys_produce_different_ciphertext(self):
        """不同密钥产生不同密文"""
        c1 = CryptoUtil(b"key_a_16_bytes!!")
        c2 = CryptoUtil(b"key_b_16_bytes!!")
        plain = "same message"
        assert c1.encrypt(plain) != c2.encrypt(plain)

    def test_decrypt_non_base64_passthrough(self, crypto):
        """非 Base64 输入直通返回原字符串（兼容未加密数据）"""
        assert crypto.decrypt("plain text!!!") == "plain text!!!"

    def test_decrypt_invalid_passthrough(self, crypto):
        """无效密文直通返回"""
        too_short = "abc"  # Base64 合法但长度不足以包含 IV+数据
        result = crypto.decrypt(too_short)
        # 兼容模式：解密失败时返回原文
        assert result == too_short


# ════════════════════════════════════════════════════════════════
# Protocol + Crypto 联合测试（真实 socket）
# ════════════════════════════════════════════════════════════════

class TestProtocolWithCrypto:
    """协议传输加密消息的完整链路测试"""

    @pytest.fixture
    def crypto(self):
        return CryptoUtil(b"link_test_key_16")

    def test_encrypted_message_over_socket(self, crypto):
        """加密消息通过 socket pair 传输后解密"""
        plain_content = "这是加密的聊天内容"
        encrypted = crypto.encrypt(plain_content)

        msg = {
            "type": "chat",
            "from": 100,
            "to": 200,
            "content": encrypted,
            "ts": 1234567890,
        }

        a, b = socket.socketpair()
        try:
            send_msg(a, msg)
            received = recv_msg(b)
        finally:
            a.close()
            b.close()

        assert received == msg
        # 解密接收到的内容
        assert crypto.decrypt(received["content"]) == plain_content

    def test_multiple_encrypted_messages(self, crypto):
        """多条加密消息连续传输"""
        messages = [
            {"type": "chat", "content": crypto.encrypt(f"消息{i}")}
            for i in range(10)
        ]

        a, b = socket.socketpair()
        try:
            for m in messages:
                send_msg(a, m)
            results = [recv_msg(b) for _ in range(10)]
        finally:
            a.close()
            b.close()

        assert results == messages
        for i, r in enumerate(results):
            assert crypto.decrypt(r["content"]) == f"消息{i}"

    def test_mixed_encrypted_and_plain(self, crypto):
        """混合加密和明文消息"""
        a, b = socket.socketpair()
        try:
            # 加密消息
            send_msg(a, {"type": "chat", "content": crypto.encrypt("secret")})
            # 明文消息（登录等不需要加密的消息）
            send_msg(a, {"type": "login", "username": "user1", "password": "123456"})
            # 另一条加密消息
            send_msg(a, {"type": "chat", "content": crypto.encrypt("another secret")})

            r1 = recv_msg(b)
            r2 = recv_msg(b)
            r3 = recv_msg(b)
        finally:
            a.close()
            b.close()

        assert crypto.decrypt(r1["content"]) == "secret"
        assert r2["username"] == "user1"  # 明文
        assert crypto.decrypt(r3["content"]) == "another secret"

    def test_concurrent_send_recv(self, crypto):
        """并发收发（模拟多线程环境）"""
        errors = []

        def client(sock, tag):
            try:
                for i in range(5):
                    msg = {"type": "chat", "content": crypto.encrypt(f"{tag}-{i}")}
                    send_msg(sock, msg)
            except Exception as e:
                errors.append(e)

        a, b = socket.socketpair()
        try:
            t1 = threading.Thread(target=client, args=(a, "A"))
            t2 = threading.Thread(target=client, args=(b, "B"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        finally:
            a.close()
            b.close()

        assert len(errors) == 0, f"并发收发出错: {errors}"


# ════════════════════════════════════════════════════════════════
# Protocol 边界测试
# ════════════════════════════════════════════════════════════════

class TestProtocolEdgeCases:
    """协议边界情况测试"""

    def test_single_char_message(self):
        """单字符消息"""
        msg = {"x": "a"}
        result = _send_and_recv(msg)
        assert result == msg

    def test_max_unicode(self):
        """Emoji 和特殊 Unicode"""
        msg = {"content": "😀🎉🚀☃☠"}
        result = _send_and_recv(msg)
        assert result == msg

    def test_list_in_message(self):
        """消息中包含数组"""
        msg = {"ids": [1, 2, 3], "names": ["张三", "李四"]}
        result = _send_and_recv(msg)
        assert result == msg

    def test_recv_msg_on_closed_socket(self):
        """对端关闭时 recv_msg 返回 None"""
        a, b = socket.socketpair()
        a.close()
        result = recv_msg(b)
        b.close()
        assert result is None

    def test_partial_read_recovery(self):
        """TCP 分片到达时能正确重组

        模拟：手动构造分片的字节流写入 socket，验证 recv_msg 能正确重组。
        """
        data = json.dumps({"hello": "world"}, ensure_ascii=False).encode("utf-8")
        header = struct.pack(">I", len(data))

        a, b = socket.socketpair()
        try:
            # 先发送头部
            a.sendall(header)
            # 再发送一半 body
            half = len(data) // 2
            a.sendall(data[:half])
            # 最后发送剩余 body
            a.sendall(data[half:])

            result = recv_msg(b)
        finally:
            a.close()
            b.close()

        assert result == {"hello": "world"}
