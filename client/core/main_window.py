from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QLabel, QPushButton, QStackedWidget, QFrame)
from PyQt5.QtCore import Qt
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

        # 右侧内容区（StackedWidget用于切换不同面板，对话列表已移至 ChatPanel 内部）
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

        # 底部头像
        self._avatar_btn = QPushButton("我")
        self._avatar_btn.setFixedSize(67, 67)
        self._avatar_btn.setStyleSheet("""
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
        layout.addWidget(self._avatar_btn, alignment=Qt.AlignHCenter)

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
        name = self.app.state.username or ""
        self._avatar_btn.setText(name[0] if name else "我")
        self.showMaximized()

    def _on_user_list(self, msg):
        self.app.state.online_users = msg.get("online_users", [])

    def _on_disconnected(self, msg):
        """服务器断开连接——自动清理 UI + 回登录界面"""
        self.app.state.user_id = None
        self.app.state.username = None
        self.app.state.online_users = []
        self.hide()
        self.app.login_win.show()
