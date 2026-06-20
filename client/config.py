import configparser


def load_config(config_file="client_config.ini"):
    """从配置文件加载客户端配置

    Args:
        config_file: 配置文件路径

    Returns:
        tuple: (HOST, PORT, AES_KEY)
    """
    config = configparser.ConfigParser()
    config.read(config_file, encoding="utf-8")

    host = config.get("server", "host", fallback="127.0.0.1")
    port = config.getint("server", "port", fallback=9000)
    aes_key_str = config.get("security", "aes_key", fallback="campus_im_demo_key_32bytes!!")
    aes_key = aes_key_str.encode()[:32].ljust(32, b"0")

    return host, port, aes_key


# 加载配置
HOST, PORT, AES_KEY = load_config()
