"""
AI 问答模块
作者：董浩楠

功能：
- 接收客户端 ai_ask 消息
- 异步调用 DeepSeek API（OpenAI 兼容格式）
- 问答持久化到 message 表
- 支持多轮对话上下文

严格遵循编码详细方案 §8.4：
- register(router, ctx) 注册 MT.AI_ASK
- handle_ai_ask → ctx.workers.submit(_do_ask, session, msg)
- _do_ask: 入库提问 → 调 API → 入库回答 → 回传 ai_answer
- 异常不崩线程，发送友好 ERROR
"""

import time
import logging
import requests
from common.messages import MT


# ── System Prompt ──────────────────────────────────────

SYSTEM_PROMPT = (
    "你是'校园通'即时通信项目的 AI 技术顾问。你熟悉本项目的技术栈："
    "Python socket 通信、PyQt5 客户端、MySQL 数据库、AES 对称加密。"
    "对于项目相关的技术问题，给出专业、具体的回答（涉及代码时给出 Python 示例）。"
    "对于通用问题，正常作答。"
    "回答使用中文，代码注释也使用中文。"
)

# ── 注册 ────────────────────────────────────────────────

def register(router, ctx):
    """注册 AI 模块的消息处理函数

    约定：只注册编码详细方案 §3.2 字段契约中属于 AI 模块的消息类型。

    Args:
        router: MessageRouter 实例
        ctx: ServerContext 实例
    """
    router.register(MT.AI_ASK, handle_ai_ask)


# ── 消息处理 ────────────────────────────────────────────

def handle_ai_ask(session, msg):
    """处理 AI 提问请求

    将任务提交到 ctx.workers 线程池异步执行，不阻塞连接线程。
    编码方案 §8.4 规定：session.ctx.workers.submit(_do_ask, session, msg)

    Args:
        session: Session 实例
        msg: 消息字典 {type: "ai_ask", question: str, ts: int}
    """
    session.ctx.workers.submit(_do_ask, session, msg)


def _do_ask(session, msg):
    """在独立线程中执行 AI 问答（编码方案 §8.4 规定流程）

    流程：
    1. 入库提问：ctx.db.messages.insert(1, user_id, AI_USER_ID, None, question)
    2. 查历史消息拼多轮上下文（可扩充特性）
    3. 调用 DeepSeek API（OpenAI 兼容，requests.post）
    4. 入库回答：ctx.db.messages.insert(1, AI_USER_ID, user_id, None, answer)
    5. 回传 ai_answer 给客户端

    异常处理：超时/失败时 session.send 友好 ERROR，不让线程崩溃。

    Args:
        session: Session 实例
        msg: 消息字典 {question: str, ts: int}
    """
    ctx = session.ctx
    question = msg.get("question", "")
    user_id = session.user_id
    ai_user_id = ctx.config.AI_USER_ID

    # 1) 入库提问（msg_type=1私聊, sender=用户, receiver=AI）
    try:
        ctx.db.messages.insert(1, user_id, ai_user_id, None, question)
    except Exception:
        logging.exception("AI模块：提问入库失败")

    # 2) 构建消息上下文
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        history = ctx.db.messages.query_p2p(user_id, ai_user_id, limit=20)
        for record in history:
            if record["sender_id"] == user_id:
                messages.append({"role": "user", "content": record["content"]})
            elif record["sender_id"] == ai_user_id:
                messages.append({"role": "assistant", "content": record["content"]})
    except Exception:
        logging.exception("AI模块：查询历史失败")

    # 追加当前问题
    messages.append({"role": "user", "content": question})

    # 3) 调用 DeepSeek API（OpenAI 兼容）
    try:
        resp = requests.post(
            ctx.config.AI_API_URL,
            headers={
                "Authorization": f"Bearer {ctx.config.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": ctx.config.AI_MODEL,
                "messages": messages,
            },
            timeout=60,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logging.exception("AI模块：API 调用失败")
        session.send({
            "type": MT.ERROR,
            "code": "AI_ERROR",
            "message": f"AI 服务暂时不可用：{str(e)[:100]}",
        })
        return

    # 4) 入库回答
    try:
        ctx.db.messages.insert(1, ai_user_id, user_id, None, answer)
    except Exception:
        logging.exception("AI模块：回答入库失败")

    # 5) 回传答案（字段严格按契约：answer, ts）
    session.send({
        "type": MT.AI_ANSWER,
        "answer": answer,
        "ts": int(time.time()),
    })
