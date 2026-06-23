"""AES 对称加解密工具

提供基于 pycryptodome 的 AES-CBC 加解密实现。
加密时生成随机 IV，输出 Base64(IV + 密文) 格式；
解密时解析 Base64，提取 IV 后解密。

author: 董钧豪
"""

import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


class CryptoUtil:
    """文本内容 AES 对称加解密（预共享密钥）

    使用 AES-CBC 模式 + PKCS7 填充，每次加密生成随机 IV。
    网络传输格式: Base64(16字节IV + 密文)
    """

    def __init__(self, key: bytes):
        """初始化加密工具

        Args:
            key: AES 密钥，应为 16/24/32 字节
        """
        if len(key) not in (16, 24, 32):
            key = key.ljust(32, b'\0')[:32]
        self._key = key

    def encrypt(self, plaintext: str) -> str:
        """加密文本，返回 Base64 密文

        Args:
            plaintext: 明文字符串

        Returns:
            Base64 编码的 "IV + 密文"
        """
        if not plaintext:
            return ""

        cipher = AES.new(self._key, AES.MODE_CBC)
        iv = cipher.iv
        ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
        return base64.b64encode(iv + ciphertext).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """解密 Base64 密文，返回明文

        Args:
            ciphertext: Base64 编码的 "IV + 密文"

        Returns:
            解密后的明文字符串
        """
        if not ciphertext:
            return ""

        try:
            raw = base64.b64decode(ciphertext)
        except Exception:
            return ciphertext  # 非 Base64 时直通（兼容桩阶段数据）

        if len(raw) < AES.block_size + 1:
            return ciphertext

        iv = raw[:AES.block_size]
        encrypted = raw[AES.block_size:]

        try:
            cipher = AES.new(self._key, AES.MODE_CBC, iv=iv)
            plaintext = unpad(cipher.decrypt(encrypted), AES.block_size)
            return plaintext.decode("utf-8")
        except Exception:
            return ciphertext  # 解密失败时直通（兼容未加密数据）
