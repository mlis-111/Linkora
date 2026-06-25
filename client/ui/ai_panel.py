"""
AI 问答面板
作者：董浩楠

面向全校师生的 AI 智能助手，覆盖课程学习、论文写作、考试复习、
校园生活、行政办事等垂直场景。
"""

import html
import time
import re
from datetime import datetime

from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QScrollArea, QFrame, QWidget, QFileDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from client.core.base_panel import BasePanel
from common.messages import MT

# ── 颜色 ─────────────────────────────────────────────
C_PURPLE        = "#7C5CFC"
C_PURPLE_LT     = "#EDE9FE"
C_PURPLE_DK     = "#5B21B6"
C_BLUE          = "#4F8DFD"
C_BLUE_DK       = "#2D6CF6"
C_BG            = "#EEF2FA"
C_SIDEBAR_BG    = "#F7F9FD"
C_HISTORY_BG    = "#F9FAFD"
C_CHAT_BG       = "#FAFBFE"
C_WHITE         = "#FFFFFF"
C_DARK          = "#1E293B"
C_SUBTLE        = "#94A3B8"
C_MUTED         = "#B0BAC8"
C_BORDER        = "#EEF1F7"
C_BORDER_STRONG = "#E5EAF3"
C_CODE_BG       = "#1E2A3A"
C_CODE_LABEL    = "#7C9EC8"
C_CODE_TEXT     = "#E2E8F0"

# ── 字号 ─────────────────────────────────────────────
FZ_SIDEBAR_TITLE = "40px"
FZ_HEADER        = "30px"
FZ_BODY          = "22px"
FZ_SUBTLE        = "20px"
FZ_SMALL         = "20px"
FZ_HISTORY_TITLE = "26px"
FZ_HISTORY_SUB   = "22px"
FZ_SEARCH        = "22px"
FZ_CODE          = "18px"


