"""
AI 问答面板
作者：董浩楠

校园 AI 智能助手，为师生提供学习、工作和校园生活方面的帮助：
- 答疑解惑（课程知识、作业辅导、考试复习）
- 文案润色（论文、报告、通知）
- 学习规划（复习计划、时间管理、选课建议）
- 校园生活（社团活动、校园资讯）

UI 严格对齐设计稿 AI问答面板.dc.html。
"""

import time
import re
from datetime import datetime

from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QScrollArea, QFrame, QWidget)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from client.core.base_panel import BasePanel
from common.messages import MT

# ── 设计稿颜色 ─────────────────────────────────────────
C_AI_PRIME  = "#7C5CFC"   # 主题紫色
C_AI_BADGE  = "#E6E6FA"   # 浅紫（选中项背景、按钮背景）
C_USER_BLUE = "#5971F2"   # 用户气泡蓝
C_CODE_BG   = "#1E2A3A"   # 代码块深色背景
C_BG        = "#F4F6FA"   # 全局背景浅蓝灰
C_SIDEBAR   = "#FFFFFF"   # 侧栏白
C_BORDER    = "#E5E5E5"   # 边框灰
C_SUBTLE    = "#8C8C8C"   # 次级文字灰
C_DARK      = "#1E293B"   # 主文字深色
C_WHITE     = "#FFFFFF"


