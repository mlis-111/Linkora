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
        self.app.net.on(MT.AI_ANSWER, self._on_ai_answer)
        self.app.net.on(MT.ERROR, self._on_server_error)
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

        payload = {"type": MT.AI_ASK, "question": text, "ts": ts}
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
                self._stream_bubble.setText(self._stream_full)
                self._scroll_to_bottom()
            return

        if is_done:
            self._is_waiting = False
            self._cancelled = False
            self._update_send_btn(sending=False)

            ts_str = datetime.now().strftime("%H:%M")
            self._messages.append(
                {"role": "ai", "content": self._stream_full, "ts": ts_str})

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
        bt.setTextFormat(Qt.PlainText)
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
        cl.setSpacing(14)

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
                cl.addWidget(bubble)
            elif part["type"] == "code":
                cl.addWidget(self._code_block(
                    part.get("language", ""), part["content"]))

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
        # 标题
        text = re.sub(r"(?m)^### (.+)$", r"<h3>\1</h3>", text)
        text = re.sub(r"(?m)^## (.+)$", r"<h2>\1</h2>", text)
        # 粗体 / 斜体
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        # 行内代码
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#F1F5F9; padding:1px 8px; '
            r'border-radius:5px; font-size:22px; color:#5B21B6;">\1</code>',
            text)
        # 无序列表
        text = re.sub(r"(?m)^- (.+)$", r"<li>\1</li>", text)
        text = re.sub(r"(?m)^\d+\. (.+)$", r"<li>\1</li>", text)
        text = text.replace("\n", "<br>")
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
