"""
登录/注册窗口 — 武家辉

提供用户登录和注册界面，支持在登录/注册模式间切换。
遵守 common/messages.py 中定义的消息契约。

@author 武家辉
"""

from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QFrame, QHBoxLayout
from PyQt5.QtCore import Qt
from common.messages import MT
from client.core.base_panel import BasePanel


class LoginWindow(BasePanel):
    """登录/注册窗口

    支持登录和注册两种模式，通过底部按钮切换。
    """

    MODE_LOGIN = "login"
    MODE_REGISTER = "register"

    def subscribe(self):
        """订阅登录和注册响应消息"""
        self.net.on(MT.LOGIN_RESP, self._on_login_resp)
        self.net.on(MT.REGISTER_RESP, self._on_register_resp)
        self._mode = self.MODE_LOGIN
        self._build_ui()

    def _build_ui(self):
        """构建UI"""
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
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B;")
        layout.addWidget(title, alignment=Qt.AlignCenter)

        # 副标题
        subtitle = QLabel("局域网即时通信")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #94A3B8;")
        layout.addWidget(subtitle, alignment=Qt.AlignCenter)

        # 登录/注册卡片
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
        username_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B;")
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
        password_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B;")
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
        self.password_entry.returnPressed.connect(self._submit)
        card_layout.addWidget(self.password_entry)

        # 确认密码（注册模式显示）
        confirm_label = QLabel("确认密码")
        confirm_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B;")
        self.confirm_label = confirm_label
        card_layout.addWidget(confirm_label)
        confirm_label.hide()

        self.confirm_entry = QLineEdit()
        self.confirm_entry.setPlaceholderText("请再次输入密码")
        self.confirm_entry.setEchoMode(QLineEdit.Password)
        self.confirm_entry.setFixedHeight(46)
        self.confirm_entry.setStyleSheet("""
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
        self.confirm_entry.returnPressed.connect(self._submit)
        card_layout.addWidget(self.confirm_entry)
        self.confirm_entry.hide()

        # 操作按钮
        self.action_btn = QPushButton("登录")
        self.action_btn.setFixedHeight(48)
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setStyleSheet("""
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
        self.action_btn.clicked.connect(self._submit)
        card_layout.addWidget(self.action_btn)

        # 模式切换按钮
        self.switch_btn = QPushButton("没有账号？去注册")
        self.switch_btn.setFixedHeight(36)
        self.switch_btn.setCursor(Qt.PointingHandCursor)
        self.switch_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #4F8DFD;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #2D6CF6;
            }
        """)
        self.switch_btn.clicked.connect(self._toggle_mode)
        card_layout.addWidget(self.switch_btn)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 12px;
            color: #FB7185;
            background-color: #FFF1F2;
            border-radius: 10px;
            padding: 8px;
        """)
        self.status_label.hide()
        card_layout.addWidget(self.status_label)

        layout.addWidget(card, alignment=Qt.AlignCenter)

    def _toggle_mode(self):
        """切换登录/注册模式"""
        if self._mode == self.MODE_LOGIN:
            self._mode = self.MODE_REGISTER
            self.action_btn.setText("注册")
            self.switch_btn.setText("已有账号？去登录")
            self.confirm_label.show()
            self.confirm_entry.show()
        else:
            self._mode = self.MODE_LOGIN
            self.action_btn.setText("登录")
            self.switch_btn.setText("没有账号？去注册")
            self.confirm_label.hide()
            self.confirm_entry.hide()
        self.status_label.hide()

    def _submit(self):
        """提交登录或注册请求"""
        username = self.username_entry.text().strip()
        password = self.password_entry.text().strip()

        if not username or not password:
            self.status_label.setText("用户名和密码不能为空")
            self.status_label.show()
            return

        if self._mode == self.MODE_LOGIN:
            self.net.send({
                "type": MT.LOGIN,
                "username": username,
                "password": password
            })
            self.status_label.setText("登录中...")
            self.status_label.show()
        else:
            confirm = self.confirm_entry.text().strip()
            if password != confirm:
                self.status_label.setText("两次输入的密码不一致")
                self.status_label.show()
                return
            if len(password) < 6:
                self.status_label.setText("密码长度不能少于6位")
                self.status_label.show()
                return
            self.net.send({
                "type": MT.REGISTER,
                "username": username,
                "password": password
            })
            self.status_label.setText("注册中...")
            self.status_label.show()

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
            self.state.all_users = msg.get("all_users", [])

            # 隐藏登录窗口，显示主界面
            self.hide()
            self.app.main.show_main()
        else:
            # 登录失败
            reason = msg.get("reason", "登录失败")
            self.status_label.setText(reason)
            self.status_label.show()

    def _on_register_resp(self, msg):
        """处理注册响应

        Args:
            msg: 消息字典
        """
        if msg.get("ok"):
            # 注册成功，切回登录模式并提示
            if self._mode == self.MODE_REGISTER:
                self._toggle_mode()
            self.status_label.setStyleSheet("""
                font-size: 12px;
                color: #10B981;
                background-color: #ECFDF5;
                border-radius: 10px;
                padding: 8px;
            """)
            self.status_label.setText("注册成功，请登录")
            self.status_label.show()
        else:
            # 注册失败
            reason = msg.get("reason", "注册失败")
            self.status_label.setStyleSheet("""
                font-size: 12px;
                color: #FB7185;
                background-color: #FFF1F2;
                border-radius: 10px;
                padding: 8px;
            """)
            self.status_label.setText(reason)
            self.status_label.show()
