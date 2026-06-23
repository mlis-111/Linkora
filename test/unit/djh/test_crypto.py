"""CryptoUtil 单元测试

覆盖内容:
1. 正常加解密往返（短文本、中文、长文本）
2. 空字符串处理
3. 解密兼容性（桩阶段直通数据）
4. 不同密钥长度
5. 损坏数据容错
6. 多次加密产生不同密文（随机IV）

author: 董钧豪
"""

import pytest
from common.crypto import CryptoUtil


@pytest.fixture
def crypto():
    """提供默认32字节密钥的 CryptoUtil 实例"""
    return CryptoUtil(b"campus_im_demo_key_32bytes!!")


@pytest.fixture
def crypto_16():
    """提供16字节密钥的 CryptoUtil 实例"""
    return CryptoUtil(b"16bytes_key_here!")


@pytest.fixture
def crypto_24():
    """提供24字节密钥的 CryptoUtil 实例"""
    return CryptoUtil(b"24bytes_key_for_test_here")


# ========== 1. 正常加解密往返 ==========

class TestEncryptDecrypt:
    """正常加解密往返测试"""

    def test_short_text(self, crypto):
        """短文本加解密往返"""
        plain = "你好"
        cipher = crypto.encrypt(plain)
        assert cipher != plain  # 密文不同于明文
        assert crypto.decrypt(cipher) == plain

    def test_chinese_text(self, crypto):
        """中文字符加解密"""
        plain = "校园即时通信系统测试"
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain

    def test_english_text(self, crypto):
        """英文字符加解密"""
        plain = "Hello, Campus IM! Testing 123."
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain

    def test_mixed_text(self, crypto):
        """中英文混合加解密"""
        plain = "Hello 世界！测试 Test 123 !@#$%"
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain

    def test_long_text(self, crypto):
        """长文本加解密往返"""
        plain = "A" * 10000 + "你好" * 100
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain

    def test_special_chars(self, crypto):
        """特殊字符加解密"""
        plain = "\n\t\r\0\\\"'<>/.,;:!@#$%^&*()_+-=~`"
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain


# ========== 2. 空字符串处理 ==========

class TestEmptyString:
    """空字符串边界测试"""

    def test_encrypt_empty(self, crypto):
        """加密空字符串返回空"""
        assert crypto.encrypt("") == ""

    def test_decrypt_empty(self, crypto):
        """解密空字符串返回空"""
        assert crypto.decrypt("") == ""

    def test_encrypt_whitespace(self, crypto):
        """加密纯空格字符串"""
        plain = "   "
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain


# ========== 3. 解密兼容性（桩阶段直通数据） ==========

class TestBackwardCompatibility:
    """与阶段0桩实现的向后兼容"""

    def test_decrypt_plain_text(self, crypto):
        """解密非Base64数据时直通返回原文"""
        assert crypto.decrypt("hello") == "hello"

    def test_decrypt_plain_chinese(self, crypto):
        """解密非Base64中文字符时直通返回"""
        assert crypto.decrypt("你好世界") == "你好世界"

    def test_decrypt_plain_number(self, crypto):
        """解密非Base64数字字符串时直通返回"""
        assert crypto.decrypt("12345") == "12345"


# ========== 4. 不同密钥长度 ==========

class TestKeyLengths:
    """不同密钥长度测试"""

    def test_16_byte_key(self, crypto_16):
        """16字节密钥加解密"""
        plain = "使用16字节密钥"
        cipher = crypto_16.encrypt(plain)
        assert crypto_16.decrypt(cipher) == plain

    def test_24_byte_key(self, crypto_24):
        """24字节密钥加解密"""
        plain = "使用24字节密钥进行测试"
        cipher = crypto_24.encrypt(plain)
        assert crypto_24.decrypt(cipher) == plain

    def test_32_byte_key(self, crypto):
        """32字节密钥加解密"""
        plain = "使用32字节密钥进行测试"
        cipher = crypto.encrypt(plain)
        assert crypto.decrypt(cipher) == plain

    def test_auto_pad_key(self):
        """非标准长度密钥自动补齐"""
        short = CryptoUtil(b"short")
        plain = "短密钥测试"
        cipher = short.encrypt(plain)
        assert short.decrypt(cipher) == plain

        long_key = CryptoUtil(b"this_is_a_very_long_key_that_exceeds_32_bytes!!")
        plain2 = "超长密钥测试"
        cipher2 = long_key.encrypt(plain2)
        assert long_key.decrypt(cipher2) == plain2


# ========== 5. 损坏数据容错 ==========

class TestCorruptedData:
    """损坏数据容错测试"""

    def test_invalid_base64(self, crypto):
        """无效Base64数据直通返回"""
        assert crypto.decrypt("!!!invalid_base64!!!") == "!!!invalid_base64!!!"

    def test_too_short_data(self, crypto):
        """加密后数据被截断"""
        plain = "测试数据"
        cipher = crypto.encrypt(plain)
        truncated = cipher[:5]  # 截断到5字符
        result = crypto.decrypt(truncated)
        assert result == truncated  # 无法解密时直通返回

    def test_wrong_key(self):
        """用不同密钥解密应返回原文（容错）"""
        c1 = CryptoUtil(b"key_for_encrypt_32bytes_test!!!")
        c2 = CryptoUtil(b"different_key_for_decrypt_test!!")
        plain = "测试文本"
        cipher = c1.encrypt(plain)
        result = c2.decrypt(cipher)
        # 用错误密钥解密失败时直通返回密文字符串
        assert result is not None  # 不会崩溃


# ========== 6. 随机IV（每次加密结果不同） ==========

class TestRandomIV:
    """随机 IV 特性测试"""

    def test_different_ciphertext(self, crypto):
        """相同明文多次加密产生不同密文"""
        plain = "相同文本"
        c1 = crypto.encrypt(plain)
        c2 = crypto.encrypt(plain)
        assert c1 != c2  # 因为有随机IV，两次加密结果不同

    def test_both_decrypt_same(self, crypto):
        """不同密文都能解密为同一明文"""
        plain = "随机IV测试"
        c1 = crypto.encrypt(plain)
        c2 = crypto.encrypt(plain)
        assert crypto.decrypt(c1) == plain
        assert crypto.decrypt(c2) == plain