class AIPanel(BasePanel):
    """AI 问答面板"""

    def subscribe(self):
        self._messages = []
        self._conversations = []
        self._current_conv_idx = -1
        self._is_waiting = False
        self.app.net.on(MT.AI_ANSWER, self._on_ai_answer)
        self._build_ui()

    # ═══════════════════════════════════════════════════
    #  整体布局
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._create_sidebar())

        right = QWidget()
        right.setObjectName("RightPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._create_header())
        rl.addWidget(self._create_messages_area(), 1)
        rl.addWidget(self._create_composer())
        layout.addWidget(right, 1)

    # ═══════════════════════════════════════════════════
    #  历史对话侧栏
    # ═══════════════════════════════════════════════════

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("LeftSidebar")
        sidebar.setFixedWidth(320)
        sidebar.setStyleSheet(
            f"background:{C_SIDEBAR}; border-right:1px solid {C_BORDER};")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 品牌区 ──
        brand = QWidget()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(24, 24, 24, 18)
        brand_layout.setSpacing(14)

        icon = QLabel("🤖")
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"""
            background:{C_AI_PRIME}; border-radius:13px;
            font-size:24px;
        """)
        brand_layout.addWidget(icon)

        brand_text = QLabel("校园通\nAI 智能助手")
        brand_text.setStyleSheet(
            f"font-size:16px; font-weight:800; color:{C_DARK}; line-height:1.3;")
        brand_layout.addWidget(brand_text)
        brand_layout.addStretch()
        layout.addWidget(brand)

        # ── 分隔线 ──
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            "background:{C_BORDER}; margin:0 24px;")
        layout.addWidget(sep)

        # ── 标题行 ──
        tr = QWidget()
        tr_layout = QHBoxLayout(tr)
        tr_layout.setContentsMargins(24, 18, 24, 10)
        title = QLabel("历史对话")
        title.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{C_DARK};")
        tr_layout.addWidget(title)
        tr_layout.addStretch()

        add = QPushButton("＋")
        add.setFixedSize(36, 36)
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(f"""
            QPushButton {{
                background:{C_AI_BADGE}; color:{C_AI_PRIME}; border:none;
                border-radius:12px; font-size:16px; font-weight:700;
            }}
            QPushButton:hover {{ background:#D4CDF2; }}
        """)
        add.clicked.connect(self._new_conversation)
        tr_layout.addWidget(add)
        layout.addWidget(tr)

        # 搜索框
        sc = QWidget()
        sc_layout = QHBoxLayout(sc)
        sc_layout.setContentsMargins(24, 0, 24, 14)
        sb = QFrame()
        sb.setFixedHeight(44)
        sb.setStyleSheet(
            f"background:{C_WHITE}; border-radius:14px; border:1px solid {C_BORDER};")
        sbl = QHBoxLayout(sb)
        sbl.setContentsMargins(15, 0, 15, 0)
        sbl.setSpacing(10)
        si = QLabel("🔍")
        si.setStyleSheet("font-size:17px;")
        sbl.addWidget(si)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索对话")
        self._search_input.setStyleSheet(
            "border:none; background:transparent; font-size:14px; color:#1E293B;")
        sbl.addWidget(self._search_input)
        sc_layout.addWidget(sb)
        layout.addWidget(sc)

        # 历史列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border:none; background:transparent; }"
            "QScrollBar:vertical { width:4px; background:transparent; }"
            "QScrollBar::handle:vertical { background:#D0D5DD; border-radius:2px; }")
        self._history_content = QWidget()
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(16, 0, 16, 0)
        self._history_layout.setSpacing(4)
        self._history_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._history_content)
        layout.addWidget(scroll, 1)

        # 示例历史
        samples = [
            ("高等数学疑难解答",  "今天",   3),
            ("论文开题报告润色", "昨天",  7),
            ("期末考试复习规划", "周一", 5),
            ("英语四级备考攻略",  "周日",  4),
            ("社团活动策划方案", "上周五", 6),
        ]
        for i, (t, d, c) in enumerate(samples):
            self._conversations.append(
                {"title": t, "date": d, "messages": [], "preview_count": c})
            self._history_layout.addWidget(
                self._create_history_item(t, f"{d} · {c} 条消息", i == 0))

        self._history_layout.addStretch()
        return sidebar

    def _create_history_item(self, title_text, subtitle, active=False):
        item = QFrame()
        item.setObjectName("HistoryItem")
        item.setProperty("selected", "true" if active else "false")
        item.setCursor(Qt.PointingHandCursor)
        item.setStyleSheet(
            "QWidget#HistoryItem { margin:4px 12px; padding:10px 14px; border-radius:8px; }"
            "QWidget#HistoryItem[selected=\"true\"] { background:#E6E6FA; }"
            "QWidget#HistoryItem:hover { background:rgba(230,230,250,0.5); }")
        il = QVBoxLayout(item)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(4)
        tl = QLabel(title_text)
        tl.setObjectName("HistoryItemTitle")
        tl.setStyleSheet(
            f"font-size:14px; font-weight:{'700' if active else 'bold'};"
            f"color:{C_AI_PRIME if active else '#333333'};")
        il.addWidget(tl)
        sl = QLabel(subtitle)
        sl.setObjectName("HistoryItemSub")
        sl.setStyleSheet(
            f"font-size:12px; color:{C_AI_PRIME if active else '#999999'};")
        il.addWidget(sl)
        return item

    def _new_conversation(self):
        self._messages = []
        self._current_conv_idx = -1
        self._is_waiting = False
        self._refresh_messages()

    # ═══════════════════════════════════════════════════
    #  AI 聊天头部
    # ═══════════════════════════════════════════════════

    def _create_header(self):
        h = QFrame()
        h.setFixedHeight(80)
        h.setStyleSheet(
            f"background:{C_SIDEBAR}; border-bottom:1px solid {C_BORDER};")
        hl = QHBoxLayout(h)
        hl.setContentsMargins(28, 11, 28, 11)
        hl.setSpacing(16)

        # 圆形头像
        av = QLabel("✨")
        av.setFixedSize(40, 40)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C_AI_PRIME}, stop:1 {C_AI_PRIME});
            color:white; border-radius:20px; font-size:24px;
        """)
        hl.addWidget(av)

        # 名称 + 徽章 + 副标题
        info = QVBoxLayout()
        info.setSpacing(3)
        nr = QHBoxLayout()
        nr.setSpacing(9)
        nm = QLabel("AI 助手")
        nm.setStyleSheet(f"font-size:16px; font-weight:800; color:{C_DARK};")
        nr.addWidget(nm)
        bd = QLabel("智能问答")
        bd.setFixedHeight(22)
        bd.setStyleSheet(f"""
            font-size:12px; font-weight:700; color:{C_AI_PRIME};
            background:{C_AI_BADGE}; padding:2px 9px; border-radius:8px;
        """)
        nr.addWidget(bd)
        nr.addStretch()
        info.addLayout(nr)
        st = QLabel("随时问我学习、工作和校园生活方面的问题")
        st.setStyleSheet(f"font-size:13px; color:{C_SUBTLE};")
        info.addWidget(st)
        hl.addLayout(info)
        hl.addStretch()

        # 新对话按钮
        nb = QPushButton("🔄  新对话")
        nb.setFixedHeight(38)
        nb.setCursor(Qt.PointingHandCursor)
        nb.setStyleSheet(f"""
            QPushButton {{
                background:{C_AI_BADGE}; color:{C_AI_PRIME}; border:none;
                border-radius:13px; font-size:14px; font-weight:600;
                padding:0 16px;
            }}
            QPushButton:hover {{ background:#D4CDF2; }}
        """)
        nb.clicked.connect(self._new_conversation)
        hl.addWidget(nb)
        return h

    # ═══════════════════════════════════════════════════
    #  消息区域
    # ═══════════════════════════════════════════════════

    def _create_messages_area(self):
        self._msg_scroll = QScrollArea()
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._msg_scroll.setStyleSheet(
            f"QScrollArea {{ border:none; background:{C_BG}; }}"
            "QScrollBar:vertical { width:6px; background:transparent; }"
            "QScrollBar::handle:vertical { background:rgba(100,116,139,0.22);"
            "border-radius:3px; min-height:20px; }")

        self._msg_content = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_content)
        self._msg_layout.setContentsMargins(36, 20, 36, 20)
        self._msg_layout.setSpacing(22)
        self._msg_layout.setAlignment(Qt.AlignTop)
        self._msg_scroll.setWidget(self._msg_content)

        # 空状态提示
        self._empty_hint = QLabel(
            "<div style='text-align:center; padding:60px 0;'>"
            "<div style='font-size:48px; margin-bottom:16px;'>✨</div>"
            "<div style='font-size:16px; font-weight:700; color:{C_SUBTLE};'>"
            "AI 智能助手</div>"
            "<div style='font-size:13px; color:{C_SUBTLE}; margin-top:8px;'>"
            "问我学习、工作和校园生活方面的问题</div>"
            "</div>")
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._msg_layout.addWidget(self._empty_hint)
        self._msg_layout.addStretch()

        return self._msg_scroll

    # ═══════════════════════════════════════════════════
    #  输入区
    # ═══════════════════════════════════════════════════

    def _create_composer(self):
        c = QFrame()
        c.setStyleSheet(f"background:{C_BG};")
        cl = QVBoxLayout(c)
        cl.setContentsMargins(24, 16, 24, 20)
        cl.setSpacing(13)

        # 快捷提问
        qr = QHBoxLayout()
        qr.setSpacing(9)
        prompts = [
            "📖 帮我解释课程知识点",
            "✍️ 润色论文摘要",
            "📅 制定期末复习计划",
            "💡 如何高效学习方法",
        ]
        for p in prompts:
            chip = QPushButton(p)
            chip.setObjectName("RecommendBtn")
            chip.setFixedHeight(34)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(f"""
                QPushButton#RecommendBtn {{
                    font-size:13px;
                    background:{C_WHITE}; border:1px solid {C_BORDER};
                    border-radius:16px; padding:6px 12px;
                    color:{C_SUBTLE};
                }}
                QPushButton#RecommendBtn:hover {{
                    background:{C_AI_BADGE}; border-color:{C_AI_PRIME};
                    color:{C_AI_PRIME};
                }}
            """)
            chip.clicked.connect(lambda _, x=p: self._send_quick(x))
            qr.addWidget(chip)
        qr.addStretch()
        cl.addLayout(qr)

        # 输入卡片
        ic = QFrame()
        ic.setStyleSheet(f"background:{C_WHITE}; border-radius:20px;")
        icl = QHBoxLayout(ic)
        icl.setContentsMargins(16, 10, 10, 10)
        icl.setSpacing(13)

        self._input_field = QLineEdit()
        self._input_field.setObjectName("InputField")
        self._input_field.setPlaceholderText(
            "问我学习、工作和校园生活方面的问题…")
        self._input_field.setMinimumHeight(48)
        self._input_field.setStyleSheet(
            f"border:none; background:transparent; font-size:15px;"
            f"color:{C_DARK}; padding-left:16px; padding-right:16px;"
            f"border-radius:24px;")
        self._input_field.returnPressed.connect(self._on_send)
        icl.addWidget(self._input_field, 1)

        # 发送按钮
        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(48, 48)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_AI_PRIME};
                color:white; border:none; border-radius:15px;
                font-size:22px;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #9677EA, stop:1 #6B4CEC);
            }}
        """)
        self._send_btn.clicked.connect(self._on_send)
        icl.addWidget(self._send_btn)

        cl.addWidget(ic)
        return c

    # ═══════════════════════════════════════════════════
    #  用户消息气泡
    # ═══════════════════════════════════════════════════

    def _user_bubble(self, text, ts_str):
        """蓝色渐变，右对齐，不对称圆角 18/5/18/18"""
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(13)
        lo.setDirection(QHBoxLayout.RightToLeft)

        av = QLabel("我")
        av.setFixedSize(40, 40)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C_USER_BLUE}, stop:1 {C_USER_BLUE});
            color:white; border-radius:20px; font-size:16px; font-weight:700;
        """)
        lo.addWidget(av)

        tw = QWidget()
        tl = QVBoxLayout(tw)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        tl.setAlignment(Qt.AlignRight)

        tm = QLabel(ts_str)
        tm.setAlignment(Qt.AlignRight)
        tm.setStyleSheet(f"font-size:12px; color:{C_SUBTLE};")
        tl.addWidget(tm)

        # 气泡容器（用 QFrame 实现不对称圆角）
        bf = QFrame()
        bf.setObjectName("UserBubble")
        bf.setStyleSheet(f"""
            QFrame#UserBubble {{
                background:{C_USER_BLUE}; color:#FFFFFF;
                border-radius:12px; border-top-right-radius:4px;
                padding:12px 16px; font-size:15px;
            }}
        """)
        bl = QVBoxLayout(bf)
        bl.setContentsMargins(0, 0, 0, 0)
        bt = QLabel(text)
        bt.setObjectName("UserBubbleText")
        bt.setWordWrap(True)
        bt.setMaximumWidth(480)
        bt.setTextFormat(Qt.PlainText)
        bt.setStyleSheet(
            "color:#FFFFFF; font-size:15px; background:transparent; border:none;")
        bt.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(bt)
        tl.addWidget(bf, alignment=Qt.AlignRight)

        lo.addWidget(tw)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════════════
    #  AI 消息气泡
    # ═══════════════════════════════════════════════════

    def _ai_bubble(self, text, ts_str):
        """白色背景，左对齐，不对称圆角 5/18/18/18"""
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(13)

        av = QLabel("✨")
        av.setFixedSize(40, 40)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C_AI_PRIME}, stop:1 {C_AI_PRIME});
            color:white; border-radius:20px; font-size:16px;
        """)
        lo.addWidget(av)

        tw = QWidget()
        tl = QVBoxLayout(tw)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)

        info = QLabel(f"AI 助手 · {ts_str}")
        info.setStyleSheet(f"font-size:12px; color:{C_SUBTLE};")
        tl.addWidget(info)

        bf = QFrame()
        bf.setObjectName("AIBubble")
        bf.setStyleSheet(f"""
            QFrame#AIBubble {{
                background:{C_WHITE}; border:1px solid #DDDDDD;
                border-radius:12px; border-top-left-radius:4px;
                padding:12px 16px; font-size:15px;
            }}
        """)
        bl = QVBoxLayout(bf)
        bl.setContentsMargins(0, 0, 0, 0)
        bt = QLabel(text)
        bt.setObjectName("AIBubbleText")
        bt.setWordWrap(True)
        bt.setMaximumWidth(520)
        bt.setTextFormat(Qt.RichText)
        bt.setStyleSheet(
            "color:#222222; font-size:15px; background:transparent; border:none;")
        bt.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(bt)
        tl.addWidget(bf)

        lo.addWidget(tw)
        lo.addStretch()
        return w

    # ═══════════════════════════════════════════════════
    #  代码块
    # ═══════════════════════════════════════════════════

    def _code_block(self, language, code_text):
        block = QFrame()
        block.setStyleSheet(f"""
            QFrame {{
                background:{C_CODE_BG};
                border-radius:12px;
                
            }}
        """)
        block.setMaximumWidth(520)
        bl = QVBoxLayout(block)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(12)

        top = QHBoxLayout()
        ll = QLabel(language)
        ll.setStyleSheet(
            "font-size:12px; font-family:Consolas,monospace; "
            "font-weight:600; color:#7C9EC8; background:transparent; border:none;")
        top.addWidget(ll)
        top.addStretch()

        cp = QPushButton("📋 复制")
        cp.setCursor(Qt.PointingHandCursor)
        cp.setStyleSheet(
            "QPushButton { color:#7C9EC8; background:transparent; border:none;"
            "font-size:12px; }"
            "QPushButton:hover { color:#A0C8F0; }")
        cp.clicked.connect(lambda: self._copy(code_text))
        top.addWidget(cp)
        bl.addLayout(top)

        cl = QLabel(code_text)
        cl.setTextFormat(Qt.PlainText)
        cl.setWordWrap(False)
        cl.setStyleSheet(
            "font-family:'Consolas','Courier New',monospace; font-size:13px;"
            "color:#E2E8F0; background:transparent; border:none;"
            "line-height:1.75;")
        bl.addWidget(cl)
        return block

    # ═══════════════════════════════════════════════════
    #  发送 & 接收
    # ═══════════════════════════════════════════════════

    def _on_send(self):
        text = self._input_field.text().strip()
        if not text or self._is_waiting:
            return
        self._input_field.clear()

        # 首次发送隐藏空状态提示
        if not self._messages:
            self._clear_messages()

        ts = int(time.time())
        ts_str = datetime.now().strftime("%H:%M")

        self._messages.append({"role": "user", "content": text, "ts": ts_str})
        self._add_to_chat(self._user_bubble(text, ts_str))

        self._is_waiting = True
        self._send_btn.setEnabled(False)

        # 等待指示器
        self._waiting = QLabel("✨ AI 正在思考…")
        self._waiting.setContentsMargins(0, 8, 0, 8)
        self._waiting.setStyleSheet(
            f"font-size:13px; color:{C_SUBTLE}; background:transparent;")
        self._add_to_chat(self._waiting)

        # 流式状态
        self._stream_full = ""
        self._stream_container = None
        self._stream_bubble = None

        self.net.send({"type": MT.AI_ASK, "question": text, "ts": ts})

    def _on_ai_answer(self, msg):
        is_chunk = msg.get("chunk", False)
        is_done = msg.get("done", False)

        # ── 流式块 ──
        if is_chunk:
            delta = msg.get("answer", "")
            if not delta:
                return

            # 第一个块：移除等待指示器，创建 AI 气泡容器
            if self._stream_container is None:
                if hasattr(self, '_waiting') and self._waiting:
                    self._waiting.hide()
                    self._waiting.deleteLater()
                    self._waiting = None

                # 创建流式气泡容器
                w = QWidget()
                lo = QHBoxLayout(w)
                lo.setContentsMargins(0, 0, 0, 0)
                lo.setSpacing(13)

                av = QLabel("✨")
                av.setFixedSize(40, 40)
                av.setAlignment(Qt.AlignCenter)
                av.setStyleSheet(f"""
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {C_AI_PRIME}, stop:1 {C_AI_PRIME});
                    color:white; border-radius:20px; font-size:16px;
                """)
                lo.addWidget(av)

                tw = QWidget()
                tl = QVBoxLayout(tw)
                tl.setContentsMargins(0, 0, 0, 0)
                tl.setSpacing(6)

                info = QLabel("AI 助手")
                info.setStyleSheet(f"font-size:12px; color:{C_SUBTLE};")
                tl.addWidget(info)

                bf = QFrame()
                bf.setObjectName("AIBubble")
                bf.setStyleSheet(f"""
                    QFrame#AIBubble {{
                        background:{C_WHITE}; border:1px solid #DDDDDD;
                        border-radius:12px; border-top-left-radius:4px;
                        padding:12px 16px; font-size:15px;
                    }}
                """)
                bl = QVBoxLayout(bf)
                bl.setContentsMargins(0, 0, 0, 0)
                bt = QLabel("")
                bt.setObjectName("AIBubbleText")
                bt.setWordWrap(True)
                bt.setMaximumWidth(520)
                bt.setTextFormat(Qt.PlainText)
                bt.setStyleSheet(
                    "color:#222222; font-size:15px; background:transparent; border:none;")
                bt.setContentsMargins(0, 0, 0, 0)
                bl.addWidget(bt)
                tl.addWidget(bf)

                lo.addWidget(tw)
                lo.addStretch()

                self._stream_container = w
                self._stream_bubble = bt

                # 移除 stretch，插入流式容器
                if self._msg_layout.count() > 0:
                    last = self._msg_layout.itemAt(self._msg_layout.count() - 1)
                    if last.spacerItem():
                        self._msg_layout.removeItem(last)
                self._msg_layout.addWidget(w)
                self._msg_layout.addStretch()

            # 追加文本
            self._stream_full += delta
            self._stream_bubble.setText(self._stream_full)
            self._scroll_to_bottom()
            return

        # ── 流结束 ──
        if is_done:
            self._is_waiting = False
            self._send_btn.setEnabled(True)

            ts_str = datetime.now().strftime("%H:%M")
            self._messages.append(
                {"role": "ai", "content": self._stream_full, "ts": ts_str})

            self._stream_container = None
            self._stream_bubble = None
            return

        # ── 非流式（兼容旧版） ──
        self._is_waiting = False
        self._send_btn.setEnabled(True)

        if hasattr(self, '_waiting') and self._waiting:
            self._waiting.hide()
            self._waiting.deleteLater()
            self._waiting = None

        answer = msg.get("answer", "抱歉，我没有理解你的问题。")
        ts_val = msg.get("ts", int(time.time()))
        ts_str = (datetime.fromtimestamp(ts_val).strftime("%H:%M")
                  if isinstance(ts_val, (int, float))
                  else datetime.now().strftime("%H:%M"))

        self._messages.append(
            {"role": "ai", "content": answer, "ts": ts_str})

        parts = self._parse_answer(answer)
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)

        hr = QHBoxLayout()
        hr.setSpacing(13)
        av = QLabel("✨")
        av.setFixedSize(40, 40)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C_AI_PRIME}, stop:1 {C_AI_PRIME});
            color:white; border-radius:20px; font-size:16px;
        """)
        hr.addWidget(av)
        info = QLabel(f"AI 助手 · {ts_str}")
        info.setStyleSheet(f"font-size:12px; color:{C_SUBTLE};")
        hr.addWidget(info)
        hr.addStretch()
        cl.addLayout(hr)

        for part in parts:
            if part["type"] == "text":
                bf = QFrame()
                bf.setObjectName("AIBubble")
                bf.setStyleSheet(f"""
                    QFrame#AIBubble {{
                        background:{C_WHITE}; border:1px solid #DDDDDD;
                        border-radius:12px; border-top-left-radius:4px;
                        padding:12px 16px; font-size:15px;
                    }}
                """)
                bl = QVBoxLayout(bf)
                bl.setContentsMargins(0, 0, 0, 0)
                bt = QLabel(part["content"])
                bt.setObjectName("AIBubbleText")
                bt.setWordWrap(True)
                bt.setMaximumWidth(520)
                bt.setTextFormat(Qt.RichText)
                bt.setStyleSheet(
                    "color:#222222; font-size:15px; background:transparent; border:none;")
                bt.setContentsMargins(0, 0, 0, 0)
                bl.addWidget(bt)
                cl.addWidget(bf)
            elif part["type"] == "code":
                cl.addWidget(self._code_block(
                    part.get("language", ""), part["content"]))

        self._add_to_chat(container)
        self._scroll_to_bottom()

    def _waiting_indicator(self):
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(13)
        av = QLabel("✨")
        av.setFixedSize(40, 40)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C_AI_PRIME}, stop:1 {C_AI_PRIME});
            color:white; border-radius:20px; font-size:16px;
        """)
        lo.addWidget(av)
        info = QLabel("AI 助手 · 正在思考…")
        info.setStyleSheet(f"font-size:12px; color:{C_SUBTLE};")
        lo.addWidget(info)
        lo.addStretch()
        return w

    def _send_quick(self, prompt_text):
        parts = prompt_text.split(" ", 1)
        question = parts[1] if len(parts) > 1 else prompt_text
        self._input_field.setText(question)
        self._on_send()

    # ═══════════════════════════════════════════════════
    #  Markdown 解析
    # ═══════════════════════════════════════════════════

    def _parse_answer(self, text):
        parts = []
        pattern = r"```(\w*)\n(.*?)```"
        last = 0
        for m in re.finditer(pattern, text, re.DOTALL):
            before = text[last:m.start()].strip()
            if before:
                parts.append(
                    {"type": "text", "content": self._md2html(before)})
            parts.append(
                {"type": "code", "language": m.group(1) or "",
                 "content": m.group(2)})
            last = m.end()
        remaining = text[last:].strip()
        if remaining:
            parts.append(
                {"type": "text", "content": self._md2html(remaining)})
        if not parts:
            parts.append({"type": "text", "content": text})
        return parts

    def _md2html(self, text):
        text = text.replace("&", "&amp;").replace(
            "<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#F1F5F9; padding:1px 7px; '
            r'border-radius:5px; font-size:13px; color:#5B21B6;">\1</code>',
            text)
        text = text.replace("\n", "<br>")
        return text

    # ═══════════════════════════════════════════════════
    #  辅助
    # ═══════════════════════════════════════════════════

    def _add_to_chat(self, widget):
        if self._msg_layout.count() > 0:
            last = self._msg_layout.itemAt(self._msg_layout.count() - 1)
            if last.spacerItem():
                self._msg_layout.removeItem(last)
        self._msg_layout.addWidget(widget)
        self._msg_layout.addStretch()

    def _clear_messages(self):
        # 隐藏空状态提示
        if hasattr(self, '_empty_hint') and self._empty_hint:
            self._empty_hint.hide()
        while self._msg_layout.count():
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_messages(self):
        self._clear_messages()
        if not self._messages:
            if hasattr(self, '_empty_hint') and self._empty_hint:
                self._empty_hint.show()
            self._msg_layout.addStretch()
            return
        for m in self._messages:
            if m["role"] == "user":
                w = self._user_bubble(m["content"], m["ts"])
            else:
                w = self._ai_bubble(m["content"], m["ts"])
            self._msg_layout.addWidget(w)
        self._msg_layout.addStretch()
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._msg_scroll.verticalScrollBar(
        ).setValue(self._msg_scroll.verticalScrollBar().maximum()))

    def _copy(self, text):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
