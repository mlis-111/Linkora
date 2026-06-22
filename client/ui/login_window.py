from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout
from common.messages import MT
from client.core.base_panel import BasePanel


class LoginWindow(BasePanel):
    """登录窗口（阶段0冒烟桩）"""

    def subscribe(self):
        """订阅登录响应消息"""
        self.net.on(MT.LOGIN_RESP, self._on_login_resp)
        self._build_ui()

    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.addStretch()

        # 标题
        title = QLabel("校园IM登录")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # 用户名输入
        layout.addWidget(QLabel("用户名:"))
        self.username_entry = QLineEdit()
        self.username_entry.setPlaceholderText("请输入用户名")
        self.username_entry.setFixedWidth(250)
        layout.addWidget(self.username_entry)

        # 密码输入
        layout.addWidget(QLabel("密码:"))
        self.password_entry = QLineEdit()
        self.password_entry.setPlaceholderText("请输入密码")
        self.password_entry.setEchoMode(QLineEdit.Password)
        self.password_entry.setFixedWidth(250)
        layout.addWidget(self.password_entry)

        # 登录按钮
        btn = QPushButton("登录")
        btn.setFixedWidth(250)
        btn.clicked.connect(self._login)
        layout.addWidget(btn)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: red;")
        layout.addWidget(self.status_label)

        layout.addStretch()

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

            # 隐藏登录窗口，显示主界面
            self.hide()
            self.app.main.show_main()
        else:
            # 登录失败
            reason = msg.get("reason", "登录失败")
            self.status_label.setText(reason)
