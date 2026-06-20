import configparser
import os


class Config:
    """服务器配置"""

    def __init__(self, config_file="server_config.ini"):
        """从配置文件加载配置

        Args:
            config_file: 配置文件路径
        """
        config = configparser.ConfigParser()
        config.read(config_file, encoding="utf-8")

        # 数据库配置
        self.DB = dict(
            host=config.get("database", "host", fallback="127.0.0.1"),
            port=config.getint("database", "port", fallback=3306),
            user=config.get("database", "user", fallback="root"),
            password=config.get("database", "password", fallback=""),
            database=config.get("database", "database", fallback="campus_im"),
            charset="utf8mb4"
        )

        # 服务器配置
        self.HOST = config.get("server", "host", fallback="0.0.0.0")
        self.PORT = config.getint("server", "port", fallback=9000)

        # 加密配置
        aes_key_str = config.get("security", "aes_key", fallback="campus_im_demo_key_32bytes!!")
        self.AES_KEY = aes_key_str.encode()[:32].ljust(32, b"0")

        # AI配置
        self.AI_API_URL = config.get("ai", "api_url", fallback="")
        self.AI_API_KEY = config.get("ai", "api_key", fallback="")
        self.AI_MODEL = config.get("ai", "model", fallback="gpt-4o-mini")
        self.AI_USER_ID = config.getint("ai", "ai_user_id", fallback=1)
