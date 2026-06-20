class CryptoUtil:
    """文本内容 AES 对称加解密（预共享密钥）

    阶段0：直通桩实现，明文输入输出，保证联调可跑
    阶段1：董钧豪使用pycryptodome的AES实现
    """

    def __init__(self, key: bytes):
        """初始化加密工具

        Args:
            key: 32字节的AES密钥
        """
        self._key = key

    def encrypt(self, plaintext: str) -> str:
        """加密文本，返回Base64密文

        阶段0桩实现：直接返回明文
        阶段1实现：AES(CBC/EAX) 加密，随机 IV，返回 Base64(IV+密文)

        Args:
            plaintext: 明文字符串

        Returns:
            Base64编码的密文（阶段0返回明文）
        """
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """解密Base64密文，返回明文

        阶段0桩实现：直接返回输入
        阶段1实现：解析Base64，提取IV，AES解密

        Args:
            ciphertext: Base64编码的密文（阶段0为明文）

        Returns:
            解密后的明文
        """
        return ciphertext
