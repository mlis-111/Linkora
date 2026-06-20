from server.config import Config
from common.crypto import CryptoUtil
from server.db.pool import DBPool
from server.core.context import ServerContext
from server.core.router import MessageRouter
from server.core.server import ChatServer
from server.modules import user, chat, friend, file, ai


def build():
    """构建并返回ChatServer实例

    Returns:
        ChatServer: 服务器实例
    """
    cfg = Config()
    pool = DBPool(cfg.DB)
    crypto = CryptoUtil(cfg.AES_KEY)
    ctx = ServerContext(cfg, pool, crypto)
    router = MessageRouter()

    # 各模块自注册
    for module in (user, chat, friend, file, ai):
        module.register(router, ctx)

    return ChatServer(ctx, router)


if __name__ == "__main__":
    build().serve_forever()
