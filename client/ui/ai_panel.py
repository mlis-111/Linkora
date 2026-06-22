from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QWidget, QLineEdit
from PyQt5.QtCore import Qt
from client.core.base_panel import BasePanel


class AIPanel(BasePanel):
    """AI问答面板 - 方案B样式"""

    def subscribe(self):
        self._build_ui()

    def _build_ui(self):
        """构建AI问答界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QFrame()
        header.setFixedHeight(68)
        header.setStyleSheet("background-color: #F7F9FD;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        # AI标题
        title_layout = QHBoxLayout()
        title = QLabel("✨ AI 助手")
        title.setStyleSheet("font-size: 19px; font-weight: 800; color: #1E293B;")
        title_layout.addWidget(title)

        badge = QLabel("智能")
        badge.setStyleSheet("""
            font-size: 10px;
            font-weight: 700;
            color: #7C5CFC;
            background-color: #F1ECFE;
            
            border-radius: 6px;
            
        """)
        title_layout.addWidget(badge)
        title_layout.addStretch()

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # 新会话按钮
        new_chat_btn = QPushButton("+ 新会话")
        new_chat_btn.setFixedHeight(36)
        new_chat_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #A78BFA, stop:1 #7C5CFC);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #9677EA, stop:1 #6B4CEC);
            }
        """)
        header_layout.addWidget(new_chat_btn)

        layout.addWidget(header)

        # 对话区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #EEF2FA;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 3px;
                min-height: 20px;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(26, 20, 26, 20)
        scroll_layout.setSpacing(18)
        scroll_layout.setAlignment(Qt.AlignTop)

        # 欢迎卡片
        welcome_card = QFrame()
        welcome_card.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #A78BFA, stop:1 #7C5CFC);
            border-radius: 18px;
            
        """)

        welcome_layout = QVBoxLayout(welcome_card)
        welcome_layout.setSpacing(12)

        welcome_icon = QLabel("✨")
        welcome_icon.setStyleSheet("font-size: 36px;")
        welcome_icon.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(welcome_icon)

        welcome_title = QLabel("AI 智能助手")
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_title.setStyleSheet("font-size: 18px; font-weight: 700; color: white;")
        welcome_layout.addWidget(welcome_title)

        welcome_desc = QLabel("我可以帮你整理待办、解答问题、提供建议")
        welcome_desc.setAlignment(Qt.AlignCenter)
        welcome_desc.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.9);")
        welcome_layout.addWidget(welcome_desc)

        scroll_layout.addWidget(welcome_card)

        # 快捷功能卡片
        suggestions_label = QLabel("试试这些功能")
        suggestions_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #6B7A90;  ")
        scroll_layout.addWidget(suggestions_label)

        suggestions = [
            ("📋 整理今日待办", "帮我整理今天的待办事项"),
            ("💡 技术问答", "解答编程和技术问题"),
            ("📊 数据分析", "分析项目进度和数据"),
            ("📝 文档生成", "帮我生成会议纪要"),
        ]

        for icon_text, desc in suggestions:
            suggestion_btn = self._create_suggestion_card(icon_text, desc)
            scroll_layout.addWidget(suggestion_btn)

        # 示例对话
        scroll_layout.addWidget(QLabel(""))  # 间距

        # 用户消息
        user_msg = self._create_user_message("帮我整理一下今天的待办事项")
        scroll_layout.addWidget(user_msg)

        # AI回复
        ai_msg = self._create_ai_message(
            "好的，我已经为你整理了今天的待办事项：\n\n"
            "1. ✅ 完成登录注册功能联调\n"
            "2. 🔄 AES加密方案审核\n"
            "3. ⏰ 今晚8:00 集成测试进度会议\n"
            "4. 📝 周五提交课程设计文档\n\n"
            "需要我帮你设置提醒吗？"
        )
        scroll_layout.addWidget(ai_msg)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 输入区域
        input_area = self._create_input_area()
        layout.addWidget(input_area)

    def _create_suggestion_card(self, title, desc):
        """创建建议卡片"""
        card = QPushButton()
        card.setFixedHeight(64)
        card.setStyleSheet("""
            QPushButton {
                background-color: #fff;
                border: 2px solid #E7EFFC;
                border-radius: 14px;
                
                text-align: left;
            }
            QPushButton:hover {
                background-color: #F7F9FD;
                border: 2px solid #D1E3FA;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1E293B;")
        card_layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        card_layout.addWidget(desc_label)

        return card

    def _create_user_message(self, text):
        """创建用户消息"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)
        layout.setDirection(QHBoxLayout.RightToLeft)

        # 头像
        avatar = QLabel("我")
        avatar.setFixedSize(38, 38)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #2D6CF6, stop:1 #1E4FD0);
            color: white;
            border-radius: 19px;
            font-size: 14px;
            font-weight: 600;
        """)
        layout.addWidget(avatar)

        # 消息气泡
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(500)
        bubble.setTextFormat(Qt.PlainText)
        bubble.setContentsMargins(15, 12, 15, 12)  # 添加内边距
        bubble.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border-radius: 16px;
                font-size: 14px;
            }
        """)
        layout.addWidget(bubble)
        layout.addStretch()

        return container

    def _create_ai_message(self, text):
        """创建AI消息"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)

        # AI头像
        avatar = QLabel("✨")
        avatar.setFixedSize(38, 38)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #A78BFA, stop:1 #7C5CFC);
            border-radius: 19px;
            font-size: 18px;
        """)
        layout.addWidget(avatar)

        # 消息气泡
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(500)
        bubble.setTextFormat(Qt.PlainText)
        bubble.setContentsMargins(15, 12, 15, 12)  # 添加内边距
        bubble.setStyleSheet("""
            QLabel {
                background-color: #fff;
                color: #1E293B;
                border: 1px solid #E7EFFC;
                border-radius: 16px;
                font-size: 14px;
            }
        """)
        layout.addWidget(bubble)
        layout.addStretch()

        return container

    def _create_input_area(self):
        """创建输入区域"""
        input_container = QFrame()
        input_container.setFixedHeight(120)
        input_container.setStyleSheet("background-color: #EEF2FA;")

        layout = QVBoxLayout(input_container)
        layout.setContentsMargins(22, 14, 22, 14)

        # 输入框容器
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 18px;
            }
        """)

        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 8, 14, 8)
        input_layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        for icon in ["📎", "🎤"]:
            btn = QPushButton(icon)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 18px;
                }
                QPushButton:hover {
                    background-color: #F7F9FD;
                    border-radius: 6px;
                }
            """)
            toolbar.addWidget(btn)

        toolbar.addStretch()
        input_layout.addLayout(toolbar)

        # 输入框和发送按钮
        send_layout = QHBoxLayout()
        send_layout.setSpacing(12)
        send_layout.setAlignment(Qt.AlignBottom)

        text_input = QLineEdit()
        text_input.setPlaceholderText("向 AI 提问...")
        text_input.setFixedHeight(40)
        text_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 14px;
                color: #1E293B;
                
            }
        """)
        send_layout.addWidget(text_input)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(40, 40)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #A78BFA, stop:1 #7C5CFC);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #9677EA, stop:1 #6B4CEC);
            }
        """)
        send_layout.addWidget(send_btn)

        input_layout.addLayout(send_layout)

        layout.addWidget(input_frame)

        return input_container
