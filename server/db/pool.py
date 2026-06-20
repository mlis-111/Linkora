import pymysql
from dbutils.pooled_db import PooledDB


class DBPool:
    """数据库连接池"""

    def __init__(self, cfg: dict):
        """初始化连接池

        Args:
            cfg: 数据库配置字典
        """
        self._pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            blocking=True,
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
            **cfg
        )

    def connection(self):
        """获取数据库连接

        Returns:
            数据库连接对象（上下文管理器）
        """
        return self._pool.connection()
