from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QScrollArea, QFrame, QWidget)
from PyQt5.QtCore import Qt
from client.core.base_panel import BasePanel
from common.messages import MT


class ChatPanel(BasePanel):
    """聊天面板"""

    def subscribe(self):
        self._build_ui()
        # 订阅在线用户列表更新
        self.app.net.on(MT.USER_LIST, self._on_user_list_update)

    def _on_user_list_update(self, msg):
        """更新在线人数显示"""
        self.app.state.online_users = msg.get("online_users", [])
        self._update_online_count()
        self._refresh_conversation_list()

    def _build_ui(self):
        """构建聊天界面：左侧对话列表 + 右侧聊天区域"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧：对话列表
        self.conversation_list = self._create_conversation_list()
        main_layout.addWidget(self.conversation_list)

        # 右侧：聊天区域
        chat_area = QWidget()
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # 聊天头部
        header = self._create_chat_header()
        chat_layout.addWidget(header)

        # 消息区域
        messages_area = self._create_messages_area()
        chat_layout.addWidget(messages_area)

        # 输入区域
        composer = self._create_composer()
        chat_layout.addWidget(composer)

        main_layout.addWidget(chat_area, 1)  # stretch factor 1，占据剩余空间

    def _create_chat_header(self):
        """创建聊天头部"""
        header = QFrame()
        header.setFixedHeight(200)
        header.setStyleSheet("background-color: #F7F9FD;")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(52, 40, 52, 10)

        # 左侧信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(10)

        # 标题行
        title_row = QHBoxLayout()
        title = QLabel("公共聊天室")
        title.setStyleSheet("font-size: 37px; font-weight: 800; color: #1E293B;")
        title_row.addWidget(title)

        subtitle = QLabel("      软件2406 项目组")
        subtitle.setStyleSheet("font-size: 32px; color: #94A3B8; ")
        title_row.addWidget(subtitle)
        title_row.addStretch()

        info_layout.addLayout(title_row)

        # 状态行
        status_row = QHBoxLayout()
        status_dot = QLabel("●")
        status_dot.setStyleSheet("font-size: 22px; color: #34D399;")
        status_row.addWidget(status_dot)

        status_text = QLabel("6 人 · 5 在线    ")
        status_text.setStyleSheet("font-size: 22px; color: #6B7A90; height: 5px")
        status_row.addWidget(status_text)

        self.status_text_label = status_text  # 保存引用以便更新

        encrypted_badge = QLabel("🔒 消息已加密")
        encrypted_badge.setContentsMargins(12, 6, 12, 6)  
        encrypted_badge.setStyleSheet("""
            font-size: 22px;
            color: #2D6CF6;
            background-color: #E7EFFC;
            border-radius: 26px;
        """)
        status_row.addWidget(encrypted_badge)
        status_row.addStretch()

        info_layout.addLayout(status_row)

        layout.addLayout(info_layout)
        layout.addStretch()

        # 右侧按钮
        for icon in ["🔍", "👥", "⋯"]:
            btn = QPushButton(icon)
            btn.setFixedSize(76, 76)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #fff;
                    border: none;
                    border-radius: 12px;
                    font-size: 35px;
                }
                QPushButton:hover {
                    background-color: #F7F9FD;
                }
            """)
            layout.addWidget(btn)

        return header

    def _create_messages_area(self):
        """创建消息区域"""
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

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(46, 30, 26, 20)
        content_layout.setSpacing(28)
        content_layout.setAlignment(Qt.AlignTop)

        # 时间戳
        time_badge = QLabel("今天 11:00")
        time_badge.setAlignment(Qt.AlignCenter)
        time_badge.setStyleSheet("""
            font-size: 21px;
            color: #94A3B8;
            background-color: #E2E8F2;
            
            border-radius: 11px;
        """)
        content_layout.addWidget(time_badge, alignment=Qt.AlignCenter)

        # 示例消息
        messages = [
            ("郭玄同", "玄", "#FB923C", "10:58", "服务器框架我提交了，大家拉一下最新代码 👍", False),
            ("武家辉", "家", "#34D399", "11:02", "登录注册联调通过了 ✅", False),
            ("董钧豪", "钧", "#6366F1", "11:20", None, False),  # 文件传输
            ("朱俊基", "基", "#F87171", "16:24", "@全体成员 今晚 8:00 线上对集成测试进度", False),
            ("我", "我", "#2D6CF6", "16:25", "收到，文件已下载，晚上准时 👌", True),
        ]

        for name, avatar_text, color, time, message, is_own in messages:
            if message is None:
                # 文件传输卡片
                msg_widget = self._create_file_message(name, avatar_text, color, time, is_own)
            else:
                msg_widget = self._create_message(name, avatar_text, color, time, message, is_own)
            content_layout.addWidget(msg_widget)

        scroll.setWidget(content)
        return scroll

    def _create_message(self, name, avatar_text, color, time, message, is_own):
        """创建消息气泡"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(21)

        if is_own:
            layout.setDirection(QHBoxLayout.RightToLeft)

        # 头像
        avatar = QLabel(avatar_text)
        avatar.setFixedSize(64, 64)
        avatar.setAlignment(Qt.AlignCenter)

        if is_own:
            avatar.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color}, stop:1 #1E4FD0);
                color: white;
                border-radius: 19px;
                font-size: 30px;
                font-weight: 600;
            """)
        else:
            avatar.setStyleSheet(f"""
                background-color: {color};
                color: white;
                border-radius: 19px;
                font-size: 30px;
                font-weight: 600;
            """)
        layout.addWidget(avatar)

        # 消息内容区
        msg_widget = QWidget()
        msg_layout = QVBoxLayout(msg_widget)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(5)

        # 名称和时间
        if not is_own:
            info = QLabel(f"{name} · {time}")
            info.setStyleSheet("font-size: 11.5px; color: #94A3B8;")
            msg_layout.addWidget(info)
        else:
            info = QLabel(time)
            info.setStyleSheet("font-size: 11.5px; color: #94A3B8;")
            info.setAlignment(Qt.AlignRight)
            msg_layout.addWidget(info)

        # 消息气泡
        bubble = QLabel(message)
        bubble.setWordWrap(False)  # 改为False，避免不必要的换行
        # bubble.setMaximumWidth(1800)  # 移除最大宽度限制，让文字自然显示
        bubble.setTextFormat(Qt.PlainText)
        bubble.setContentsMargins(20, 15, 20, 15)  # 添加内边距

        if is_own:
            bubble.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #4F8DFD, stop:1 #2D6CF6);
                    color: white;
                    border-radius: 18px;
                    font-size: 24px;
                }
            """)
            bubble.setAlignment(Qt.AlignRight)
        else:
            bubble.setStyleSheet("""
                QLabel {
                    background-color: #fff;
                    color: #1E293B;
                    border: 1px solid #E7EFFC;
                    border-radius: 18px;
                    font-size: 24px;
                }
            """)

        msg_layout.addWidget(bubble, alignment=Qt.AlignRight if is_own else Qt.AlignLeft)

        layout.addWidget(msg_widget)
        layout.addStretch()

        return container

    def _create_file_message(self, name, avatar_text, color, time, is_own):
        """创建文件传输消息"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(11)

        # 头像
        avatar = QLabel(avatar_text)
        avatar.setFixedSize(64, 64)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background-color: {color};
            color: white;
            border-radius: 19px;
            font-size: 30px;
            font-weight: 600;
        """)
        layout.addWidget(avatar)

        # 文件卡片区
        card_layout = QVBoxLayout()
        card_layout.setSpacing(5)

        info = QLabel(f"{name} · {time}")
        info.setStyleSheet("font-size: 21.5px; color: #94A3B8;")
        card_layout.addWidget(info)

        # 文件卡片
        file_card = QFrame()
        file_card.setFixedWidth(610)
        file_card.setStyleSheet("""
            background-color: #fff;
            border-radius: 4px 16px 16px 16px;
            
            
        """)

        file_layout = QVBoxLayout(file_card)
        file_layout.setSpacing(21)

        # 文件信息行
        file_info_layout = QHBoxLayout()
        file_info_layout.setSpacing(12)

        # 文件图标
        file_icon = QLabel("📄")
        file_icon.setFixedSize(58, 58)
        file_icon.setAlignment(Qt.AlignCenter)
        file_icon.setStyleSheet("""
            background-color: #FEE2E2;
            border-radius: 13px;
            font-size: 38px;
        """)
        file_info_layout.addWidget(file_icon)

        # 文件名和大小
        file_text_layout = QVBoxLayout()
        file_text_layout.setSpacing(3)

        file_name = QLabel("AES加密方案.pdf")
        file_name.setStyleSheet("font-size: 32.5px; font-weight: 600; color: #1E293B;")
        file_text_layout.addWidget(file_name)

        file_size = QLabel("2.4 MB · 传输中")
        file_size.setStyleSheet("font-size: 30.5px; color: #94A3B8;")
        file_text_layout.addWidget(file_size)

        file_info_layout.addLayout(file_text_layout)

        # 下载按钮
        download_btn = QLabel("⬇")
        download_btn.setFixedSize(55, 55)
        download_btn.setAlignment(Qt.AlignCenter)
        download_btn.setStyleSheet("""
            background-color: #E7EFFC;
            border-radius: 17px;
            font-size: 25px;
        """)
        file_info_layout.addWidget(download_btn)

        file_layout.addLayout(file_info_layout)

        # 进度条
        progress_bg = QFrame()
        progress_bg.setFixedHeight(7)
        progress_bg.setStyleSheet("background-color: #EDF1F8; border-radius: 14px;")

        progress_bar = QFrame(progress_bg)
        progress_bar.setGeometry(0, 0, int(310 * 0.72), 7)
        progress_bar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4F8DFD, stop:1 #2D6CF6);
            border-radius: 14px;
        """)
        file_layout.addWidget(progress_bg)

        # 进度信息
        progress_info_layout = QHBoxLayout()
        progress_percent = QLabel("72%")
        progress_percent.setStyleSheet("font-size: 35.5px; color: #2D6CF6; font-weight: 700;")
        progress_info_layout.addWidget(progress_percent)

        progress_info_layout.addStretch()

        progress_detail = QLabel("1.7 / 2.4 MB · 480 KB/s")
        progress_detail.setStyleSheet("font-size: 32.5px; color: #94A3B8;")
        progress_info_layout.addWidget(progress_detail)

        file_layout.addLayout(progress_info_layout)

        card_layout.addWidget(file_card)

        layout.addLayout(card_layout)
        layout.addStretch()

        return container

    def _create_composer(self):
        """创建消息输入区"""
        composer = QFrame()
        composer.setFixedHeight(250)
        composer.setStyleSheet("background-color: #EEF2FA;")

        layout = QVBoxLayout(composer)
        layout.setContentsMargins(22, 14, 22, 24)

        # 输入框容器
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 18px;
            }
        """)

        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(14, 8, 14, 8)
        input_layout.setSpacing(8)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        for icon in ["📎", "😊", "📄"]:
            btn = QPushButton(icon)
            btn.setFixedSize(58, 58)
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 30px;
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
        send_layout.setSpacing(20)  # 增加间距，让按钮往左一点
        send_layout.setAlignment(Qt.AlignBottom)

        text_input = QLineEdit()
        text_input.setPlaceholderText("输入消息，Enter 发送…")
        text_input.setFixedHeight(200)
        text_input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 23px;
                color: #1E293B;

            }
        """)
        send_layout.addWidget(text_input)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(55, 55)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        send_layout.addWidget(send_btn)
        send_layout.addSpacing(20)  # 在按钮右边添加20px空隙

        input_layout.addLayout(send_layout)

        layout.addWidget(input_container)

        return composer

    def _update_online_count(self):
        """更新在线人数显示"""
        total = len(self.app.state.all_users)  # 总人数
        online = len(self.app.state.online_users)  # 在线人数
        self.status_text_label.setText(f"{total} 人 · {online} 在线    ")

    # ==================== 对话列表（从 MainWindow 移入） ====================

    _AVATAR_COLORS = [
        "#6366F1", "#FB923C", "#F472B6", "#34D399",
        "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
        "#4ADE80", "#E879F9",
    ]

    def _create_conversation_list(self):
        """创建对话列表"""
        conv_panel = QFrame()
        conv_panel.setFixedWidth(500)
        conv_panel.setStyleSheet("background-color: #F7F9FD;")

        layout = QVBoxLayout(conv_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(35, 50, 35, 34)

        title = QLabel("消息")
        title.setStyleSheet("font-size: 42px; font-weight: 800; color: #1E293B;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        add_btn = QPushButton("+")
        add_btn.setFixedSize(50, 50)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #E7EFFC;
                color: #2D6CF6;
                border: none;
                border-radius: 12px;
                font-size: 35px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D1E3FA;
            }
        """)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # 搜索框
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(32, 0, 32, 24)

        search_box = QLineEdit()
        search_box.setPlaceholderText("🔍 搜索用户或消息")
        search_box.setFixedHeight(64)
        search_box.setStyleSheet("""
            QLineEdit {
                background-color: #fff;
                border: none;
                border-radius: 14px;
                font-size: 20px;
                color: #1E293B;
            }
            QLineEdit::placeholder {
                color: #A9B6C8;
            }
        """)
        search_layout.addWidget(search_box)
        layout.addWidget(search_container)

        # 对话列表滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
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

        self.conv_scroll_content = QWidget()
        self.conv_scroll_layout = QVBoxLayout(self.conv_scroll_content)
        self.conv_scroll_layout.setContentsMargins(32, 0, 32, 0)
        self.conv_scroll_layout.setSpacing(4)
        self.conv_scroll_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self.conv_scroll_content)
        layout.addWidget(scroll)

        # 首次填充
        self._refresh_conversation_list()

        return conv_panel

    def _create_conversation_item(self, name, message, time, is_active, avatar_text, avatar_color, unread=0):
        """创建对话列表项"""
        item = QFrame()
        item.setFixedHeight(105)

        if is_active:
            item.setStyleSheet("""
                QFrame {
                    background-color: #fff;
                    border-radius: 16px;
                }
            """)
        else:
            item.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border-radius: 16px;
                }
                QFrame:hover {
                    background-color: rgba(255,255,255,0.5);
                }
            """)

        layout = QHBoxLayout(item)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(20)

        # 头像
        avatar = QLabel(avatar_text)
        avatar.setFixedSize(52, 52)
        avatar.setAlignment(Qt.AlignCenter)
        if avatar_color.startswith('q'):  # 渐变色
            avatar.setStyleSheet(f"""
                background: {avatar_color};
                color: white;
                border-radius: 23px;
                font-size: 26px;
                font-weight: 600;
            """)
        else:
            avatar.setStyleSheet(f"""
                background-color: {avatar_color};
                color: white;
                border-radius: 23px;
                font-size: 26px;
                font-weight: 600;
            """)
        layout.addWidget(avatar)

        # 文字区域
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)

        # 名称和时间
        name_row = QHBoxLayout()
        name_row.setSpacing(0)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 26px; font-weight: {'700' if is_active else '600'}; color: #1E293B;")
        name_row.addWidget(name_label)

        name_row.addStretch()

        time_label = QLabel(time)
        time_label.setStyleSheet("font-size: 21px; color: #A9B6C8;")
        name_row.addWidget(time_label)

        text_layout.addLayout(name_row)

        # 消息内容和未读
        msg_row = QHBoxLayout()
        msg_row.setSpacing(0)

        msg_label = QLabel(message)
        msg_label.setStyleSheet("font-size: 21px; color: #6B7A90;")
        msg_label.setWordWrap(False)
        msg_label.setSizePolicy(msg_label.sizePolicy().horizontalPolicy(), msg_label.sizePolicy().verticalPolicy())
        msg_row.addWidget(msg_label, 1)

        if unread > 0:
            msg_row.addSpacing(8)
            unread_badge = QLabel(str(unread))
            unread_badge.setFixedSize(19, 19)
            unread_badge.setAlignment(Qt.AlignCenter)
            unread_badge.setStyleSheet("""
                background-color: #FB7185;
                color: white;
                border-radius: 10px;
                font-size: 11px;
                font-weight: 700;
            """)
            msg_row.addWidget(unread_badge)

        text_layout.addLayout(msg_row)

        layout.addWidget(text_widget, 1)

        return item

    def _refresh_conversation_list(self):
        """根据在线用户动态刷新对话列表"""
        while self.conv_scroll_layout.count():
            child = self.conv_scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 固定项：公共聊天室 + AI 助手
        fixed = [
            ("公共聊天室", "💬 点击进入公共聊天室", "", True, "👥",
             "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4F8DFD, stop:1 #2D6CF6)"),
            ("AI 助手", "✨ 智能问答，随时为你解答", "", False, "✨",
             "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #A78BFA, stop:1 #7C5CFC)"),
        ]
        for name, msg_text, time, active, avatar, color in fixed:
            item = self._create_conversation_item(
                name, msg_text, time, active, avatar, color)
            self.conv_scroll_layout.addWidget(item)

        # 在线用户
        online = self.app.state.online_users
        for i, u in enumerate(online):
            uid = u.get("user_id")
            if uid == self.app.state.user_id:
                continue
            name = u.get("nickname") or u.get("username", "")
            avatar_text = name[0] if name else "?"
            color = self._AVATAR_COLORS[i % len(self._AVATAR_COLORS)]
            item = self._create_conversation_item(
                name, "在线", "", False, avatar_text, color)
            self.conv_scroll_layout.addWidget(item)

        self.conv_scroll_layout.addStretch()
