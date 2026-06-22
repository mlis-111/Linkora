from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QFrame
from PyQt5.QtCore import Qt
from common.messages import MT
from client.core.base_panel import BasePanel


class LoginWindow(BasePanel):
    """登录窗口 - 方案B样式"""

    def subscribe(self):
        """订阅登录响应消息"""
        self.net.on(MT.LOGIN_RESP, self._on_login_resp)
        self._build_ui()

    def _build_ui(self):
        """构建UI - 方案B温和校园风格"""
        # 设置背景色
        self.setStyleSheet("background-color: #EEF2FA;")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)

        # Logo
        logo = QLabel("💬")
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("""
            font-size: 48px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #4F8DFD, stop:1 #2D6CF6);
            color: white;
            border-radius: 28px;
            
            min-width: 80px;
            max-width: 80px;
            min-height: 80px;
            max-height: 80px;
        """)
        layout.addWidget(logo, alignment=Qt.AlignCenter)

        # 标题
        title = QLabel("校园通")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B; ")
        layout.addWidget(title, alignment=Qt.AlignCenter)

        # 副标题
        subtitle = QLabel("局域网即时通信")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #94A3B8; ")
        layout.addWidget(subtitle, alignment=Qt.AlignCenter)

        # 登录卡片
        card = QFrame()
        card.setFixedWidth(380)
        card.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(18)

        # 用户名输入
        username_label = QLabel("用户名")
        username_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B; ")
        card_layout.addWidget(username_label)

        self.username_entry = QLineEdit()
        self.username_entry.setPlaceholderText("请输入用户名")
        self.username_entry.setFixedHeight(46)
        self.username_entry.setStyleSheet("""
            QLineEdit {
                background-color: #F7F9FD;
                border: 2px solid #E7EFFC;
                border-radius: 12px;
                
                font-size: 14px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border: 2px solid #4F8DFD;
                background-color: #fff;
            }
            QLineEdit::placeholder {
                color: #A9B6C8;
            }
        """)
        card_layout.addWidget(self.username_entry)

        # 密码输入
        password_label = QLabel("密码")
        password_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B;  ")
        card_layout.addWidget(password_label)

        self.password_entry = QLineEdit()
        self.password_entry.setPlaceholderText("请输入密码")
        self.password_entry.setEchoMode(QLineEdit.Password)
        self.password_entry.setFixedHeight(46)
        self.password_entry.setStyleSheet("""
            QLineEdit {
                background-color: #F7F9FD;
                border: 2px solid #E7EFFC;
                border-radius: 12px;
                
                font-size: 14px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border: 2px solid #4F8DFD;
                background-color: #fff;
            }
            QLineEdit::placeholder {
                color: #A9B6C8;
            }
        """)
        self.password_entry.returnPressed.connect(self._login)
        card_layout.addWidget(self.password_entry)

        # 登录按钮
        btn = QPushButton("登录")
        btn.setFixedHeight(48)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: 700;
                
                
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2D6CF6, stop:1 #1E4FD0);
            }
        """)
        btn.clicked.connect(self._login)
        card_layout.addWidget(btn)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #FB7185;
            background-color: #FFF1F2;
            
            border-radius: 10px;
            
        """)
        self.status_label.hide()
        card_layout.addWidget(self.status_label)

        layout.addWidget(card, alignment=Qt.AlignCenter)

        # 底部提示
        footer = QLabel("首次使用？请联系管理员注册账号")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 12px; color: #94A3B8; ")
        layout.addWidget(footer, alignment=Qt.AlignCenter)

    def _login(self):
        """处理登录按钮点击"""
        username = self.username_entry.text().strip()
        password = self.password_entry.text().strip()

        if not username or not password:
            self.status_label.setText("用户名和密码不能为空")
            return

        self.net.send({
            "type": MT.LOGIN,
            "username": username,
            "password": password
        })
        self.status_label.setText("登录中...")

    def _on_login_resp(self, msg):
        """处理登录响应

        Args:
            msg: 消息字典
        """
        if msg.get("ok"):
            # 登录成功
            self.state.user_id = msg["user_id"]
            self.state.username = msg.get("nickname", msg.get("username", ""))
            self.state.online_users = msg.get("online_users", [])
            self.state.all_users = msg.get("all_users", [])  # 接收所有用户列表

            # 隐藏登录窗口，显示主界面
            self.hide()
            self.app.main.show_main()
        else:
            # 登录失败
            reason = msg.get("reason", "登录失败")
            self.status_label.setText(reason)
