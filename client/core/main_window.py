from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QLabel, QPushButton, QScrollArea, QStackedWidget,
                             QLineEdit, QTextEdit, QFrame)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
from common.messages import MT


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("校园通 - 局域网即时通信")
        self.setMinimumSize(1240, 800)
        self._build_ui()
        self.app.net.on(MT.USER_LIST, self._on_user_list)
        self.app.net.on("__disconnected__", self._on_disconnected)

    def _build_ui(self):
        """构建主界面UI"""
        # 设置整体背景色
        self.setStyleSheet("QMainWindow { background-color: #EEF2FA; }")

        # 主容器
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航栏
        nav_rail = self._create_nav_rail()
        main_layout.addWidget(nav_rail)

        # 中间对话列表
        self.conversation_list = self._create_conversation_list()
        main_layout.addWidget(self.conversation_list)

        # 右侧内容区（StackedWidget用于切换不同面板）
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #EEF2FA;")
        main_layout.addWidget(self.content_stack, 1)  # stretch factor 1，占据剩余空间

    def _create_nav_rail(self):
        """创建左侧导航栏"""
        nav = QFrame()
        nav.setFixedWidth(130)  # 增加宽度
        nav.setStyleSheet("background-color: #fff;")

        layout = QVBoxLayout(nav)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.setSpacing(62)
        layout.setAlignment(Qt.AlignTop)

        # 导航按钮数据
        nav_items = [
            ("消息", "💬", "chat"),
            ("好友", "👥", "friend"),
            ("文件", "📁", "file"),
            ("AI", "✨", "ai"),
        ]

        self.nav_buttons = {}  # 存储导航按钮用于切换状态
        for label, icon, panel_key in nav_items:
            btn = self._create_nav_button(label, icon, panel_key == "chat", panel_key)
            self.nav_buttons[panel_key] = btn
            layout.addWidget(btn, alignment=Qt.AlignHCenter)

        layout.addStretch()

        # 底部设置和头像
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(76, 76)  # 增大尺寸
        settings_btn.setStyleSheet("""
            QPushButton {
                border: none;
                font-size: 40px;
                color: #94A3B8;
                background: transparent;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: #F7F9FD;
            }
        """)
        layout.addWidget(settings_btn, alignment=Qt.AlignHCenter)

        avatar_btn = QPushButton("我")
        avatar_btn.setFixedSize(67, 67)  # 增大头像
        avatar_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2D6CF6, stop:1 #1E4FD0);
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 36px;
                font-weight: 700;
            }
        """)
        layout.addWidget(avatar_btn, alignment=Qt.AlignHCenter)

        return nav

    def _create_nav_button(self, text, icon, is_active, panel_key):
        """创建导航按钮"""
        container = QWidget()
        container.setFixedSize(100, 100)  # 增大尺寸
        container.panel_key = panel_key  # 保存panel_key
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)

        # 图标按钮
        icon_btn = QPushButton(icon)
        icon_btn.setFixedSize(67, 67)  # 增大图标按钮
        icon_btn.clicked.connect(lambda: self.switch_panel(panel_key))  # 添加点击事件

        if is_active:
            icon_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #4F8DFD, stop:1 #2D6CF6);
                    color: white;
                    border: none;
                    border-radius: 16px;
                    font-size: 35px;

                }
            """)
        else:
            icon_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #94A3B8;
                    border: none;
                    border-radius: 16px;
                    font-size: 35px;
                }
                QPushButton:hover {
                    background: #F7F9FD;
                }
            """)

        container.icon_btn = icon_btn  # 保存引用以便后续更新样式
        layout.addWidget(icon_btn, alignment=Qt.AlignCenter)

        # 文字标签
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        if is_active:
            label.setStyleSheet("font-size: 23px; color: #2D6CF6; font-weight: 700;")
        else:
            label.setStyleSheet("font-size: 23px; color: #94A3B8;")
        container.label = label  # 保存引用以便后续更新样式
        layout.addWidget(label, alignment=Qt.AlignCenter)

        return container

    def _create_conversation_list(self):
        """创建对话列表"""
        conv_panel = QFrame()
        conv_panel.setFixedWidth(500)  # 进一步增加宽度
        conv_panel.setStyleSheet("background-color: #F7F9FD;")

        layout = QVBoxLayout(conv_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(35, 50, 35, 34)

        title = QLabel("消息")
        title.setStyleSheet("font-size: 42px; font-weight: 800; color: #1E293B;")  # 增大字体
        header_layout.addWidget(title)

        header_layout.addStretch()

        add_btn = QPushButton("+")
        add_btn.setFixedSize(50, 50)  # 增大按钮
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
        search_box.setFixedHeight(64)  # 增加高度
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
        item.setFixedHeight(105)  # 增加高度

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
        layout.setContentsMargins(14, 14, 14, 14)  # 增加内边距
        layout.setSpacing(20)  # 增加间距

        # 头像
        avatar = QLabel(avatar_text)
        avatar.setFixedSize(52, 52)  # 增大头像
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

    def add_panel(self, key, panel):
        """由app.py调用注册面板，接口与原方案一致"""
        self.app.panels[key] = panel
        self.content_stack.addWidget(panel)
        # 默认显示第一个面板（聊天面板）
        if key == "chat":
            self.content_stack.setCurrentWidget(panel)

    def switch_panel(self, panel_key):
        """切换面板"""
        if panel_key in self.app.panels:
            panel = self.app.panels[panel_key]
            self.content_stack.setCurrentWidget(panel)

            # 更新所有导航按钮的样式
            for key, btn_container in self.nav_buttons.items():
                is_active = (key == panel_key)
                icon_btn = btn_container.icon_btn
                label = btn_container.label

                if is_active:
                    icon_btn.setStyleSheet("""
                        QPushButton {
                            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #4F8DFD, stop:1 #2D6CF6);
                            color: white;
                            border: none;
                            border-radius: 16px;
                            font-size: 35px;
                        }
                    """)
                    label.setStyleSheet("font-size: 23px; color: #2D6CF6; font-weight: 700;")
                else:
                    icon_btn.setStyleSheet("""
                        QPushButton {
                            background: transparent;
                            color: #94A3B8;
                            border: none;
                            border-radius: 16px;
                            font-size: 35px;
                        }
                        QPushButton:hover {
                            background: #F7F9FD;
                        }
                    """)
                    label.setStyleSheet("font-size: 23px; color: #94A3B8;")

    def show_main(self):
        """登录成功后由login面板调用，接口与原方案一致"""
        self._refresh_conversation_list()
        self.showMaximized()  # 登录成功后最大化显示

    def _on_user_list(self, msg):
        self.app.state.online_users = msg.get("online_users", [])
        self._refresh_conversation_list()

    # ── 对话列表刷新 ──────────────────────────────────

    _AVATAR_COLORS = [
        "#6366F1", "#FB923C", "#F472B6", "#34D399",
        "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
        "#4ADE80", "#E879F9",
    ]

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

    def _on_disconnected(self, msg):
        """服务器断开连接——自动清理 UI + 回登录界面"""
        self.app.state.user_id = None
        self.app.state.username = None
        self.app.state.online_users = []
        self._refresh_conversation_list()
        self.hide()
        self.app.login_win.show()
