import time
from datetime import datetime

from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QScrollArea, QFrame, QWidget)
from PyQt5.QtCore import Qt, QTimer

from client.core.base_panel import BasePanel
from common.messages import MT


# ── 颜色常量 ──────────────────────────────────────────────
AI_PRIMARY = "#7C5CFC"
AI_GRADIENT_START = "#A78BFA"
AI_GRADIENT_END = "#7C5CFC"
AI_BADGE_BG = "#EDE9FE"
AI_BADGE_TEXT = "#5B21B6"
USER_GRADIENT_START = "#4F8DFD"
USER_GRADIENT_END = "#2D6CF6"
USER_AVATAR_START = "#2D6CF6"
USER_AVATAR_END = "#1E4FD0"
CODE_BLOCK_BG = "#1E2A3A"
CHAT_BG = "#FAFBFE"
PANEL_BG = "#EEF2FA"
SIDEBAR_BG = "#F7F9FD"
BUBBLE_SHADOW_USER = "0 6px 18px rgba(45,108,246,0.28)"
BUBBLE_SHADOW_AI = "0 2px 12px rgba(45,108,246,0.08)"


class AIPanel(BasePanel):
    """AI 问答面板 —— 根据 UI 设计稿重写"""

    def subscribe(self):
        # 状态
        self._messages = []          # 当前会话的消息: [{"role","content","ts","has_code","code_lang","code_content"}, ...]
        self._conversations = []     # 历史对话列表
        self._current_conv_idx = -1  # 当前对话索引，-1 表示新对话
        self._is_waiting = False     # 是否在等待 AI 回复

        # 订阅 AI 回复
        self.app.net.on(MT.AI_ANSWER, self._on_ai_answer)
        self._build_ui()

    # ═══════════════════════════════════════════════════════
    #  整体布局
    # ═══════════════════════════════════════════════════════

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 左侧：历史对话侧栏 ──
        self._sidebar = self._create_sidebar()
        layout.addWidget(self._sidebar)

        # ── 右侧：聊天主区域 ──
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self._create_header())
        right_layout.addWidget(self._create_messages_area(), 1)
        right_layout.addWidget(self._create_composer())

        layout.addWidget(right, 1)

    # ═══════════════════════════════════════════════════════
    #  历史对话侧栏
    # ═══════════════════════════════════════════════════════

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(f"background-color: {SIDEBAR_BG}; border-right: 1px solid #E5EAF3;")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题行
        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(20, 22, 20, 14)

        title = QLabel("历史对话")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #1E293B;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        new_btn = QPushButton("＋")
        new_btn.setFixedSize(36, 36)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AI_BADGE_BG};
                color: {AI_PRIMARY};
                border: none;
                border-radius: 12px;
                font-size: 20px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #DDD4FA; }}
        """)
        new_btn.clicked.connect(self._new_conversation)
        title_layout.addWidget(new_btn)
        layout.addWidget(title_row)

        # 搜索框
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(20, 0, 20, 14)

        search_box = QFrame()
        search_box.setFixedHeight(44)
        search_box.setStyleSheet("""
            background-color: #fff; border-radius: 14px;
            box-shadow: 0 2px 8px rgba(45,108,246,0.06);
        """)
        sb_layout = QHBoxLayout(search_box)
        sb_layout.setContentsMargins(15, 0, 15, 0)
        sb_layout.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 17px;")
        sb_layout.addWidget(search_icon)

        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索对话")
        search_input.setStyleSheet("""
            border: none; background: transparent;
            font-size: 14px; color: #1E293B;
        """)
        sb_layout.addWidget(search_input)
        search_layout.addWidget(search_box)
        layout.addWidget(search_container)

        # 历史列表滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._history_content = QWidget()
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(12, 0, 12, 0)
        self._history_layout.setSpacing(4)
        self._history_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._history_content)
        layout.addWidget(scroll, 1)

        # 初始历史项（示例）
        sample_convs = [
            ("AES加密实现思路", "今天", 3),
            ("PyQt5 布局最佳实践", "昨天", 7),
            ("TCP Socket 长连接心跳", "周一", 5),
            ("SQLite 并发读写问题", "周日", 4),
            ("文件分片传输算法设计", "上周五", 6),
        ]
        for i, (title_text, date, count) in enumerate(sample_convs):
            conv = {"title": title_text, "date": date, "messages": [], "preview_count": count}
            self._conversations.append(conv)
            item = self._create_history_item(title_text, f"{date} · {count} 条消息", active=(i == 0))
            self._history_layout.addWidget(item)

        self._history_layout.addStretch()

        return sidebar

    def _create_history_item(self, title_text, subtitle, active=False):
        """创建历史对话项"""
        item = QFrame()
        item.setFixedHeight(58)
        item.setCursor(Qt.PointingHandCursor)

        if active:
            item.setStyleSheet(f"""
                QFrame {{
                    background-color: {AI_BADGE_BG};
                    border-radius: 16px;
                }}
            """)
        else:
            item.setStyleSheet("""
                QFrame { background-color: transparent; border-radius: 16px; }
                QFrame:hover { background-color: rgba(237,233,254,0.5); }
            """)

        layout = QVBoxLayout(item)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title_label = QLabel(title_text)
        title_label.setStyleSheet(f"""
            font-size: 14px; font-weight: {'700' if active else '600'};
            color: {'{AI_BADGE_TEXT}' if active else '#1E293B'};
        """)
        title_label.setWordWrap(False)
        layout.addWidget(title_label)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(f"""
            font-size: 12px; color: {'{AI_PRIMARY}' if active else '#94A3B8'};
        """)
        layout.addWidget(sub_label)

        return item

    def _new_conversation(self):
        """创建新对话"""
        self._messages = []
        self._current_conv_idx = -1
        self._is_waiting = False
        self._refresh_messages()

    # ═══════════════════════════════════════════════════════
    #  聊天头部
    # ═══════════════════════════════════════════════════════

    def _create_header(self):
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet(f"background-color: {SIDEBAR_BG}; border-bottom: 1px solid #EEF1F7;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(16)

        # AI 头像
        avatar = QLabel("✨")
        avatar.setFixedSize(50, 50)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AI_GRADIENT_START}, stop:1 {AI_GRADIENT_END});
            color: white;
            border-radius: 25px;
            font-size: 24px;
        """)
        layout.addWidget(avatar)

        # 名称 & 副标题
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        name_row = QHBoxLayout()
        name_row.setSpacing(9)
        name = QLabel("AI 助手")
        name.setStyleSheet("font-size: 18px; font-weight: 800; color: #1E293B;")
        name_row.addWidget(name)

        badge = QLabel("智能问答")
        badge.setStyleSheet(f"""
            font-size: 12px; font-weight: 700; color: {AI_PRIMARY};
            background-color: {AI_BADGE_BG}; padding: 2px 9px; border-radius: 8px;
        """)
        name_row.addWidget(badge)
        name_row.addStretch()
        info_layout.addLayout(name_row)

        subtitle = QLabel("随时问我校园通项目的任何技术问题")
        subtitle.setStyleSheet("font-size: 13px; color: #94A3B8;")
        info_layout.addWidget(subtitle)

        layout.addLayout(info_layout)
        layout.addStretch()

        # 新对话按钮
        new_btn = QPushButton("🔄  新对话")
        new_btn.setFixedHeight(38)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AI_BADGE_BG};
                color: {AI_PRIMARY};
                border: none;
                border-radius: 13px;
                font-size: 14px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background-color: #DDD4FA; }}
        """)
        new_btn.clicked.connect(self._new_conversation)
        layout.addWidget(new_btn)

        return header

    # ═══════════════════════════════════════════════════════
    #  消息区域
    # ═══════════════════════════════════════════════════════

    def _create_messages_area(self):
        self._msg_scroll = QScrollArea()
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._msg_scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background-color: {CHAT_BG}; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{
                background: rgba(100,116,139,0.22); border-radius: 3px; min-height: 20px;
            }}
        """)

        self._msg_content = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_content)
        self._msg_layout.setContentsMargins(36, 28, 36, 28)
        self._msg_layout.setSpacing(22)
        self._msg_layout.setAlignment(Qt.AlignTop)

        self._msg_scroll.setWidget(self._msg_content)

        # 初始显示欢迎引导
        self._show_welcome()

        return self._msg_scroll

    def _show_welcome(self):
        """显示欢迎引导（首次进入 / 新对话）"""
        self._clear_messages()

        # 欢迎卡片
        welcome = QFrame()
        welcome.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AI_GRADIENT_START}, stop:1 {AI_GRADIENT_END});
            border-radius: 18px;
        """)
        wl = QVBoxLayout(welcome)
        wl.setSpacing(12)
        wl.setContentsMargins(28, 24, 28, 24)

        icon = QLabel("✨")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 36px;")
        wl.addWidget(icon)

        wt = QLabel("AI 智能助手")
        wt.setAlignment(Qt.AlignCenter)
        wt.setStyleSheet("font-size: 18px; font-weight: 700; color: white;")
        wl.addWidget(wt)

        wd = QLabel("我可以帮你整理待办、解答问题、提供建议")
        wd.setAlignment(Qt.AlignCenter)
        wd.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.9);")
        wl.addWidget(wd)

        self._msg_layout.addWidget(welcome)

        # 建议标签
        sug_label = QLabel("试试这些功能")
        sug_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #6B7A90; margin-top: 8px;")
        self._msg_layout.addWidget(sug_label)

        suggestions = [
            ("📋 整理今日待办", "帮我整理今天的待办事项"),
            ("💡 技术问答", "解答编程和技术问题"),
            ("📊 数据分析", "分析项目进度和数据"),
            ("📝 文档生成", "帮我生成会议纪要"),
        ]
        for icon_text, desc in suggestions:
            card = self._create_suggestion_card(icon_text, desc)
            self._msg_layout.addWidget(card)

        self._msg_layout.addStretch()

    def _create_suggestion_card(self, title_text, desc):
        """创建建议卡片"""
        card = QPushButton()
        card.setFixedHeight(64)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QPushButton {{
                background-color: #fff;
                border: 2px solid #E7EFFC;
                border-radius: 14px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_BG};
                border: 2px solid #D1E3FA;
            }}
        """)
        card.clicked.connect(lambda: self._send_quick(desc))

        cl = QVBoxLayout(card)
        cl.setSpacing(4)

        tl = QLabel(title_text)
        tl.setStyleSheet("font-size: 14px; font-weight: 600; color: #1E293B;")
        cl.addWidget(tl)

        dl = QLabel(desc)
        dl.setStyleSheet("font-size: 12px; color: #94A3B8;")
        cl.addWidget(dl)

        return card

    # ═══════════════════════════════════════════════════════
    #  输入区
    # ═══════════════════════════════════════════════════════

    def _create_composer(self):
        composer = QFrame()
        composer.setStyleSheet(f"background-color: {PANEL_BG};")

        layout = QVBoxLayout(composer)
        layout.setContentsMargins(24, 16, 24, 20)
        layout.setSpacing(13)

        # ── 快捷提问标签 ──
        quick_row = QHBoxLayout()
        quick_row.setSpacing(9)

        quick_prompts = [
            "🔑 密钥管理最佳实践",
            "📡 TCP 断线重连",
            "🗃️ 消息持久化",
            "⚡ 并发处理优化",
        ]
        for prompt in quick_prompts:
            chip = QPushButton(prompt)
            chip.setFixedHeight(34)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(f"""
                QPushButton {{
                    background-color: #fff;
                    border: 1.5px solid #E5EAF3;
                    border-radius: 22px;
                    font-size: 13px;
                    color: #64748B;
                    padding: 0 14px;
                    white-space: nowrap;
                }}
                QPushButton:hover {{
                    background-color: {AI_BADGE_BG};
                    border-color: {AI_GRADIENT_START};
                    color: {AI_PRIMARY};
                }}
            """)
            chip.clicked.connect(lambda _, p=prompt: self._send_quick(p))
            quick_row.addWidget(chip)

        quick_row.addStretch()
        layout.addLayout(quick_row)

        # ── 输入卡片 ──
        input_card = QFrame()
        input_card.setStyleSheet("""
            background-color: #fff;
            border-radius: 20px;
        """)

        card_layout = QHBoxLayout(input_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(13)

        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("问我关于校园通项目的任何技术问题…")
        self._input_field.setStyleSheet("""
            border: none; background: transparent;
            font-size: 15px; color: #1E293B; padding: 2px 4px;
        """)
        self._input_field.setMinimumHeight(26)
        self._input_field.returnPressed.connect(self._on_send)
        card_layout.addWidget(self._input_field, 1)

        # 语音按钮
        voice_btn = QPushButton("🎤")
        voice_btn.setFixedSize(44, 44)
        voice_btn.setCursor(Qt.PointingHandCursor)
        voice_btn.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9; border: none; border-radius: 14px;
                font-size: 20px;
            }
            QPushButton:hover { background-color: #E5EAF3; }
        """)
        card_layout.addWidget(voice_btn)

        # 发送按钮
        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(48, 48)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {AI_GRADIENT_START}, stop:1 {AI_GRADIENT_END});
                color: white; border: none; border-radius: 15px;
                font-size: 22px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #9677EA, stop:1 #6B4CEC);
            }}
        """)
        self._send_btn.clicked.connect(self._on_send)
        card_layout.addWidget(self._send_btn)

        layout.addWidget(input_card)

        return composer

    # ═══════════════════════════════════════════════════════
    #  消息气泡构建
    # ═══════════════════════════════════════════════════════

    def _create_user_message_widget(self, text, ts_str):
        """用户消息气泡（蓝色渐变，右对齐）"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)
        layout.setDirection(QHBoxLayout.RightToLeft)

        # 头像
        avatar = QLabel("我")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {USER_AVATAR_START}, stop:1 {USER_AVATAR_END});
            color: white; border-radius: 21px;
            font-size: 16px; font-weight: 700;
        """)
        layout.addWidget(avatar)

        # 文字区
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        text_layout.setAlignment(Qt.AlignRight)

        time_label = QLabel(ts_str)
        time_label.setAlignment(Qt.AlignRight)
        time_label.setStyleSheet("font-size: 12.5px; color: #94A3B8;")
        text_layout.addWidget(time_label)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(500)
        bubble.setTextFormat(Qt.PlainText)
        bubble.setContentsMargins(14, 14, 14, 14)
        bubble.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {USER_GRADIENT_START}, stop:1 {USER_GRADIENT_END});
            color: white; border-radius: 18px;
            font-size: 15px; line-height: 1.6;
        """)
        text_layout.addWidget(bubble, alignment=Qt.AlignRight)

        layout.addWidget(text_widget)
        layout.addStretch()

        return container

    def _create_ai_message_widget(self, text, ts_str):
        """AI 消息气泡（白色，左对齐，支持富文本）"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)

        # 头像
        avatar = QLabel("✨")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AI_GRADIENT_START}, stop:1 {AI_GRADIENT_END});
            color: white; border-radius: 21px;
            font-size: 20px;
        """)
        layout.addWidget(avatar)

        # 文字区
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        info = QLabel(f"AI 助手 · {ts_str}")
        info.setStyleSheet("font-size: 12.5px; color: #94A3B8;")
        text_layout.addWidget(info)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(520)
        bubble.setTextFormat(Qt.RichText)
        bubble.setContentsMargins(16, 16, 16, 16)
        bubble.setStyleSheet(f"""
            background-color: #fff; color: #1E293B;
            border-radius: 18px;
            font-size: 15px; line-height: 1.65;
        """)
        text_layout.addWidget(bubble)

        layout.addWidget(text_widget)
        layout.addStretch()

        return container

    def _create_code_block_widget(self, language, code_text):
        """代码块（深色背景 + 语法高亮风格）"""
        block = QFrame()
        block.setStyleSheet(f"""
            background-color: {CODE_BLOCK_BG};
            border-radius: 16px;
            padding: 16px 18px;
        """)
        block.setMaximumWidth(540)

        bl = QVBoxLayout(block)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(12)

        # 语言标签 + 复制按钮
        top = QHBoxLayout()
        lang_label = QLabel(f"{language}")
        lang_label.setStyleSheet("""
            font-size: 12px; font-family: monospace; font-weight: 600; color: #7C9EC8;
        """)
        top.addWidget(lang_label)
        top.addStretch()

        copy_btn = QPushButton("📋 复制")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                color: #7C9EC8; background: transparent; border: none;
                font-size: 12px;
            }
            QPushButton:hover { color: #A0C8F0; }
        """)
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(code_text))
        top.addWidget(copy_btn)
        bl.addLayout(top)

        # 代码内容
        code_label = QLabel(code_text)
        code_label.setTextFormat(Qt.PlainText)
        code_label.setWordWrap(False)
        code_label.setStyleSheet("""
            font-family: 'Courier New', monospace; font-size: 13px;
            color: #E2E8F0; line-height: 1.75;
        """)
        bl.addWidget(code_label)

        return block

    def _create_waiting_indicator(self):
        """AI 思考中指示器"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)

        avatar = QLabel("✨")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AI_GRADIENT_START}, stop:1 {AI_GRADIENT_END});
            color: white; border-radius: 21px;
            font-size: 20px;
        """)
        layout.addWidget(avatar)

        info = QLabel("AI 助手 · 正在思考")
        info.setStyleSheet("font-size: 12.5px; color: #94A3B8;")
        layout.addWidget(info)
        layout.addStretch()

        self._waiting_widget = container
        return container

    def _create_date_badge(self, text):
        """中间日期/话题标识"""
        badge = QLabel(text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("""
            font-size: 12px; color: #94A3B8; background: #E2E8F2;
            padding: 4px 14px; border-radius: 12px;
        """)
        return badge

    # ═══════════════════════════════════════════════════════
    #  消息发送 & 接收
    # ═══════════════════════════════════════════════════════

    def _on_send(self):
        """发送消息"""
        text = self._input_field.text().strip()
        if not text or self._is_waiting:
            return

        self._input_field.clear()

        # 首次发送时清除欢迎引导
        if self._current_conv_idx == -1 and len(self._messages) == 0:
            self._clear_messages()

        ts = int(time.time())
        ts_str = datetime.now().strftime("%H:%M")

        # 1) 立即显示用户消息
        self._messages.append({"role": "user", "content": text, "ts": ts_str})
        user_widget = self._create_user_message_widget(text, ts_str)
        self._add_to_chat(user_widget)

        # 2) 显示等待指示器
        self._is_waiting = True
        self._send_btn.setEnabled(False)
        wait_widget = self._create_waiting_indicator()
        self._add_to_chat(wait_widget)

        # 3) 发送请求到服务器
        self.net.send({
            "type": MT.AI_ASK,
            "question": text,
            "ts": ts,
        })

    def _on_ai_answer(self, msg):
        """收到 AI 回复"""
        self._is_waiting = False
        self._send_btn.setEnabled(True)

        # 移除等待指示器
        if hasattr(self, '_waiting_widget') and self._waiting_widget:
            self._waiting_widget.hide()
            self._waiting_widget.deleteLater()
            self._waiting_widget = None

        answer = msg.get("answer", "抱歉，我没有理解你的问题。")
        ts = msg.get("ts", int(time.time()))
        ts_str = datetime.fromtimestamp(ts).strftime("%H:%M") if isinstance(ts, (int, float)) else datetime.now().strftime("%H:%M")

        self._messages.append({"role": "ai", "content": answer, "ts": ts_str})

        # 解析 answer 中的代码块标记 ```language\n...\n```
        parts = self._parse_ai_response(answer)
        ai_container = QWidget()
        ai_layout = QVBoxLayout(ai_container)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(10)

        # AI 头像 + 时间
        top_row = QHBoxLayout()
        top_row.setSpacing(13)

        avatar = QLabel("✨")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {AI_GRADIENT_START}, stop:1 {AI_GRADIENT_END});
            color: white; border-radius: 21px; font-size: 20px;
        """)
        top_row.addWidget(avatar)

        info = QLabel(f"AI 助手 · {ts_str}")
        info.setStyleSheet("font-size: 12.5px; color: #94A3B8;")
        top_row.addWidget(info)
        top_row.addStretch()
        ai_layout.addLayout(top_row)

        # 渲染各个部分
        for part in parts:
            if part["type"] == "text":
                bubble = QLabel(part["content"])
                bubble.setWordWrap(True)
                bubble.setMaximumWidth(540)
                bubble.setTextFormat(Qt.RichText)
                bubble.setContentsMargins(16, 16, 16, 16)
                bubble.setStyleSheet("""
                    background-color: #fff; color: #1E293B;
                    border-radius: 18px; font-size: 15px; line-height: 1.65;
                """)
                ai_layout.addWidget(bubble)
            elif part["type"] == "code":
                code_widget = self._create_code_block_widget(
                    part.get("language", ""), part["content"]
                )
                ai_layout.addWidget(code_widget)

        self._add_to_chat(ai_container)
        self._scroll_to_bottom()

    def _send_quick(self, prompt_text):
        """发送快捷提问（去掉 emoji 前缀）"""
        # 去掉 emoji 前缀，取空格后面的内容
        parts = prompt_text.split(" ", 1)
        question = parts[1] if len(parts) > 1 else prompt_text
        self._input_field.setText(question)
        self._on_send()

    def _parse_ai_response(self, text):
        """解析 AI 回复，分离普通文本和代码块"""
        parts = []
        import re
        # 匹配 ```language\n...\n```
        pattern = r"```(\w*)\n(.*?)```"
        last_end = 0

        for match in re.finditer(pattern, text, re.DOTALL):
            # 前面的普通文本
            before = text[last_end:match.start()].strip()
            if before:
                # 简单 Markdown → HTML
                before_html = self._simple_md_to_html(before)
                parts.append({"type": "text", "content": before_html})

            # 代码块
            lang = match.group(1) or ""
            code = match.group(2)
            parts.append({"type": "code", "language": lang, "content": code})

            last_end = match.end()

        # 剩余文本
        remaining = text[last_end:].strip()
        if remaining:
            remaining_html = self._simple_md_to_html(remaining)
            parts.append({"type": "text", "content": remaining_html})

        # 如果没有任何内容，当作纯文本
        if not parts:
            parts.append({"type": "text", "content": text})

        return parts

    def _simple_md_to_html(self, text):
        """简易 Markdown → HTML"""
        import re
        # 转义 HTML
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # 粗体 **text**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

        # 行内代码 `code`
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#F1F5F9; padding:1px 7px; border-radius:5px; '
            r'font-size:13.5px; color:#5B21B6;">\1</code>',
            text,
        )

        # 换行 → <br>
        text = text.replace("\n", "<br>")

        return text

    # ═══════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════

    def _add_to_chat(self, widget):
        """向消息区追加一个 widget"""
        # 移除底部的 stretch（如果有的话）
        if self._msg_layout.count() > 0:
            item = self._msg_layout.itemAt(self._msg_layout.count() - 1)
            if item.spacerItem():
                self._msg_layout.removeItem(item)

        self._msg_layout.addWidget(widget)
        self._msg_layout.addStretch()

    def _clear_messages(self):
        """清空消息区"""
        while self._msg_layout.count():
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                pass  # spacer 不需要 deleteLater

    def _refresh_messages(self):
        """刷新消息区（从 _messages 列表重新渲染）"""
        self._clear_messages()

        if not self._messages:
            self._show_welcome()
            return

        for msg in self._messages:
            if msg["role"] == "user":
                widget = self._create_user_message_widget(msg["content"], msg["ts"])
            else:
                widget = self._create_ai_message_widget(msg["content"], msg["ts"])
            self._msg_layout.addWidget(widget)

        self._msg_layout.addStretch()
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """滚动到消息区底部"""
        QTimer.singleShot(50, lambda: self._msg_scroll.verticalScrollBar().setValue(
            self._msg_scroll.verticalScrollBar().maximum()
        ))

    def _copy_to_clipboard(self, text):
        """复制到剪贴板"""
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
