class BaseDAO:
    """DAO基类，提供通用的查询和执行方法"""

    def __init__(self, pool):
        """初始化DAO

        Args:
            pool: DBPool实例
        """
        self._pool = pool

    def _query(self, sql, args=()):
        """执行查询，返回所有行

        Args:
            sql: SQL语句
            args: 参数元组

        Returns:
            list: 查询结果列表（字典列表）
        """
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.fetchall()

    def _query_one(self, sql, args=()):
        """查询单行

        Args:
            sql: SQL语句
            args: 参数元组

        Returns:
            dict or None: 查询结果（字典）或None
        """
        rows = self._query(sql, args)
        return rows[0] if rows else None

    def _execute(self, sql, args=()):
        """执行INSERT/UPDATE/DELETE

        Args:
            sql: SQL语句
            args: 参数元组

        Returns:
            int: lastrowid（INSERT时的自增ID）
        """
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return cur.lastrowid
