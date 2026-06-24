"""
AI 问答模块
作者：董浩楠

校园 AI 智能助手服务端：
- 接收客户端 ai_ask 消息
- 异步调用 DeepSeek API（OpenAI 兼容格式）
- 问答持久化到 message 表
- 支持多轮对话上下文

System Prompt 定位：为全校师生提供学习、工作和校园生活方面的帮助。

严格遵循编码详细方案 §8.4：
- register(router, ctx) 注册 MT.AI_ASK
- handle_ai_ask → ctx.workers.submit(_do_ask, session, msg)
- _do_ask: 入库提问 → 调 API → 入库回答 → 回传 ai_answer
- 异常不崩线程，发送友好 ERROR
"""

import json
import time
import logging
import requests
from common.messages import MT


# ── System Prompt ──────────────────────────────────────

SYSTEM_PROMPT = (
    "你是'校园通'的 AI 智能助手，专门为全校师生提供校园学习、工作和生活方面的帮助。"
    "你的核心能力包括："
    "1）课程答疑：解释课程知识点、辅导作业、帮助理解教材内容；"
    "2）论文写作：润色论文摘要、优化文章逻辑、检查语法错误；"
    "3）考试复习：制定复习计划、梳理知识框架、提供模拟练习题；"
    "4）校园办事：解答行政流程、社团活动策划、选课建议等。"
    "请用热情、耐心、专业的态度回答，始终使用中文。"
    "遇到编程或技术类问题也请正常回答并提供示例。"
    "你不是项目客服，不需要了解'校园通'项目的技术实现细节。"
    "请使用 Markdown 格式组织回答，适当使用标题(##)、列表(-)、粗体(**)、"
    "代码块(```)等，让回答结构清晰、易于阅读。"
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

    if user_id is None:
        logging.error("AI模块：user_id 为 None，用户可能未登录")
        session.send({
            "type": MT.ERROR,
            "code": "AI_ERROR",
            "message": "请先登录后再使用 AI 助手",
        })
        return

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

    # 追加当前问题（含附件）
    attachment_name = msg.get("attachment_name", "")
    attachment_content = msg.get("attachment", "")
    if attachment_name and attachment_content:
        question = (f"用户上传了文件 '{attachment_name}'，内容如下：\n"
                    f"```\n{attachment_content}\n```\n"
                    f"用户问题：{question}")
    messages.append({"role": "user", "content": question})

    # 3) 调用 DeepSeek API（流式输出）
    full_answer = ""
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
                "stream": True,
            },
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        # 逐行读取 SSE 流
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except Exception:
                logging.warning("AI模块：SSE 数据行 JSON 解析失败: %.100s", data_str)
                continue

            try:
                delta = chunk["choices"][0]["delta"].get("content", "")
            except (KeyError, IndexError, TypeError):
                logging.warning("AI模块：SSE chunk 缺少 choices/delta: %.200s", data_str)
                delta = ""

            if delta:
                full_answer += delta
                # 逐块推送给客户端
                session.send({
                    "type": MT.AI_ANSWER,
                    "answer": delta,
                    "chunk": True,
                    "ts": int(time.time()),
                })

        # 发送流结束标记
        session.send({
            "type": MT.AI_ANSWER,
            "answer": "",
            "chunk": False,
            "done": True,
            "ts": int(time.time()),
        })

    except Exception as e:
        logging.exception("AI模块：API 调用失败")
        session.send({
            "type": MT.ERROR,
            "code": "AI_ERROR",
            "message": f"AI 服务暂时不可用：{str(e)[:100]}",
        })
        return

    # 4) 入库完整回答
    if full_answer:
        try:
            ctx.db.messages.insert(1, ai_user_id, user_id, None, full_answer)
        except Exception:
            logging.exception("AI模块：回答入库失败")