class AIPanel(BasePanel):
    """AI 问答面板"""

    def subscribe(self):
        self._messages = []
        self._conversations = []
        self._current_conv_idx = -1
        self._is_waiting = False
        self._cancelled = False
        self._history_loaded = False
        self._conv_id = int(time.time())  # 面板创建即生成 conv_id
        self.app.net.on(MT.AI_ANSWER, self._on_ai_answer)
        self.app.net.on(MT.AI_HISTORY_RESP, self._on_ai_history)
        self.app.net.on(MT.ERROR, self._on_server_error)
        self.app.net.on(MT.LOGIN_RESP, self._on_login_for_history)
        if self.app.state.user_id:
            self._load_history()
        self._build_ui()

    # ═══════════════════════════════════════════════════
    #  整体布局
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        self.setStyleSheet(f"background:{C_BG};")

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
        sidebar.setObjectName("HistorySidebar")
        sidebar.setFixedWidth(500)
        sidebar.setAutoFillBackground(True)
        sidebar.setStyleSheet(
            f"QFrame#HistorySidebar {{"
            f"background:{C_HISTORY_BG}; "
            f"border-right:1px solid {C_BORDER_STRONG};"
            f"}}"
            f"QFrame#HistorySidebar > QScrollArea {{"
            f"background:{C_HISTORY_BG};"
            f"}}"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题行
        title_row = QWidget()
        title_row.setStyleSheet(f"background:{C_HISTORY_BG};")
        tr_layout = QHBoxLayout(title_row)
        tr_layout.setContentsMargins(38, 56, 36, 36)
        tr_layout.setSpacing(0)

        title = QLabel("历史对话")
        title.setStyleSheet(
            f"font-size:{FZ_SIDEBAR_TITLE}; font-weight:800; color:{C_DARK};"
            f"background:transparent; border:none;"
        )
        tr_layout.addWidget(title)
        tr_layout.addStretch()

        add_btn = QPushButton("＋")
        add_btn.setFixedSize(56, 56)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_PURPLE_LT}; color:{C_PURPLE};
                border:none; border-radius:14px;
                font-size:36px; font-weight:700;
            }}
            QPushButton:hover {{ background:#DDD6FE; }}
        """)
        add_btn.clicked.connect(self._new_conversation)
        tr_layout.addWidget(add_btn)
        layout.addWidget(title_row)

        # 搜索框
        search_wrapper = QWidget()
        search_wrapper.setStyleSheet(f"background:{C_HISTORY_BG};")
        sw_layout = QHBoxLayout(search_wrapper)
        sw_layout.setContentsMargins(32, 0, 32, 28)
        sw_layout.setSpacing(0)

        search_box = QFrame()
        search_box.setFixedHeight(64)
        search_box.setStyleSheet(
            f"background:{C_WHITE}; border-radius:16px; "
            f"border:1px solid {C_BORDER_STRONG};"
        )
        sbl = QHBoxLayout(search_box)
        sbl.setContentsMargins(20, 0, 20, 0)
        sbl.setSpacing(14)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(
            "font-size:24px; background:transparent; border:none;")
        sbl.addWidget(search_icon)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索对话")
        self._search_input.setStyleSheet(
            f"border:none; background:transparent; "
            f"font-size:{FZ_SEARCH}; color:{C_DARK};"
        )
        sbl.addWidget(self._search_input)
        sw_layout.addWidget(search_box)
        layout.addWidget(search_wrapper)

        # 历史列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border:none; background:transparent; }"
            "QScrollBar:vertical { width:8px; background:transparent; }"
            "QScrollBar::handle:vertical { "
            "  background:#CBD5E1; border-radius:4px; "
            "  min-height:24px; }"
            "QScrollBar::add-line:vertical, "
            "QScrollBar::sub-line:vertical { height:0px; }"
        )

        self._history_content = QWidget()
        self._history_content.setStyleSheet(
            f"background:{C_HISTORY_BG};")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(20, 0, 20, 24)
        self._history_layout.setSpacing(8)
        self._history_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._history_content)
        layout.addWidget(scroll, 1)

        self._history_layout.addStretch()
        self._refresh_history()
        return sidebar

    def _create_history_item(self, title_text, subtitle, index, active=False):
        item = QFrame()
        item.setObjectName("HistoryItem")
        item.setProperty("conv_index", index)
        item.setProperty("active", "true" if active else "false")
        item.setCursor(Qt.PointingHandCursor)
        item.mousePressEvent = lambda e: self._on_history_click(index)
        item.setStyleSheet(f"""
            QFrame#HistoryItem {{
                padding:20px;
                border-radius:18px;
                background:transparent;
            }}
            QFrame#HistoryItem[active="true"] {{
                background:{C_PURPLE_LT};
            }}
            QFrame#HistoryItem:hover {{
                background:{"rgba(237,233,254,0.6)" if not active else C_PURPLE_LT};
            }}
        """)

        il = QVBoxLayout(item)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(10)

        tl = QLabel(title_text)
        tl.setObjectName("HistoryTitle")
        tl.setStyleSheet(
            f"font-size:{FZ_HISTORY_TITLE}; "
            f"font-weight:{'700' if active else '600'}; "
            f"color:{C_PURPLE_DK if active else C_DARK}; "
            f"background:transparent; border:none;"
        )
        il.addWidget(tl)

        sl = QLabel(subtitle)
        sl.setObjectName("HistorySub")
        sl.setStyleSheet(
            f"font-size:{FZ_HISTORY_SUB}; "
            f"color:{C_PURPLE if active else C_SUBTLE}; "
            f"background:transparent; border:none;"
        )
        il.addWidget(sl)
        return item

    # ═══════════════════════════════════════════════════
    #  聊天头部
    # ═══════════════════════════════════════════════════

    def _create_header(self):
        header = QFrame()
        header.setObjectName("ChatHeader")
        header.setFixedHeight(150)
        header.setStyleSheet(
            f"QFrame#ChatHeader {{"
            f"background:{C_SIDEBAR_BG}; "
            f"border-bottom:1px solid {C_BORDER};"
            f"}}"
        )

        hl = QHBoxLayout(header)
        hl.setContentsMargins(64, 42, 64, 0)
        hl.setSpacing(24)

        avatar = QLabel("✨")
        avatar.setFixedSize(68, 68)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #A78BFA, stop:1 {C_PURPLE});
            color:white; border-radius:34px; font-size:34px;
        """)
        hl.addWidget(avatar, alignment=Qt.AlignTop)

        info_col = QVBoxLayout()
        info_col.setSpacing(0)

        name_row = QHBoxLayout()
        name_row.setSpacing(16)

        name = QLabel("AI 助手")
        name.setStyleSheet(
            f"font-size:{FZ_HEADER}; font-weight:800; color:{C_DARK};"
            f"background:transparent; border:none;"
        )
        name_row.addWidget(name)

        badge = QLabel("智能问答")
        badge.setFixedHeight(28)
        badge.setStyleSheet(f"""
            font-size:{FZ_SMALL}; font-weight:700; color:{C_PURPLE};
            background:{C_PURPLE_LT}; padding:4px 12px; border-radius:9px;
        """)
        name_row.addWidget(badge)
        name_row.addStretch()
        info_col.addLayout(name_row)

        subtitle = QLabel("课程答疑 · 论文润色 · 复习规划 · 校园办事指南")
        subtitle.setStyleSheet(
            f"font-size:{FZ_SUBTLE}; color:{C_SUBTLE};"
            f"background:transparent; border:none;"
            f"margin-top:-18px;"
        )
        info_col.addWidget(subtitle)

        hl.addLayout(info_col)
        hl.addStretch()

        new_btn = QPushButton("+ 新对话")
        new_btn.setFixedHeight(65)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_PURPLE_LT}; color:{C_PURPLE};
                border:none; border-radius:16px;
                font-size:23px; font-weight:600;
                padding:0 26px;
            }}
            QPushButton:hover {{ background:#DDD6FE; }}
        """)
        new_btn.clicked.connect(self._new_conversation)
        hl.addWidget(new_btn, alignment=Qt.AlignTop)

        return header

    # ═══════════════════════════════════════════════════
    #  消息区域
    # ═══════════════════════════════════════════════════

    def _create_messages_area(self):
        self._msg_scroll = QScrollArea()
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._msg_scroll.setStyleSheet(
            f"QScrollArea {{ border:none; background:{C_WHITE}; }}"
            "QScrollBar:vertical { width:8px; background:transparent; }"
            "QScrollBar::handle:vertical { "
            "  background:rgba(100,116,139,0.22); border-radius:4px; "
            "  min-height:24px; }"
            "QScrollBar::add-line:vertical, "
            "QScrollBar::sub-line:vertical { height:0px; }"
        )

        self._msg_content = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_content)
        self._msg_layout.setContentsMargins(48, 68, 48, 68)
        self._msg_layout.setSpacing(34)
        self._msg_layout.setAlignment(Qt.AlignTop)
        self._msg_scroll.setWidget(self._msg_content)

        self._empty_hint = QLabel(
            "<div style='text-align:center; padding:100px 0;'>"
            "<div style='font-size:68px; margin-bottom:36px;'>✨</div>"
            "<div style='font-size:30px; font-weight:700; color:#64748B;'>"
            "校园 AI 智能助手</div>"
            "<div style='font-size:22px; color:#94A3B8; margin-top:18px;'>"
            "课程答疑 · 论文润色 · 复习规划 · 校园办事指南</div>"
            "</div>"
        )
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._msg_layout.addStretch()
        self._msg_layout.addWidget(self._empty_hint)
        self._msg_layout.addStretch()

        return self._msg_scroll

    # ═══════════════════════════════════════════════════
    #  底部输入区
    # ═══════════════════════════════════════════════════

    def _create_composer(self):
        composer = QFrame()
        composer.setObjectName("Composer")
        composer.setStyleSheet(f"QFrame#Composer {{ background:{C_BG}; }}")

        cl = QVBoxLayout(composer)
        cl.setContentsMargins(40, 28, 40, 32)
        cl.setSpacing(20)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(16)

        prompts = [
            "📖 帮我解释课程知识点",
            "✍️ 润色论文摘要",
            "📅 制定期末复习计划",
            "🏫 校园办事流程咨询",
        ]
        for p in prompts:
            chip = QPushButton(p)
            chip.setObjectName("QuickChip")
            chip.setFixedHeight(44)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(f"""
                QPushButton#QuickChip {{
                    font-size:{FZ_SUBTLE}; color:{C_SUBTLE};
                    background:{C_WHITE}; border:1.5px solid {C_BORDER_STRONG};
                    border-radius:28px; padding:0 20px;
                }}
                QPushButton#QuickChip:hover {{
                    background:{C_PURPLE_LT}; border-color:{C_PURPLE};
                    color:{C_PURPLE};
                }}
            """)
            chip.clicked.connect(lambda _, x=p: self._send_quick(x))
            quick_row.addWidget(chip)
        quick_row.addStretch()
        cl.addLayout(quick_row)

        input_card = QFrame()
        input_card.setObjectName("InputCard")
        input_card.setStyleSheet(
            f"QFrame#InputCard {{"
            f"background:{C_WHITE}; border-radius:28px;"
            f"}}"
        )

        icl = QHBoxLayout(input_card)
        icl.setContentsMargins(24, 20, 16, 20)
        icl.setSpacing(20)

        self._input_field = QLineEdit()
        self._input_field.setObjectName("InputField")
        self._input_field.setPlaceholderText(
            "问我课程学习、论文写作和校园生活方面的问题…")
        self._input_field.setMinimumHeight(40)
        self._input_field.setStyleSheet(
            f"border:none; background:transparent; "
            f"font-size:{FZ_BODY}; color:{C_DARK}; "
            f"padding:4px 6px;"
        )
        self._input_field.returnPressed.connect(self._on_send)
        icl.addWidget(self._input_field, 1)

        self._attach_btn = QPushButton("📎")
        self._attach_btn.setFixedSize(56, 56)
        self._attach_btn.setCursor(Qt.PointingHandCursor)
        self._attach_btn.setToolTip("添加附件")
        self._attach_btn.clicked.connect(self._pick_attachment)
        self._attach_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C_SIDEBAR_BG}; color:{C_SUBTLE};
                border:none; border-radius:16px; font-size:28px;
            }}
            QPushButton:hover {{ background:#E2E8F0; }}
        """)
        icl.addWidget(self._attach_btn)

        # 附件标签
        self._attach_label = QLabel("")
        self._attach_label.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_PURPLE}; background:transparent; padding:4px 20px;")
        self._attach_label.hide()
        cl.addWidget(self._attach_label)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(64, 64)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send_click)
        icl.addWidget(self._send_btn)
        self._update_send_btn(sending=False)

        cl.addWidget(input_card)
        return composer

    # ═══════════════════════════════════════════════════
    #  用户消息气泡
    # ═══════════════════════════════════════════════════

    def _user_bubble(self, text, ts_str):
        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")

        lo = QHBoxLayout(wrapper)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(20)

        lo.addStretch()

        content_col = QWidget()
        ccl = QVBoxLayout(content_col)
        ccl.setContentsMargins(0, 0, 0, 0)
        ccl.setSpacing(10)
        ccl.setAlignment(Qt.AlignRight)

        time_lbl = QLabel(ts_str)
        time_lbl.setAlignment(Qt.AlignRight)
        time_lbl.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_SUBTLE};"
            f"background:transparent; border:none;"
        )
        ccl.addWidget(time_lbl)

        bubble = QFrame()
        bubble.setObjectName("UserBubble")
        bubble.setStyleSheet(f"""
            QFrame#UserBubble {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {C_BLUE}, stop:1 {C_BLUE_DK});
                border-radius:26px;
                border-top-right-radius:7px;
                padding:22px 28px;
            }}
        """)

        bbl = QVBoxLayout(bubble)
        bbl.setContentsMargins(0, 0, 0, 0)

        bubble_text = QLabel(text)
        bubble_text.setObjectName("UserBubbleText")
        bubble_text.setWordWrap(True)
        bubble_text.setMaximumWidth(1280)
        bubble_text.setTextFormat(Qt.PlainText)
        bubble_text.setStyleSheet(
            f"color:{C_WHITE}; font-size:{FZ_BODY}; "
            f"background:transparent; border:none;"
        )
        bbl.addWidget(bubble_text)
        ccl.addWidget(bubble, alignment=Qt.AlignRight)
        lo.addWidget(content_col)

        avatar = QLabel("我")
        avatar.setFixedSize(60, 60)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {C_BLUE_DK}, stop:1 #1E4FD0);
            color:white; border-radius:30px;
            font-size:26px; font-weight:700;
        """)
        lo.addWidget(avatar, alignment=Qt.AlignTop)

        return wrapper

    # ═══════════════════════════════════════════════════
    #  AI 消息气泡
    # ═══════════════════════════════════════════════════

    def _ai_bubble(self, text, ts_str):
        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")

        lo = QHBoxLayout(wrapper)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(20)

        avatar = QLabel("✨")
        avatar.setFixedSize(60, 60)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #A78BFA, stop:1 {C_PURPLE});
            color:white; border-radius:30px;
            font-size:30px;
        """)
        lo.addWidget(avatar, alignment=Qt.AlignTop)

        content_col = QWidget()
        ccl = QVBoxLayout(content_col)
        ccl.setContentsMargins(0, 0, 0, 0)
        ccl.setSpacing(10)

        info_lbl = QLabel(f"AI 助手 · {ts_str}")
        info_lbl.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_SUBTLE};"
            f"background:transparent; border:none;"
        )
        ccl.addWidget(info_lbl)

        bubble = QFrame()
        bubble.setObjectName("AIBubble")
        bubble.setStyleSheet(f"""
            QFrame#AIBubble {{
                background:{C_WHITE};
                border-radius:26px;
                border-top-left-radius:7px;
                padding:22px 28px;
            }}
        """)

        bbl = QVBoxLayout(bubble)
        bbl.setContentsMargins(0, 0, 0, 0)

        bubble_text = QLabel(self._md2html(text))
        bubble_text.setObjectName("AIBubbleText")
        bubble_text.setWordWrap(True)
        bubble_text.setMaximumWidth(1360)
        bubble_text.setTextFormat(Qt.RichText)
        bubble_text.setStyleSheet(
            f"color:{C_DARK}; font-size:{FZ_BODY}; "
            f"background:transparent; border:none;"
        )
        bbl.addWidget(bubble_text)
        ccl.addWidget(bubble)

        lo.addWidget(content_col)
        lo.addStretch()
        return wrapper

    # ═══════════════════════════════════════════════════
    #  代码块
    # ═══════════════════════════════════════════════════

    def _code_block(self, language, code_text):
        block = QFrame()
        block.setObjectName("CodeBlock")
        block.setStyleSheet(f"""
            QFrame#CodeBlock {{
                background:{C_CODE_BG};
                border-radius:22px;
                border-top-left-radius:7px;
                padding:22px 24px;
            }}
        """)
        block.setMaximumWidth(1360)

        bl = QVBoxLayout(block)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(16)

        top_row = QHBoxLayout()
        top_row.setSpacing(0)

        lang_lbl = QLabel(language if language else "Code")
        lang_lbl.setStyleSheet(
            f"font-size:{FZ_SMALL}; font-family:Consolas,monospace; "
            f"font-weight:600; color:{C_CODE_LABEL}; "
            f"background:transparent; border:none;"
        )
        top_row.addWidget(lang_lbl)
        top_row.addStretch()

        copy_btn = QPushButton("📋 复制")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(
            "QPushButton { color:#7C9EC8; background:transparent; border:none;"
            "font-size:15px; }"
            "QPushButton:hover { color:#A0C8F0; }"
        )
        copy_btn.clicked.connect(lambda: self._copy(code_text))
        top_row.addWidget(copy_btn)
        bl.addLayout(top_row)

        code_lbl = QLabel(code_text)
        code_lbl.setTextFormat(Qt.PlainText)
        code_lbl.setWordWrap(False)
        code_lbl.setStyleSheet(
            f"font-family:'Consolas','Courier New',monospace; "
            f"font-size:{FZ_CODE}; color:{C_CODE_TEXT}; "
            f"background:transparent; border:none;"
            f"line-height:1.75;"
        )
        bl.addWidget(code_lbl)

        return block

    # ═══════════════════════════════════════════════════
    #  日期分隔线
    # ═══════════════════════════════════════════════════

    def _date_divider(self, text):
        divider = QLabel(text)
        divider.setAlignment(Qt.AlignCenter)
        divider.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_SUBTLE}; "
            f"background:{C_BORDER_STRONG}; "
            f"padding:8px 20px; border-radius:14px;"
        )
        return divider

    # ═══════════════════════════════════════════════════
    #  发送 & 接收
    # ═══════════════════════════════════════════════════

    def _on_send_click(self):
        """按钮点击路由：正常发送或停止生成"""
        if self._is_waiting:
            self._stop_streaming()
        else:
            self._on_send()

    def _update_send_btn(self, sending):
        """切换发送按钮的样式：发送（紫色箭头） / 停止（红色方块）"""
        if sending:
            self._send_btn.setText("■")
            self._send_btn.setStyleSheet(f"""
                QPushButton {{
                    background:#EF4444; color:white;
                    border:none; border-radius:22px;
                    font-size:26px;
                }}
                QPushButton:hover {{ background:#DC2626; }}
            """)
        else:
            self._send_btn.setText("➤")
            self._send_btn.setStyleSheet(f"""
                QPushButton {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #A78BFA, stop:1 {C_PURPLE});
                    color:white; border:none; border-radius:22px;
                    font-size:30px;
                }}
                QPushButton:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 #9677EA, stop:1 #6B4CEC);
                }}
            """)

    def _stop_streaming(self):
        """用户主动停止当前 AI 生成"""
        self._cancelled = True
        self._is_waiting = False
        self._update_send_btn(sending=False)

        if self._stream_full:
            ts_str = datetime.now().strftime("%H:%M")
            self._messages.append(
                {"role": "ai", "content": self._stream_full + "…", "ts": ts_str})

        self._stream_container = None
        self._stream_bubble = None
        self._stream_full = ""

        self._save_current_conv()
        self._refresh_history()

    def _pick_attachment(self):
        """选择附件文件（排除图片/视频/PPT/音乐）"""
        import os
        path, _ = QFileDialog.getOpenFileName(
            self, "选择附件", "",
            "文档/代码 (*.txt *.md *.py *.java *.c *.cpp *.js *.ts *.html *.css "
            "*.json *.xml *.csv *.log *.sql *.docx *.pdf *.xlsx);;所有文件 (*)")
        if not path:
            return
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        blacklist = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                     '.mp4', '.avi', '.mov', '.mkv', '.mp3', '.wav', '.flac',
                     '.ppt', '.pptx', '.zip', '.rar', '.7z', '.exe'}
        if ext in blacklist:
            self._attach_label.setText(f"❌ 不支持的文件类型: {ext}")
            self._attach_label.setStyleSheet(
                f"font-size:{FZ_SMALL}; color:#FB7185; background:transparent; padding:4px 20px;")
            self._attach_label.show()
            return
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            try:
                with open(path, 'r', encoding='latin-1', errors='replace') as f:
                    content = f.read()
            except Exception:
                self._attach_label.setText("❌ 无法读取此文件")
                self._attach_label.setStyleSheet(
                    f"font-size:{FZ_SMALL}; color:#FB7185; background:transparent; padding:4px 20px;")
                self._attach_label.show()
                return
        if len(content) > 8000:
            content = content[:8000] + "\n...(内容已截断)"
        self._attached_name = name
        self._attached_content = content
        self._attach_label.setText(f"📎 已附加: {name}")
        self._attach_label.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_PURPLE}; background:transparent; padding:4px 20px;")
        self._attach_label.show()

    def _on_send(self):
        text = self._input_field.text().strip()
        if not text or self._is_waiting:
            return

        if not self.app.state.user_id:
            self._input_field.clear()
            if not self._messages:
                self._clear_messages()
            hint = "请先登录后再使用 AI 助手"
            ts_str = datetime.now().strftime("%H:%M")
            self._messages.append(
                {"role": "ai", "content": hint, "ts": ts_str})
            self._add_to_chat(self._ai_bubble(hint, ts_str))
            return

        self._input_field.clear()

        if not self._messages:
            self._clear_messages()

        ts = int(time.time())
        ts_str = datetime.now().strftime("%H:%M")

        self._messages.append({"role": "user", "content": text, "ts": ts_str})
        self._add_to_chat(self._user_bubble(text, ts_str))

        self._is_waiting = True
        self._cancelled = False
        self._update_send_btn(sending=True)

        self._stream_full = ""
        self._stream_container = None
        self._stream_bubble = None

        # 立即构建带头像的容器，用思考文案占位
        self._stream_container = self._build_streaming_container()
        if self._stream_bubble:
            self._stream_bubble.setText("AI 正在思考…")
        self._add_to_chat(self._stream_container)

        payload = {"type": MT.AI_ASK, "question": text, "ts": ts,
                   "conv_id": self._conv_id}
        attached = getattr(self, '_attached_name', None)
        if attached:
            payload["attachment_name"] = self._attached_name
            payload["attachment"] = self._attached_content
            self._attached_name = None
            self._attached_content = None
            self._attach_label.hide()
        self.net.send(payload)

    def _on_server_error(self, msg):
        self._is_waiting = False
        self._cancelled = True
        self._update_send_btn(sending=False)

        error_text = msg.get("message", "AI 服务暂时不可用")
        ts_str = datetime.now().strftime("%H:%M")
        self._messages.append(
            {"role": "ai", "content": error_text, "ts": ts_str})
        self._add_to_chat(self._ai_bubble(error_text, ts_str))

    # ═══════════════════════════════════════════════════
    #  历史记录加载
    # ═══════════════════════════════════════════════════

    def _on_login_for_history(self, msg):
        """登录成功后自动拉取 AI 历史"""
        if msg.get("ok") and not self._history_loaded:
            self._load_history()

    def _load_history(self):
        """向服务器请求 AI 历史记录"""
        if self._history_loaded:
            return
        self._history_loaded = True
        self.net.send({"type": MT.AI_HISTORY_REQ})

    def _on_ai_history(self, msg):
        """收到服务器返回的 AI 历史记录（已按 conv_id 分组）"""
        conversations = msg.get("conversations", [])
        if not conversations:
            return

        self._conversations = []
        for c in conversations:
            conv_msgs = []
            for r in c.get("messages", []):
                role = "user" if r["sender_id"] == self.app.state.user_id else "ai"
                ts = r.get("ts", 0)
                ts_str = (datetime.fromtimestamp(ts).strftime("%H:%M")
                          if ts else datetime.now().strftime("%H:%M"))
                conv_msgs.append({
                    "role": role,
                    "content": r["content"],
                    "ts": ts_str,
                })

            if conv_msgs:
                first_ts = c["messages"][0].get("ts", 0)
                date_str = (datetime.fromtimestamp(first_ts).strftime("%m/%d")
                            if first_ts else datetime.now().strftime("%m/%d"))
                self._conversations.append({
                    "conv_id": c["conv_id"],
                    "title": c.get("title", "新对话")[:24],
                    "date": date_str,
                    "messages": conv_msgs,
                    "preview_count": len(conv_msgs),
                })

        # 显示最近一个对话
        self._current_conv_idx = len(self._conversations) - 1
        self._conv_id = self._conversations[self._current_conv_idx]["conv_id"]
        self._messages = list(self._conversations[self._current_conv_idx]["messages"])
        self._refresh_history()
        self._refresh_messages()

    def _on_ai_answer(self, msg):
        if self._cancelled:
            return

        is_chunk = msg.get("chunk", False)
        is_done = msg.get("done", False)

        if is_chunk:
            delta = msg.get("answer", "")
            if not delta:
                return

            self._stream_full += delta
            if self._stream_bubble is not None:
                # 流式过程中实时渲染 Markdown → HTML
                self._stream_bubble.setText(self._md2html(self._stream_full))
                self._scroll_to_bottom()
            return

        if is_done:
            self._is_waiting = False
            self._cancelled = False
            self._update_send_btn(sending=False)

            # 回写 conv_id（如果客户端还没设，就用服务端返回的）
            if msg.get("conv_id") and not self._conv_id:
                self._conv_id = msg["conv_id"]

            ts_str = datetime.now().strftime("%H:%M")
            self._messages.append(
                {"role": "ai", "content": self._stream_full, "ts": ts_str})

            # 替换流式容器为完整解析版（含代码块样式）
            if self._stream_container is not None:
                parts = self._parse_answer(self._stream_full)
                parsed_container = self._build_ai_answer_container(ts_str, parts)
                self._replace_last_widget(parsed_container)

            self._stream_container = None
            self._stream_bubble = None

            # 每次 AI 回答完毕，自动保存到历史
            self._save_current_conv()
            self._refresh_history()
            return

        # 非流式（兼容旧版）
        self._is_waiting = False
        self._cancelled = False
        self._update_send_btn(sending=False)

        answer = msg.get("answer", "抱歉，我没有理解你的问题。")
        ts_val = msg.get("ts", int(time.time()))
        ts_str = (datetime.fromtimestamp(ts_val).strftime("%H:%M")
                  if isinstance(ts_val, (int, float))
                  else datetime.now().strftime("%H:%M"))

        self._messages.append(
            {"role": "ai", "content": answer, "ts": ts_str})

        parts = self._parse_answer(answer)
        container = self._build_ai_answer_container(ts_str, parts)
        self._add_to_chat(container)
        self._scroll_to_bottom()

    def _build_streaming_container(self):
        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")

        lo = QHBoxLayout(wrapper)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(20)

        avatar = QLabel("✨")
        avatar.setFixedSize(60, 60)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #A78BFA, stop:1 {C_PURPLE});
            color:white; border-radius:30px;
            font-size:30px;
        """)
        lo.addWidget(avatar, alignment=Qt.AlignTop)

        content_col = QWidget()
        ccl = QVBoxLayout(content_col)
        ccl.setContentsMargins(0, 0, 0, 0)
        ccl.setSpacing(10)

        info_lbl = QLabel("AI 助手")
        info_lbl.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_SUBTLE};"
            f"background:transparent; border:none;"
        )
        ccl.addWidget(info_lbl)

        bubble = QFrame()
        bubble.setObjectName("AIBubble")
        bubble.setStyleSheet(f"""
            QFrame#AIBubble {{
                background:{C_WHITE};
                border-radius:26px;
                border-top-left-radius:7px;
                padding:22px 28px;
            }}
        """)
        bbl = QVBoxLayout(bubble)
        bbl.setContentsMargins(0, 0, 0, 0)

        bt = QLabel("")
        bt.setObjectName("AIBubbleText")
        bt.setWordWrap(True)
        bt.setMaximumWidth(1360)
        bt.setTextFormat(Qt.RichText)
        bt.setStyleSheet(
            f"color:{C_DARK}; font-size:{FZ_BODY};"
            f"background:transparent; border:none;"
        )
        bbl.addWidget(bt)
        ccl.addWidget(bubble)

        lo.addWidget(content_col)
        lo.addStretch()

        self._stream_bubble = bt
        return wrapper

    def _build_ai_answer_container(self, ts_str, parts):
        container = QWidget()
        container.setStyleSheet("background:transparent;")

        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)

        hr = QHBoxLayout()
        hr.setSpacing(20)

        avatar = QLabel("✨")
        avatar.setFixedSize(60, 60)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #A78BFA, stop:1 {C_PURPLE});
            color:white; border-radius:30px;
            font-size:30px;
        """)
        hr.addWidget(avatar, alignment=Qt.AlignTop)

        info = QLabel(f"AI 助手 · {ts_str}")
        info.setStyleSheet(
            f"font-size:{FZ_SMALL}; color:{C_SUBTLE};"
            f"background:transparent; border:none;"
        )
        hr.addWidget(info)
        hr.addStretch()
        cl.addLayout(hr)

        for part in parts:
            if part["type"] == "text":
                bubble = QFrame()
                bubble.setObjectName("AIBubble")
                bubble.setStyleSheet(f"""
                    QFrame#AIBubble {{
                        background:{C_WHITE};
                        border-radius:26px;
                        border-top-left-radius:7px;
                        padding:22px 28px;
                    }}
                """)
                bbl = QVBoxLayout(bubble)
                bbl.setContentsMargins(0, 0, 0, 0)
                bt = QLabel(part["content"])
                bt.setObjectName("AIBubbleText")
                bt.setWordWrap(True)
                bt.setMaximumWidth(1360)
                bt.setTextFormat(Qt.RichText)
                bt.setStyleSheet(
                    f"color:{C_DARK}; font-size:{FZ_BODY};"
                    f"background:transparent; border:none;"
                )
                bbl.addWidget(bt)
                # 用水平 layout + stretch 约束气泡宽度，防止撑满整行
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(bubble)
                row.addStretch()
                cl.addLayout(row)
            elif part["type"] == "code":
                code_row = QHBoxLayout()
                code_row.setContentsMargins(0, 0, 0, 0)
                code_row.addWidget(self._code_block(
                    part.get("language", ""), part["content"]))
                code_row.addStretch()
                cl.addLayout(code_row)
            elif part["type"] == "math":
                math_row = QHBoxLayout()
                math_row.setContentsMargins(0, 0, 0, 0)
                math_row.addWidget(self._math_block(part["content"]))
                math_row.addStretch()
                cl.addLayout(math_row)

        return container

    def _send_quick(self, prompt_text):
        parts = prompt_text.split(" ", 1)
        question = parts[1] if len(parts) > 1 else prompt_text
        self._input_field.setText(question)
        self._on_send()

    def _on_history_click(self, index):
        """点击历史条目，切换到该对话"""
        if index < 0 or index >= len(self._conversations):
            return
        if index == self._current_conv_idx:
            return

        if self._is_waiting:
            self._stop_streaming()

        # 先记住目标对话引用，因为 _save_current_conv 可能改变列表结构
        target_conv = self._conversations[index]

        self._save_current_conv()

        # 保存后重新定位目标对话
        try:
            new_index = self._conversations.index(target_conv)
        except ValueError:
            new_index = self._conversations.index(target_conv) if target_conv in self._conversations else 0

        self._messages = list(target_conv["messages"])
        self._current_conv_idx = new_index
        self._conv_id = target_conv.get("conv_id")
        self._refresh_history()
        self._refresh_messages()

    def _save_current_conv(self):
        """把当前 _messages 保存到 _conversations 对应位置"""
        if not self._messages:
            return

        title = ""
        for m in self._messages:
            if m["role"] == "user":
                title = m["content"][:24]
                break
        if not title:
            title = "空对话"

        if self._current_conv_idx >= 0:
            # 更新已有记录
            conv = self._conversations[self._current_conv_idx]
            conv["title"] = title
            conv["date"] = datetime.now().strftime("%m/%d")
            conv["messages"] = list(self._messages)
            conv["preview_count"] = len(self._messages)
        else:
            # 新记录，插入最前
            entry = {
                "conv_id": self._conv_id,
                "title": title,
                "date": datetime.now().strftime("%m/%d"),
                "messages": list(self._messages),
                "preview_count": len(self._messages),
            }
            self._conversations.insert(0, entry)
            self._current_conv_idx = 0

    def _new_conversation(self):
        if self._is_waiting:
            self._stop_streaming()

        self._save_current_conv()
        self._refresh_history()

        self._messages = []
        self._current_conv_idx = -1
        self._conv_id = int(time.time())  # 生成新 conv_id
        self._is_waiting = False
        self._cancelled = False
        self._refresh_messages()

    def _refresh_history(self):
        """根据 _conversations 重建左侧历史列表"""
        # 移除 stretch（最后一个 item）
        last = self._history_layout.count() - 1
        if last >= 0:
            item = self._history_layout.itemAt(last)
            if item and item.spacerItem():
                self._history_layout.removeItem(item)

        # 清空剩余 widget
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 重建列表
        for i, conv in enumerate(self._conversations):
            subtitle = f"{conv['date']} · {conv['preview_count']} 条消息"
            self._history_layout.addWidget(
                self._create_history_item(
                    conv["title"], subtitle, i, active=(i == self._current_conv_idx)))

        self._history_layout.addStretch()

    # ═══════════════════════════════════════════════════
    #  Markdown 解析
    # ═══════════════════════════════════════════════════

    # ── 预编译的正则 ──
    _RE_CODE_BLOCK = re.compile(r"```(\w*)\s*\n(.*?)```", re.DOTALL)

    # 数学环境名（不含 * 后缀，下面会拼 \*? ）
    _MATH_ENVS = (
        "equation|align|aligned|gather|eqnarray|displaymath|"
        "cases|array|split|multline|"
        "pmatrix|bmatrix|vmatrix|Vmatrix|matrix|Bmatrix|"
        "smallmatrix|subarray|gathered|alignedat"
    )
    # $$...$$ 或 \[...\] 或 \begin{env}...\end{env}
    _RE_DISPLAY_MATH = re.compile(
        r"(?:\$\$|\\\[|\\begin\{(" + _MATH_ENVS + r")(\*?)\})"
        r"\s*\n?"
        r"(.*?)"
        r"(?:\$\$|\\\]|\\end\{\1\2\})",
        re.DOTALL)

    def _parse_answer(self, text):
        """将 AI 回答按 代码块 / LaTeX 数学块 拆分为片段"""
        # 收集所有 match（代码块 + 数学块），按位置排序
        matches = []
        for m in self._RE_CODE_BLOCK.finditer(text):
            matches.append((m.start(), m.end(), "code", m))
        for m in self._RE_DISPLAY_MATH.finditer(text):
            # 排除和代码块重叠的（$$ 可能在 ``` 内部）
            if not any(c_start <= m.start() < c_end for c_start, c_end, _, _ in matches):
                matches.append((m.start(), m.end(), "math", m))
        matches.sort(key=lambda x: x[0])

        parts = []
        last = 0
        for start, end, kind, m in matches:
            before = text[last:start].strip()
            if before:
                parts.append(
                    {"type": "text", "content": self._md2html(before)})
            if kind == "code":
                parts.append(
                    {"type": "code", "language": m.group(1) or "",
                     "content": m.group(2).rstrip()})
            else:
                content = m.group(3).strip()  # group 3 = (.*?) 数学内容
                parts.append(
                    {"type": "math", "content": content})
            last = end
        remaining = text[last:].strip()
        if remaining:
            parts.append(
                {"type": "text", "content": self._md2html(remaining)})
        if not parts:
            parts.append({"type": "text", "content": self._md2html(text)})
        return parts

    def _md2html(self, text):
        """Markdown → HTML，支持标题/列表/引用/粗斜体/删除线/代码/链接/表格/任务列表/分割线"""
        text = text.strip()
        if not text:
            return ""
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines = text.split("\n")
        out = []
        in_ul, in_ol, in_quote, in_code_block = False, False, False, False
        code_lang = ""
        last_was_br = False  # 合并连续 <br>

        # 块级元素样式（压缩 Qt RichText 默认边距）
        P_STYLE   = "margin:0 0 4px 0;"
        H1_STYLE  = "margin:12px 0 4px 0; font-size:28px; font-weight:800;"
        H2_STYLE  = "margin:10px 0 3px 0; font-size:26px; font-weight:700;"
        H3_STYLE  = "margin:8px 0 2px 0; font-size:24px; font-weight:700;"
        H4_STYLE  = "margin:6px 0 2px 0; font-size:23px; font-weight:600;"

        i = 0
        while i < len(lines):
            line = lines[i]

            # ── 代码块（```fence```） ──
            if line.strip().startswith("```"):
                if not in_code_block:
                    if in_ul: out.append("</ul>"); in_ul = False
                    if in_ol: out.append("</ol>"); in_ol = False
                    if in_quote: out.append("</blockquote>"); in_quote = False
                    code_lang = line.strip()[3:].strip()
                    in_code_block = True
                    last_was_br = False
                    out.append(
                        '<pre style="background:#1E2A3A;color:#E2E8F0;'
                        'border-radius:22px;border-top-left-radius:7px;'
                        'padding:22px 24px;margin:8px 0;'
                        'font-family:Consolas,monospace;font-size:18px;'
                        'overflow-x:auto;line-height:1.75;">')
                    if code_lang:
                        out.append(
                            f'<div style="color:#7C9EC8;font-size:15px;'
                            f'font-weight:600;margin-bottom:12px;">'
                            f'{code_lang}</div>')
                    i += 1
                    continue
                else:
                    out.append("</pre>")
                    in_code_block = False
                    code_lang = ""
                    last_was_br = False
                    i += 1
                    continue

            if in_code_block:
                out.append(line + "\n")
                i += 1
                continue

            # LaTeX display math：$$...$$ / \[...\] / \begin{env}...\end{env}
            stripped = line.strip()
            math_env_name = ""      # 若是 \begin{env} 则为 env 名
            math_close_delim = ""   # 对应的闭合定界符
            math_open_len = 0

            if stripped.startswith('$$'):
                math_close_delim = '$$'
                math_open_len = 2
            elif stripped.startswith('\\['):
                math_close_delim = '\\]'
                math_open_len = 2
            else:
                # 匹配 \begin{env} 或 \begin{env*}
                m_begin = re.match(
                    r"\\begin\{((?:equation|align|aligned|gather|eqnarray|displaymath|"
                    r"cases|array|split|multline|"
                    r"pmatrix|bmatrix|vmatrix|Vmatrix|matrix|Bmatrix|"
                    r"smallmatrix|subarray|gathered|alignedat)\*?)\}(.*)",
                    stripped)
                if m_begin:
                    math_env_name = m_begin.group(1)
                    math_close_delim = '\\end{' + math_env_name + '}'
                    # 单行 \begin{env} ... \end{env}
                    rest = m_begin.group(2)
                    if math_close_delim in rest:
                        # 单行 math 块
                        math_content = rest[:rest.rfind(math_close_delim)].strip()
                        if in_ul: out.append('</ul>'); in_ul = False
                        if in_ol: out.append('</ol>'); in_ol = False
                        if in_quote: out.append('</blockquote>'); in_quote = False
                        out.append(self._build_math_html(math_content))
                        last_was_br = False
                        i += 1
                        continue

            if math_close_delim:
                # 单行闭合？
                if math_env_name:
                    # \begin{env} 单行已在上方处理，这里处理多行
                    if in_ul: out.append('</ul>'); in_ul = False
                    if in_ol: out.append('</ol>'); in_ol = False
                    if in_quote: out.append('</blockquote>'); in_quote = False
                    math_lines = []
                    i += 1
                    while i < len(lines):
                        if lines[i].strip() == math_close_delim:
                            break
                        math_lines.append(lines[i])
                        i += 1
                    out.append(self._build_math_html('\n'.join(math_lines)))
                    last_was_br = False
                    i += 1
                    continue
                elif stripped.endswith(math_close_delim) and len(stripped) > math_open_len + len(math_close_delim):
                    # 单行 $$...$$ 或 \[...\]
                    if in_ul: out.append('</ul>'); in_ul = False
                    if in_ol: out.append('</ol>'); in_ol = False
                    if in_quote: out.append('</blockquote>'); in_quote = False
                    math = stripped[math_open_len:-len(math_close_delim)].strip()
                    out.append(self._build_math_html(math))
                    last_was_br = False
                    i += 1
                    continue
                else:
                    # 多行 $$...$$ 或 \[...\]
                    if in_ul: out.append('</ul>'); in_ul = False
                    if in_ol: out.append('</ol>'); in_ol = False
                    if in_quote: out.append('</blockquote>'); in_quote = False
                    math_lines = []
                    i += 1
                    while i < len(lines):
                        if lines[i].strip() == math_close_delim:
                            break
                        math_lines.append(lines[i])
                        i += 1
                    out.append(self._build_math_html('\n'.join(math_lines)))
                    last_was_br = False
                    i += 1
                    continue

            # ── 空行 → 结束列表/引用，最多保留一个 <br> ──
            if not line.strip():
                if in_ul: out.append("</ul>"); in_ul = False
                if in_ol: out.append("</ol>"); in_ol = False
                if in_quote: out.append("</blockquote>"); in_quote = False
                if not last_was_br:
                    out.append("<br>")
                    last_was_br = True
                i += 1; continue
            last_was_br = False

            # ── 引用 ──
            if line.lstrip().startswith("> "):
                if not in_quote:
                    out.append('<blockquote style="border-left:3px solid #7C5CFC; '
                               'margin:8px 0; padding:4px 12px; color:#555;">')
                    in_quote = True
                content = line.lstrip()[2:]
                while content.startswith("> "):
                    content = content[2:]
                out.append(f"<p style='{P_STYLE}'>{self._inline_md(content)}</p>")
                i += 1; continue
            elif in_quote and not line.lstrip().startswith(">"):
                out.append("</blockquote>"); in_quote = False

            # ── 标题 ──
            if line.startswith("#### "):
                out.append(f"<h4 style='{H4_STYLE}'>{self._inline_md(line[5:])}</h4>"); i += 1; continue
            if line.startswith("### "):
                out.append(f"<h3 style='{H3_STYLE}'>{self._inline_md(line[4:])}</h3>"); i += 1; continue
            if line.startswith("## "):
                out.append(f"<h2 style='{H2_STYLE}'>{self._inline_md(line[3:])}</h2>"); i += 1; continue
            if line.startswith("# "):
                out.append(f"<h1 style='{H1_STYLE}'>{self._inline_md(line[2:])}</h1>"); i += 1; continue

            # ── 分割线 ──
            if line.strip() in ("---", "***", "___", "- - -", "* * *"):
                out.append("<hr style='border:none;height:1px;background:#E5E5E5;margin:12px 0;'>")
                i += 1; continue

            # ── 表格 ──
            if "|" in line and i + 1 < len(lines) and "|" in lines[i + 1]:
                table_lines = []
                j = i
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    stripped = lines[j].strip()
                    if stripped.startswith("|") or " | " in stripped:
                        table_lines.append(stripped)
                    else:
                        break
                    j += 1
                if len(table_lines) >= 2:
                    if in_ul: out.append("</ul>"); in_ul = False
                    if in_ol: out.append("</ol>"); in_ol = False
                    if in_quote: out.append("</blockquote>"); in_quote = False
                    out.append(self._build_table_html(table_lines))
                    i = j
                    continue

            # ── 任务列表（- [ ] / - [x]） ──
            m = re.match(r"^[-*]\s+\[([ xX])\]\s+(.+)", line)
            if m:
                if in_ol: out.append("</ol>"); in_ol = False
                if not in_ul:
                    out.append("<ul style='margin:4px 0;padding-left:24px;list-style:none;'>")
                    in_ul = True
                checked = m.group(1).lower() == "x"
                icon = "☑" if checked else "☐"
                color = "#22C55E" if checked else "#94A3B8"
                out.append(
                    f'<li style="margin:2px 0;">'
                    f'<span style="color:{color};font-size:20px;margin-right:6px;">{icon}</span>'
                    f'{self._inline_md(m.group(2))}</li>')
                i += 1; continue

            # ── 有序列表 ──
            m = re.match(r"^(\d+)\.\s+(.+)", line)
            if m:
                if in_ul: out.append("</ul>"); in_ul = False
                if not in_ol: out.append("<ol style='margin:4px 0;padding-left:24px;'>"); in_ol = True
                out.append(f"<li>{self._inline_md(m.group(2))}</li>")
                i += 1; continue

            # ── 无序列表 ──
            m = re.match(r"^[-*+]\s+(.+)", line)
            if m:
                if in_ol: out.append("</ol>"); in_ol = False
                if not in_ul: out.append("<ul style='margin:4px 0;padding-left:24px;'>"); in_ul = True
                out.append(f"<li>{self._inline_md(m.group(1))}</li>")
                i += 1; continue

            # ── 结束列表 ──
            if in_ul: out.append("</ul>"); in_ul = False
            if in_ol: out.append("</ol>"); in_ol = False

            # ── 普通段落 ──
            out.append(f"<p style='{P_STYLE}'>{self._inline_md(line)}</p>")
            i += 1

        # 收尾未关闭的块
        if in_code_block: out.append("</pre>")
        if in_ul: out.append("</ul>")
        if in_ol: out.append("</ol>")
        if in_quote: out.append("</blockquote>")

        # 去尾部的 <br> 标签
        result = "".join(out)
        while result.endswith("<br>"):
            result = result[:-4]
        return result

    def _build_table_html(self, lines):
        """将 Markdown 表格行转为 HTML <table>"""
        if len(lines) < 2:
            return ""
        rows = []
        for line in lines:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)

        # 第一行是表头，第二行是分隔符
        header = rows[0]
        has_sep = len(rows) >= 2 and all(
            re.match(r"^:?-{3,}:?$", c) for c in rows[1])
        data_start = 2 if has_sep else 1

        # 从分隔符提取对齐
        aligns = ["left"] * len(header)
        if has_sep:
            for ci, sep in enumerate(rows[1]):
                if ci >= len(aligns):
                    break
                if sep.startswith(":") and sep.endswith(":"):
                    aligns[ci] = "center"
                elif sep.endswith(":"):
                    aligns[ci] = "right"
                elif sep.startswith(":"):
                    aligns[ci] = "left"

        align_map = {"left": "left", "center": "center", "right": "right"}
        html = ('<table style="border-collapse:collapse;width:100%;'
                'margin:8px 0;font-size:20px;">')
        html += "<thead><tr>"
        for ci, cell in enumerate(header):
            html += (f'<th style="border:1px solid #E5EAF3;padding:10px 16px;'
                     f'background:#F1F5F9;text-align:{align_map[aligns[ci]]};'
                     f'font-weight:700;color:#1E293B;">'
                     f'{self._inline_md(cell)}</th>')
        html += "</tr></thead><tbody>"
        for row in rows[data_start:]:
            html += "<tr>"
            for ci, cell in enumerate(row):
                al = align_map[aligns[ci]] if ci < len(aligns) else "left"
                html += (f'<td style="border:1px solid #E5EAF3;padding:10px 16px;'
                         f'text-align:{al};color:#334155;">'
                         f'{self._inline_md(cell)}</td>')
            html += "</tr>"
        html += "</tbody></table>"
        return html

    # ── LaTeX → Unicode 符号表 ──────────────────────────────
    _LATEX_SYMBOLS = {
        # 希腊字母（小写）
        r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
        r'\epsilon': 'ε', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η',
        r'\theta': 'θ', r'\vartheta': 'ϑ', r'\iota': 'ι', r'\kappa': 'κ',
        r'\lambda': 'λ', r'\mu': 'μ', r'\nu': 'ν', r'\xi': 'ξ',
        r'\omicron': 'ο', r'\pi': 'π', r'\varpi': 'ϖ', r'\rho': 'ρ',
        r'\varrho': 'ϱ', r'\sigma': 'σ', r'\varsigma': 'ς', r'\tau': 'τ',
        r'\upsilon': 'υ', r'\phi': 'φ', r'\varphi': 'ϕ', r'\chi': 'χ',
        r'\psi': 'ψ', r'\omega': 'ω',
        # 希腊字母（大写）
        r'\Gamma': 'Γ', r'\Delta': 'Δ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
        r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ', r'\Upsilon': 'Υ',
        r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
        # 运算符
        r'\pm': '±', r'\mp': '∓', r'\times': '×', r'\div': '÷',
        r'\cdot': '·', r'\ast': '∗', r'\star': '⋆', r'\circ': '∘',
        r'\bullet': '•', r'\oplus': '⊕', r'\ominus': '⊖', r'\otimes': '⊗',
        r'\oslash': '⊘', r'\odot': '⊙',
        # 关系符号
        r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\approx': '≈',
        r'\equiv': '≡', r'\sim': '∼', r'\simeq': '≃', r'\propto': '∝',
        r'\ll': '≪', r'\gg': '≫', r'\doteq': '≐', r'\prec': '≺',
        r'\succ': '≻', r'\preceq': '≼', r'\succeq': '≽', r'\subset': '⊂',
        r'\supset': '⊃', r'\subseteq': '⊆', r'\supseteq': '⊇',
        r'\in': '∈', r'\notin': '∉', r'\ni': '∋', r'\exists': '∃',
        r'\forall': '∀', r'\emptyset': '∅', r'\varnothing': '∅',
        # 箭头
        r'\rightarrow': '→', r'\to': '→', r'\leftarrow': '←',
        r'\Rightarrow': '⇒', r'\Leftarrow': '⇐', r'\leftrightarrow': '↔',
        r'\Leftrightarrow': '⇔', r'\mapsto': '↦', r'\longmapsto': '⟼',
        r'\longrightarrow': '⟶', r'\longleftarrow': '⟵',
        r'\uparrow': '↑', r'\downarrow': '↓', r'\updownarrow': '↕',
        r'\nearrow': '↗', r'\searrow': '↘', r'\swarrow': '↙',
        r'\nwarrow': '↖',
        # 大型运算符
        r'\sum': '∑', r'\prod': '∏', r'\coprod': '∐', r'\int': '∫',
        r'\iint': '∬', r'\iiint': '∭', r'\oint': '∮', r'\bigcup': '⋃',
        r'\bigcap': '⋂', r'\bigvee': '⋁', r'\bigwedge': '⋀',
        # 特殊符号
        r'\infty': '∞', r'\partial': '∂', r'\nabla': '∇',
        r'\aleph': 'ℵ', r'\hbar': 'ℏ', r'\ell': 'ℓ', r'\wp': '℘',
        r'\Re': 'ℜ', r'\Im': 'ℑ', r'\angle': '∠', r'\triangle': '△',
        r'\square': '□', r'\diamond': '◇',
        r'\ldots': '…', r'\cdots': '⋯', r'\vdots': '⋮', r'\ddots': '⋱',
        r'\perp': '⊥', r'\parallel': '∥',
        # 集合
        r'\cap': '∩', r'\cup': '∪', r'\setminus': '∖',
        # 逻辑
        r'\land': '∧', r'\lor': '∨', r'\lnot': '¬', r'\neg': '¬',
        r'\top': '⊤', r'\bot': '⊥',
        # 微积分
        r'\lim': 'lim', r'\log': 'log', r'\ln': 'ln', r'\exp': 'exp',
        r'\sin': 'sin', r'\cos': 'cos', r'\tan': 'tan', r'\cot': 'cot',
        r'\sec': 'sec', r'\csc': 'csc', r'\arcsin': 'arcsin',
        r'\arccos': 'arccos', r'\arctan': 'arctan', r'\sinh': 'sinh',
        r'\cosh': 'cosh', r'\tanh': 'tanh', r'\max': 'max', r'\min': 'min',
        r'\sup': 'sup', r'\inf': 'inf', r'\det': 'det', r'\gcd': 'gcd',
        r'\dim': 'dim', r'\hom': 'hom', r'\ker': 'ker',
        # 上下标（Unicode 用于单字符 fallback）
        r'\prime': '′', r'\primeprime': '″',
        # 括号修饰
        r'\bigl': '', r'\bigr': '', r'\Bigl': '', r'\Bigr': '',
        r'\biggl': '', r'\biggr': '', r'\Biggl': '', r'\Biggr': '',
        r'\big': '', r'\Big': '', r'\bigg': '', r'\Bigg': '',
        # 空格
        r'\;': ' ', r'\:': ' ', r'\,': '', r'\!': '',
        r'\qquad': '  ', r'\quad': ' ',
        # 换行
        r'\\': '<br>',
        # 样式
        r'\text': '', r'\mathbf': '', r'\mathrm': '', r'\mathit': '',
        r'\mathsf': '', r'\mathtt': '', r'\mathcal': '', r'\mathbb': '',
        r'\boldsymbol': '', r'\mathfrak': '', r'\mathscr': '',
        r'\operatorname': '', r'\widehat': '', r'\widetilde': '',
        r'\overline': '', r'\underline': '', r'\overbrace': '', r'\underbrace': '',
        r'\boxed': '', r'\not': '̸',  # combining long solidus overlay
    }

    def _render_latex(self, text):
        """将 LaTeX 数学公式转为 HTML（支持希腊字母、符号、上下标、分式、根号等）

        注意：调用方需确保输入已做 HTML 转义（&lt; &amp; &gt;），
        若调用自 _inline_md 则已由 _md2html 转义；
        若调用自 _build_math_html / _math_block 则需先转义。
        """
        if not text or not text.strip():
            return text

        result = text

        # ── 1. \text{...} → 纯文本 ──
        def _replace_text(m):
            inner = m.group(1)
            # 递归渲染 \text 内部（可能还有 $...$ 之类的）
            return inner
        result = re.sub(r'\\text\{(.+?)\}', _replace_text, result)

        # ── 3. \frac{a}{b} → 分式 ──
        def _replace_frac(m):
            num = self._render_latex(m.group(1))
            den = self._render_latex(m.group(2))
            return (f'<span style="display:inline-block;vertical-align:middle;'
                    f'text-align:center;">'
                    f'<span style="display:block;border-bottom:1px solid #B45309;'
                    f'padding:0 4px 2px 4px;margin-bottom:2px;">{num}</span>'
                    f'<span style="display:block;padding:0 4px;">{den}</span>'
                    f'</span>')
        result = re.sub(r'\\frac\{(.+?)\}\{(.+?)\}', _replace_frac, result)

        # ── 4. \sqrt[n]{x} 或 \sqrt{x} ──
        def _replace_sqrt(m):
            # m.lastindex=2 来自 \sqrt[n]{x}  (g1=n, g2=x)
            # m.lastindex=1 来自 \sqrt{x}     (g1=x)
            if m.lastindex and m.lastindex >= 2:
                n = m.group(1)
                inner = m.group(2)
            else:
                n = None
                inner = m.group(1)
            root_index = f'<sup style="font-size:16px;">{n}</sup>' if n else ''
            return (f'<span style="display:inline-block;vertical-align:middle;">'
                    f'{root_index}√<span style="text-decoration:overline;">'
                    f'{inner}</span></span>')
        result = re.sub(r'\\sqrt\[(.+?)\]\{(.+?)\}', _replace_sqrt, result)
        result = re.sub(r'\\sqrt\{(.+?)\}', _replace_sqrt, result)

        # ── 5. \left...\right...（去掉 \left/\right，保留括号） ──
        result = re.sub(r'\\left\s*([()\[\]{}|.\\])', r'\1', result)
        result = re.sub(r'\\right\s*([()\[\]{}|.\\])', r'\1', result)

        # ── 6. 上下标 { } 组 ──
        result = re.sub(r'\_\{(.+?)\}', r'<sub>\1</sub>', result)
        result = re.sub(r'\^\{(.+?)\}', r'<sup>\1</sup>', result)
        # 单 LaTeX 命令作上下标（如 ^\infty、_\alpha）
        result = re.sub(r'(?<!\\)\^(\\(?:[a-zA-Z]+\*?))', r'<sup>\1</sup>', result)
        result = re.sub(r'(?<!\\)\_(\\(?:[a-zA-Z]+\*?))', r'<sub>\1</sub>', result)
        # 单字符上下标：排除 \ （避免吃掉命令前导 \），排除空格
        result = re.sub(r'(?<!\\)\_([^\\\s])', r'<sub>\1</sub>', result)
        result = re.sub(r'(?<!\\)\^([^\\\s])', r'<sup>\1</sup>', result)

        # ── 7. \mathbb{X} / \mathcal{X} / \mathbf{X} 等带参样式命令 ──
        # 只对单字符内容做 Unicode 映射，多字符则去掉外包装
        def _replace_style(m):
            cmd = m.group(1)
            inner = m.group(2)
            if len(inner) == 1:
                # 尝试 Unicode 数学字母映射
                c = inner
                if cmd == 'mathbb':
                    tbl = {'A':'𝔸','B':'𝔹','C':'ℂ','D':'𝔻','E':'𝔼','F':'𝔽','G':'𝔾',
                           'H':'ℍ','I':'𝕀','J':'𝕁','K':'𝕂','L':'𝕃','M':'𝕄',
                           'N':'ℕ','O':'𝕆','P':'ℙ','Q':'ℚ','R':'ℝ','S':'𝕊',
                           'T':'𝕋','U':'𝕌','V':'𝕍','W':'𝕎','X':'𝕏','Y':'𝕐','Z':'ℤ',
                           'a':'𝕒','b':'𝕓','c':'𝕔','d':'𝕕','e':'𝕖','f':'𝕗','g':'𝕘',
                           'h':'𝕙','i':'𝕚','j':'𝕛','k':'𝕜','l':'𝕝','m':'𝕞',
                           'n':'𝕟','o':'𝕠','p':'𝕡','q':'𝕢','r':'𝕣','s':'𝕤',
                           't':'𝕥','u':'𝕦','v':'𝕧','w':'𝕨','x':'𝕩','y':'𝕪','z':'𝕫',
                           '0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜',
                           '5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡'}
                    return tbl.get(c, c)
                elif cmd == 'mathcal':
                    tbl = {'A':'𝒜','B':'ℬ','C':'𝒞','D':'𝒟','E':'ℰ','F':'ℱ','G':'𝒢',
                           'H':'ℋ','I':'ℐ','J':'𝒥','K':'𝒦','L':'ℒ','M':'ℳ',
                           'N':'𝒩','O':'𝒪','P':'𝒫','Q':'𝒬','R':'ℛ','S':'𝒮',
                           'T':'𝒯','U':'𝒰','V':'𝒱','W':'𝒲','X':'𝒳','Y':'𝒴','Z':'𝒵'}
                    return tbl.get(c, c)
                elif cmd in ('mathbf', 'mathrm', 'mathsf', 'mathtt'):
                    return c
                else:
                    return c
            else:
                return inner
        result = re.sub(
            r'\\(mathbb|mathcal|mathbf|mathrm|mathsf|mathtt|mathit|'
            r'mathfrak|mathscr|boldsymbol)\{(\S+?)\}',
            _replace_style, result)

        # ── 8. LaTeX 命令 → Unicode ──
        # 按长度降序排列避免部分匹配（如 \varepsilon 优先于 \epsilon）
        patterns = sorted(self._LATEX_SYMBOLS.keys(), key=len, reverse=True)
        for pat in patterns:
            val = self._LATEX_SYMBOLS[pat]
            # 只替换独立的命令（前面不是字母）
            result = re.sub(r'(?<!\w)' + re.escape(pat), val, result)

        # ── 9. 算子名正体 + 大型运算符放大 ──
        _OP_NAMES = (
            r'sin|cos|tan|cot|sec|csc|arcsin|arccos|arctan|'
            r'sinh|cosh|tanh|coth|'
            r'ln|log|lg|exp|lim|max|min|sup|inf|det|gcd|dim|ker|hom|'
            r'arg|deg|Pr|mod|bmod|pmod'
        )
        result = re.sub(
            r'\b(' + _OP_NAMES + r')\b',
            r'<span style="font-style:normal;font-weight:500;">\1</span>',
            result)

        # 大型运算符 Unicode 放大
        _LARGE_OPS = '∑∏∐∫∬∭∮∲∳⋃⋂⋁⋀⨁⨂⨄⨅⨆⨈⨉⨊⨋⨌⨍⨎⨏⨐⨑⨒⨓⨔⨕⨖⨗⨘⨙⨚⨛⨜⨝⨞⨟⨠⨡⨢⨣⨤⨥⨦⨧⨨⨩⨪⨫⨬⨭⨮'
        for ch in _LARGE_OPS:
            if ch in result:
                result = result.replace(
                    ch, f'<span style="font-size:130%;">{ch}</span>')

        # ── 10. 清理未配对的 { }（LaTeX 分组括号） ──
        result = result.replace('{', '').replace('}', '')

        return result

    def _build_math_html(self, math_text):
        """LaTeX 数学公式 → 居中显示的 HTML 块"""
        escaped = math_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rendered = self._render_latex(escaped)
        return (
            '<div style="background:#FFF8E1;border-left:4px solid #F59E0B;'
            'border-radius:12px;padding:16px 24px;margin:8px 0;'
            'font-family:Georgia,serif;font-size:22px;color:#92400E;'
            'text-align:center;font-style:italic;">'
            f'{rendered}'
            '</div>'
        )

    def _math_block(self, math_text):
        """数学公式块（原生 QFrame widget，用于 _build_ai_answer_container）"""
        escaped = math_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rendered = self._render_latex(escaped)
        block = QFrame()
        block.setObjectName("MathBlock")
        block.setStyleSheet(f"""
            QFrame#MathBlock {{
                background:#FFF8E1;
                border-left:4px solid #F59E0B;
                border-radius:12px;
                padding:16px 24px;
            }}
        """)
        block.setMaximumWidth(1360)
        bl = QVBoxLayout(block)
        bl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(rendered)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(1300)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(
            "font-family:Georgia,serif; font-size:22px; "
            "color:#92400E; "
            "background:transparent; border:none;"
        )
        bl.addWidget(lbl)
        return block

    def _inline_md(self, text):
        """行内：粗体、斜体、删除线、代码、链接、图片、LaTeX 行内数学公式"""
        _MATH_STYLE = (
            'background:#FFF8E1;padding:2px 8px;border-radius:4px;'
            'font-size:21px;color:#B45309;font-family:Georgia,serif;'
        )
        # 行内 LaTeX 数学公式：\(...\)（标准 LaTeX 语法）
        text = re.sub(
            r"\\\((.+?)\\\)",
            lambda m: f'<code style="{_MATH_STYLE}">'
                      f'{self._render_latex(m.group(1))}</code>', text)
        # 行内 LaTeX 数学公式 $...$（先处理，避免和 $ 后续正则冲突）
        text = re.sub(
            r"(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)",
            lambda m: f'<code style="{_MATH_STYLE}">'
                      f'{self._render_latex(m.group(1))}</code>', text)
        # 粗体（**text**）
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # 斜体（*text*），注意不要匹配 ** 内的内容
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        # 删除线（~~text~~）
        text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
        # 行内代码（`code`）
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#F1F5F9;padding:2px 8px;'
            r'border-radius:4px;font-size:22px;color:#5B21B6;">\1</code>', text)
        # 链接 [text](url)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                      r'<a href="\2" style="color:#7C5CFC;">\1</a>', text)
        # 图片 ![alt](url) → 显示为可点击链接
        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                      r'[📷 \1](\2)', text)
        return text

    # ═══════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════

    def _add_to_chat(self, widget):
        if self._msg_layout.count() > 0:
            last = self._msg_layout.itemAt(self._msg_layout.count() - 1)
            if last.spacerItem():
                self._msg_layout.removeItem(last)
        self._msg_layout.addWidget(widget)
        self._msg_layout.addStretch()

    def _replace_last_widget(self, new_widget):
        """将消息区域最后一个 widget 替换为 new_widget"""
        count = self._msg_layout.count()
        if count < 2:
            self._add_to_chat(new_widget)
            return
        # 倒数第二个是最后一个 widget（倒数第一个是 stretch）
        stretch_idx = count - 1
        widget_idx = count - 2
        old_item = self._msg_layout.takeAt(widget_idx)
        if old_item and old_item.widget():
            old_item.widget().hide()
            old_item.widget().deleteLater()
        self._msg_layout.insertWidget(widget_idx, new_widget)

    def _clear_messages(self):
        # 先隐藏 _empty_hint 并从布局中移除，防止被 deleteLater 删掉
        if hasattr(self, '_empty_hint') and self._empty_hint:
            try:
                self._empty_hint.hide()
                self._msg_layout.removeWidget(self._empty_hint)
            except RuntimeError:
                self._empty_hint = None

        while self._msg_layout.count():
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_messages(self):
        self._clear_messages()
        if not self._messages:
            if hasattr(self, '_empty_hint') and self._empty_hint:
                try:
                    self._empty_hint.show()
                    self._msg_layout.addStretch()
                    self._msg_layout.addWidget(self._empty_hint)
                except RuntimeError:
                    self._empty_hint = None
            self._msg_layout.addStretch()
            return
        for m in self._messages:
            if m["role"] == "user":
                w = self._user_bubble(m["content"], m["ts"])
            else:
                # AI 消息：先用 _parse_answer 拆分代码块，再渲染
                parts = self._parse_answer(m["content"])
                w = self._build_ai_answer_container(m["ts"], parts)
            self._msg_layout.addWidget(w)
        self._msg_layout.addStretch()
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._msg_scroll.verticalScrollBar(
        ).setValue(self._msg_scroll.verticalScrollBar().maximum()))

    def _copy(self, text):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
