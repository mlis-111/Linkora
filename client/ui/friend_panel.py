from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QWidget, QLineEdit
from PyQt5.QtCore import Qt
from client.core.base_panel import BasePanel
from common.messages import MT


class FriendPanel(BasePanel):
    """好友面板 - 方案B样式"""

    def subscribe(self):
        self._build_ui()
        # 订阅在线用户列表更新
        self.app.net.on(MT.USER_LIST, self._on_user_list_update)

    def _on_user_list_update(self, msg):
        """处理用户列表更新（同步更新 all_users 确保新用户可见）"""
        self.app.state.online_users = msg.get("online_users", [])
        if msg.get("all_users"):
            self.app.state.all_users = msg["all_users"]
        self._refresh_user_list()

    def _build_ui(self):
        """构建好友列表界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QFrame()
        header.setFixedHeight(68)
        header.setStyleSheet("background-color: #F7F9FD;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        title = QLabel("好友列表")
        title.setStyleSheet("font-size: 19px; font-weight: 800; color: #1E293B;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        add_btn = QPushButton("+ 添加好友")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # 搜索框
        search_container = QWidget()
        search_container.setStyleSheet("background-color: #EEF2FA;")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(24, 16, 24, 16)

        search_box = QLineEdit()
        search_box.setPlaceholderText("🔍 搜索好友")
        search_box.setFixedHeight(42)
        search_box.setStyleSheet("""
            QLineEdit {
                background-color: #fff;
                border: none;
                border-radius: 14px;
                
                font-size: 14px;
                color: #1E293B;
                
            }
            QLineEdit::placeholder {
                color: #A9B6C8;
            }
        """)
        search_layout.addWidget(search_box)

        layout.addWidget(search_container)

        # 好友列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #EEF2FA;
            }
        """)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)  # 保存引用以便刷新
        self.scroll_layout.setContentsMargins(24, 12, 24, 12)
        self.scroll_layout.setSpacing(12)
        self.scroll_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 初始化时渲染用户列表
        self._refresh_user_list()

    def _refresh_user_list(self):
        """刷新用户列表显示"""
        # 如果还没有登录，不执行刷新
        if not self.app.state.all_users:
            return

        # 清空现有列表
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 获取所有用户和在线用户ID集合
        all_users = self.app.state.all_users
        online_user_ids = {u["user_id"] for u in self.app.state.online_users}

        # 渲染所有用户
        for user in all_users:
            user_id = user["user_id"]
            nickname = user.get("nickname") or user["username"]
            username = user["username"]

            # 判断是否在线
            is_online = user_id in online_user_ids
            status = "在线" if is_online else "离线"

            # 生成头像文字和颜色
            avatar_text = nickname[0] if nickname else username[0]
            colors = ["#6366F1", "#FB923C", "#34D399", "#F87171", "#F472B6", "#A78BFA"]
            color = colors[user_id % len(colors)]

            item = self._create_friend_item(nickname, avatar_text, color, status, is_online)
            self.scroll_layout.addWidget(item)

    def _create_friend_item(self, name, avatar_text, color, status, is_online):
        """创建好友列表项"""
        item = QFrame()
        item.setFixedHeight(72)
        item.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 16px;
                
            }
            QFrame:hover {
                background-color: #F7F9FD;
            }
        """)

        layout = QHBoxLayout(item)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # 头像（带在线状态）
        avatar_container = QWidget()
        avatar_container.setFixedSize(48, 48)

        avatar = QLabel(avatar_text, avatar_container)
        avatar.setFixedSize(48, 48)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background-color: {color};
            color: white;
            border-radius: 24px;
            font-size: 16px;
            font-weight: 600;
        """)

        # 在线状态点
        if is_online:
            status_dot = QLabel("●", avatar_container)
            status_dot.setFixedSize(12, 12)
            status_dot.setStyleSheet("color: #34D399; font-size: 12px;")
            status_dot.move(36, 36)

        layout.addWidget(avatar_container)

        # 信息区域
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #1E293B;")
        info_layout.addWidget(name_label)

        status_label = QLabel(status)
        status_label.setStyleSheet(f"font-size: 12px; color: {'#34D399' if is_online else '#94A3B8'};")
        info_layout.addWidget(status_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # 消息按钮
        msg_btn = QPushButton("💬")
        msg_btn.setFixedSize(38, 38)
        msg_btn.setStyleSheet("""
            QPushButton {
                background-color: #E7EFFC;
                color: #2D6CF6;
                border: none;
                border-radius: 12px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #D1E3FA;
            }
        """)
        layout.addWidget(msg_btn)

        return item
