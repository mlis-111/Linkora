"""Server 核心组件集成测试

测试服务器框架层各组件之间的协作：
1. MessageRouter 注册 + 分发
2. ServerContext 依赖注入
3. OnlineRegistry 线程安全
4. Session 生命周期
5. 多模块联合注册
6. 断开连接钩子链
"""

import threading
import time

import pytest
from common.messages import MT
from server.core.router import MessageRouter
from server.core.online import OnlineRegistry
from server.core.session import Session
from server.core.context import ServerContext


# ════════════════════════════════════════════════════════════════
# MessageRouter 注册与分发测试
# ════════════════════════════════════════════════════════════════

class TestRouterDispatch:
    """路由器分发集成测试"""

    def test_register_and_dispatch(self, router, session):
        """注册处理函数并分发消息"""
        called = []

        def handler(s, msg):
            called.append((s.user_id, msg["data"]))

        router.register("test_type", handler)
        router.dispatch(session, {"type": "test_type", "data": "payload"})

        assert called == [(100, "payload")]

    def test_unknown_type_returns_error(self, router, session):
        """未注册的消息类型返回错误"""
        router.dispatch(session, {"type": "nonexistent"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR
        assert "未知" in resp.get("message", "") or "UNKNOWN" in resp.get("code", "")

    def test_multiple_handlers_dispatch_correctly(self, router, session):
        """多个处理函数各自收到正确的消息"""
        results = {}

        def handler_a(s, msg):
            results["a"] = msg["value"]

        def handler_b(s, msg):
            results["b"] = msg["value"]

        router.register("type_a", handler_a)
        router.register("type_b", handler_b)

        router.dispatch(session, {"type": "type_a", "value": 1})
        router.dispatch(session, {"type": "type_b", "value": 2})

        assert results == {"a": 1, "b": 2}

    def test_duplicate_registration_raises(self, router):
        """重复注册相同消息类型抛出 ValueError"""
        router.register("dup_type", lambda s, m: None)
        with pytest.raises(ValueError, match="重复注册"):
            router.register("dup_type", lambda s, m: None)

    def test_dispatch_missing_type_key(self, router, session):
        """消息缺少 type 字段返回错误"""
        router.dispatch(session, {"data": "no_type"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == MT.ERROR

    def test_handler_exception_is_not_propagated(self, router, session):
        """处理函数抛异常不会影响路由分发"""
        def faulty(s, msg):
            raise RuntimeError("模拟处理异常")

        router.register("faulty", faulty)
        # 不应抛出异常（dispatch 本身不 catch，但 ClientHandler.run 会 catch）
        with pytest.raises(RuntimeError):
            router.dispatch(session, {"type": "faulty"})

    def test_full_module_registration(self, router, ctx):
        """模拟所有业务模块的注册流程"""
        from server.modules import user, chat, friend, group, file, ai

        modules = [user, chat, friend, group, file, ai]
        for mod in modules:
            mod.register(router, ctx)

        # 验证所有模块的关键消息类型都已注册
        registered = set(router._handlers.keys())
        essential_types = {
            MT.LOGIN, MT.REGISTER, MT.LOGOUT,
            MT.CHAT, MT.ROOM_CHAT, MT.HISTORY_REQ,
            MT.FRIEND_ADD, MT.FRIEND_LIST, MT.FRIEND_AGREE,
            MT.GROUP_CREATE, MT.GROUP_LIST,
            MT.FILE_REQ, MT.FILE_DATA, MT.FILE_END,
        }
        missing = essential_types - registered
        assert not missing, f"缺少注册: {missing}"


# ════════════════════════════════════════════════════════════════
# OnlineRegistry 集成测试
# ════════════════════════════════════════════════════════════════

class TestOnlineRegistry:
    """在线注册表集成测试"""

    def test_add_and_is_online(self, online_registry, mock_handler):
        """添加上线 → 检查在线状态"""
        online_registry.add(100, mock_handler)
        assert online_registry.is_online(100)
        assert not online_registry.is_online(999)

    def test_remove(self, online_registry, mock_handler):
        """下线后不再在线"""
        online_registry.add(100, mock_handler)
        online_registry.remove(100)
        assert not online_registry.is_online(100)

    def test_online_ids(self, online_registry, mock_handler, second_handler):
        """在线用户 ID 列表"""
        online_registry.add(100, mock_handler)
        online_registry.add(200, second_handler)
        ids = online_registry.online_ids()
        assert sorted(ids) == [100, 200]

    def test_send_to_user(self, online_registry, mock_handler):
        """发送消息给在线用户"""
        online_registry.add(100, mock_handler)
        msg = {"type": "chat", "content": "hello"}
        result = online_registry.send(100, msg)
        assert result is True
        mock_handler.send.assert_called_with(msg)

    def test_send_to_offline(self, online_registry):
        """发送给不在线用户返回 False"""
        result = online_registry.send(999, {"type": "chat"})
        assert result is False

    def test_broadcast(self, online_registry, mock_handler, second_handler):
        """广播给所有在线用户"""
        online_registry.add(100, mock_handler)
        online_registry.add(200, second_handler)
        msg = {"type": "user_list"}
        online_registry.broadcast(msg)

        mock_handler.send.assert_called_with(msg)
        second_handler.send.assert_called_with(msg)

    def test_broadcast_exclude(self, online_registry, mock_handler, second_handler):
        """广播时排除指定用户"""
        online_registry.add(100, mock_handler)
        online_registry.add(200, second_handler)
        msg = {"type": "user_list"}
        online_registry.broadcast(msg, exclude=100)

        mock_handler.send.assert_not_called()
        second_handler.send.assert_called_with(msg)

    def test_broadcast_to(self, online_registry, mock_handler, second_handler):
        """向指定 ID 列表中的在线用户广播"""
        online_registry.add(100, mock_handler)
        online_registry.add(200, second_handler)
        msg = {"type": "room_chat"}
        online_registry.broadcast_to(msg, [100, 300])  # 300 不在线

        mock_handler.send.assert_called_with(msg)
        second_handler.send.assert_not_called()

    def test_thread_safety(self, online_registry):
        """多线程并发 add/remove/online_ids"""
        errors = []

        def worker(tag):
            try:
                for i in range(100):
                    uid = tag * 1000 + i
                    handler = type("Mock", (), {"send": lambda self, m: None})()
                    online_registry.add(uid, handler)
                    online_registry.is_online(uid)
                    online_registry.online_ids()
                    online_registry.remove(uid)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"并发错误: {errors}"
        # 所有用户都应已移除
        assert online_registry.online_ids() == []


# ════════════════════════════════════════════════════════════════
# Session 生命周期测试
# ════════════════════════════════════════════════════════════════

class TestSessionLifecycle:
    """Session 生命周期集成测试"""

    def test_bind_user(self, unbound_session):
        """绑定用户设置 user_id 和 username"""
        unbound_session.bind_user(100, "test_user")
        assert unbound_session.user_id == 100
        assert unbound_session.username == "test_user"

    def test_send_delegates_to_handler(self, session):
        """session.send() 委托给 handler.send()"""
        msg = {"type": "test", "data": 42}
        session.send(msg)
        session._handler.send.assert_called_with(msg)

    def test_rebind_user_overwrites(self, session):
        """Session 重复绑定会覆盖原有用户信息"""
        session.bind_user(999, "another")
        assert session.user_id == 999
        assert session.username == "another"

    def test_unbound_send_still_works(self, unbound_session):
        """未绑定 Session 也能发送消息"""
        unbound_session.send({"type": "error", "reason": "未登录"})
        assert unbound_session._handler.send.called

    def test_session_holds_ctx_reference(self, session, ctx):
        """Session 持有 ServerContext 引用"""
        assert session.ctx is ctx


# ════════════════════════════════════════════════════════════════
# ServerContext 集成测试
# ════════════════════════════════════════════════════════════════

class TestServerContext:
    """ServerContext 依赖注入集成测试"""

    def test_context_has_all_components(self, ctx, mock_db, online_registry, crypto):
        """Context 包含所有必要的组件"""
        assert ctx.config is not None
        assert ctx.db is mock_db
        assert ctx.online is online_registry
        assert ctx.crypto is crypto
        assert ctx.workers is not None

    def test_db_dao_access(self, ctx, mock_db):
        """通过 ctx.db 访问各 DAO"""
        assert ctx.db.users is mock_db.users
        assert ctx.db.messages is mock_db.messages
        assert ctx.db.friends is mock_db.friends
        assert ctx.db.files is mock_db.files
        assert ctx.db.ai_msg is mock_db.ai_msg
        assert ctx.db.friend_requests is mock_db.friend_requests
        assert ctx.db.groups is mock_db.groups

    def test_disconnect_hook_registration(self, ctx):
        """注册断连钩子"""
        called = []

        def hook(s):
            called.append(s.user_id)

        ctx.on_disconnect(hook)
        assert len(ctx._disconnect_hooks) == 1

        # 模拟触发
        mock_session = type("MockSession", (), {"user_id": 100, "ctx": ctx})()
        ctx.fire_disconnect(mock_session)
        assert called == [100]

    def test_disconnect_hook_chain(self, ctx):
        """多个断连钩子依次执行"""
        order = []

        def hook_a(s): order.append("a")
        def hook_b(s): order.append("b")
        def hook_c(s): order.append("c")

        ctx.on_disconnect(hook_a)
        ctx.on_disconnect(hook_b)
        ctx.on_disconnect(hook_c)

        mock_session = type("MockSession", (), {"user_id": 100, "ctx": ctx})()
        ctx.fire_disconnect(mock_session)

        assert order == ["a", "b", "c"]

    def test_disconnect_hook_exception_ignored(self, ctx):
        """某个钩子抛异常不影响后续钩子执行"""
        order = []

        def faulty(s): raise RuntimeError("hook error")
        def ok_hook(s): order.append("ok")

        ctx.on_disconnect(faulty)
        ctx.on_disconnect(ok_hook)

        mock_session = type("MockSession", (), {"user_id": 100, "ctx": ctx})()
        # 不应抛出异常
        ctx.fire_disconnect(mock_session)
        assert order == ["ok"]


# ════════════════════════════════════════════════════════════════
# Router + Context + Session 联合测试
# ════════════════════════════════════════════════════════════════

class TestRouterContextSessionIntegration:
    """路由器 + 上下文 + 会话联合集成"""

    def test_full_dispatch_chain(self, router, ctx, session):
        """完整的消息分发链：dispatch → handler(session, msg) → session.send()"""
        router.register("greet", lambda s, m: s.send({
            "type": "greet_resp",
            "echo": m["text"],
            "user": s.username,
        }))

        router.dispatch(session, {"type": "greet", "text": "hello"})

        resp = session._handler.send.call_args[0][0]
        assert resp["type"] == "greet_resp"
        assert resp["echo"] == "hello"
        assert resp["user"] == "test_user"

    def test_handler_accesses_context(self, router, ctx, session):
        """处理函数通过 session.ctx 访问数据库和在线表"""
        ctx.db.users.get_by_id.return_value = {"user_id": 200, "username": "friend"}
        ctx.online.add(200, session._handler)

        def get_user_info(s, msg):
            user = s.ctx.db.users.get_by_id(msg["user_id"])
            online = s.ctx.online.is_online(msg["user_id"])
            s.send({"user": user, "online": online})

        router.register("get_user", get_user_info)
        router.dispatch(session, {"type": "get_user", "user_id": 200})

        resp = session._handler.send.call_args[0][0]
        assert resp["user"]["username"] == "friend"
        assert resp["online"] is True
