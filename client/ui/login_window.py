"""
登录/注册窗口 — 武家辉

提供用户登录和注册界面，支持在登录/注册模式间切换。
遵守 common/messages.py 中定义的消息契约。

@author 武家辉
"""

from PyQt5.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QCheckBox, QDesktopWidget, QApplication
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QPixmap, QPainter, QBrush
from common.messages import MT
from client.core.base_panel import BasePanel


class LoginWindow(BasePanel):
    """登录/注册窗口"""

    MODE_LOGIN = "login"
    MODE_REGISTER = "register"

    def subscribe(self):
        self.net.on(MT.LOGIN_RESP, self._on_login_resp)
        self.net.on(MT.REGISTER_RESP, self._on_register_resp)
        self._mode = self.MODE_LOGIN
        self._build_ui()
        self._settings = QSettings("CampusIM", "login")
        self.login_username.textChanged.connect(self._on_username_changed)

    def _on_username_changed(self, text):
        if not text:
            return
        saved = self._settings.value(text.strip(), "")
        if saved:
            self.login_password.setText(saved)
            self.remember_cb.setChecked(True)

    # ── 工具方法 ──────────────────────────────

    def _rounded_pixmap(self, path, size, radius):
        """返回圆角裁剪后的 QPixmap"""
        pixmap = QPixmap(path).scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)
        p = QPainter(rounded)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(pixmap))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(pixmap.rect(), radius, radius)
        p.end()
        return rounded

    def _make_input(self, placeholder, echo=None, focused=False):
        e = QLineEdit()
        e.setPlaceholderText(placeholder)
        e.setFixedHeight(72)
        if echo:
            e.setEchoMode(echo)
        border = "#2D6CF6" if focused else "#E2E8F2"
        bg = "#F5F8FF" if focused else "#fff"
        e.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 15px;
                font-size: 25px;
                color: #1E293B;
                padding: 0 17px;
            }}
            QLineEdit::placeholder {{
                color: #C0CADB;
                font-size: 5px;
            }}
        """)
        return e

    def _make_primary_btn(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(78)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border: none;
                border-radius: 19px;
                font-size: 25px;
                font-weight: 800;
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
        btn.clicked.connect(self._submit)
        return btn

    def _make_switch_btn(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(72)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F8FF;
                border: 2px solid #D4E2FC;
                border-radius: 17px;
                font-size: 24px;
                font-weight: 700;
                color: #2D6CF6;
            }
            QPushButton:hover {
                background-color: #EEF4FF;
                border: 2px solid #B8D0FC;
            }
        """)
        btn.clicked.connect(self._toggle_mode)
        return btn

    def _make_divider(self, text):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        left = QFrame()
        left.setFixedHeight(2)
        left.setStyleSheet("background-color: #E5EAF3;")
        right = QFrame()
        right.setFixedHeight(2)
        right.setStyleSheet("background-color: #E5EAF3;")
        label = QLabel(text)
        label.setStyleSheet("font-size: 20px; color: #C0CADB;")
        row.addWidget(left)
        row.addSpacing(14)
        row.addWidget(label)
        row.addSpacing(14)
        row.addWidget(right)
        return row

    def _make_field_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 20px; font-weight: 600; color: #475569;")
        return lbl

    def _make_status_bar(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignCenter)
        dot = QLabel("●")
        dot.setStyleSheet("font-size: 16px; color: #34D399;")
        text = QLabel("服务器连接正常")
        text.setStyleSheet("font-size: 20px; color: #64748B; font-weight: 500;")
        addr = QLabel("127.0.0.1:9000")
        addr.setStyleSheet("font-size: 20px; color: #C0CADB;")
        row.addWidget(dot)
        row.addSpacing(7)
        row.addWidget(text)
        row.addSpacing(10)
        row.addWidget(addr)
        return row

    # ── 构建UI ──────────────────────────────────

    def _build_ui(self):
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background-color: #EEF2FA;"
            "font-family: 'SimHei', 'Microsoft YaHei', sans-serif;")

        self.login_card = self._build_login_card()
        self.root_layout.addWidget(self.login_card, alignment=Qt.AlignCenter)

        self.register_card = self._build_register_card()
        self.root_layout.addWidget(self.register_card, alignment=Qt.AlignCenter)
        self.register_card.hide()

        cp = QDesktopWidget().availableGeometry().center()
        self.move(cp.x() - 320, cp.y() - 520)

    def _build_login_card(self):
        card = QFrame()
        card.setFixedWidth(640)
        card.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 24px;
                font-family: 'SimHei', 'Microsoft YaHei', sans-serif;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(53, 43, 53, 41)
        layout.setSpacing(0)

        # 标题区域
        title_area = QVBoxLayout()
        title_area.setAlignment(Qt.AlignCenter)
        title_area.setSpacing(16)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(180, 180)
        logo.setPixmap(self._rounded_pixmap("icon/logo.png", 180, 50))
        title_area.addWidget(logo, alignment=Qt.AlignCenter)
        title_area.addSpacing(36)

        title = QLabel("欢迎回来")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 44px; font-weight: 900; color: #1E293B;")
        title_area.addWidget(title)

        subtitle = QLabel("使用校园账号登录校园通")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 25px; color: #94A3B8; margin-bottom: 12px;")
        title_area.addWidget(subtitle)

        layout.addLayout(title_area)
        layout.addSpacing(45)

        # 用户名
        layout.addWidget(self._make_field_label("用户名"))
        layout.addSpacing(11)
        self.login_username = self._make_input("输入用户名")
        self.login_username.returnPressed.connect(self._submit)
        layout.addWidget(self.login_username)
        layout.addSpacing(34)

        # 密码
        layout.addWidget(self._make_field_label("密码"))
        layout.addSpacing(11)
        self.login_password = self._make_input("输入密码",
                                                echo=QLineEdit.Password)
        self.login_password.returnPressed.connect(self._submit)
        layout.addWidget(self.login_password)
        layout.addSpacing(18)

        # 记住我 + 忘记密码
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.remember_cb = QCheckBox("记住我")
        self.remember_cb.setStyleSheet("""
            QCheckBox {
                font-size: 20px;
                color: #64748B;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 22px;
                height: 22px;
                border-radius: 7px;
                border: 2px solid #2D6CF6;
                background-color: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #2D6CF6;
                border: 2px solid #2D6CF6;
            }
        """)
        forgot = QLabel("忘记密码？")
        forgot.setStyleSheet("font-size: 20px; color: #2D6CF6; font-weight: 600;")
        forgot.setCursor(Qt.PointingHandCursor)
        row.addWidget(self.remember_cb)
        row.addStretch()
        row.addWidget(forgot)
        layout.addLayout(row)
        layout.addSpacing(35)

        self.login_btn = self._make_primary_btn("登录 →")
        layout.addWidget(self.login_btn)
        layout.addSpacing(29)

        layout.addLayout(self._make_divider("还没有账号？"))
        layout.addSpacing(29)

        self.to_register_btn = self._make_switch_btn("＋ 立即注册")
        layout.addWidget(self.to_register_btn)
        layout.addSpacing(34)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size: 20px;
            color: #FB7185;
            background-color: #FFF1F2;
            border-radius: 12px;
            padding: 10px;
        """)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        layout.addStretch()
        layout.addSpacing(16)
        layout.addLayout(self._make_status_bar())

        return card

    def _build_register_card(self):
        card = QFrame()
        card.setFixedWidth(640)
        card.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 24px;
                font-family: 'SimHei', 'Microsoft YaHei', sans-serif;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(53, 41, 53, 41)
        layout.setSpacing(0)

        title_area = QVBoxLayout()
        title_area.setAlignment(Qt.AlignCenter)
        title_area.setSpacing(16)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(180, 180)
        logo.setPixmap(self._rounded_pixmap("icon/logo.png", 180, 50))
        title_area.addWidget(logo, alignment=Qt.AlignCenter)
        title_area.addSpacing(36)

        title = QLabel("创建账户")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 44px; font-weight: 900; color: #1E293B;")
        title_area.addWidget(title)

        subtitle = QLabel("加入你的校园通信团队")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 25px; color: #94A3B8;")
        title_area.addWidget(subtitle)

        layout.addLayout(title_area)
        layout.addSpacing(50)

        # 用户名 + 昵称
        row = QHBoxLayout()
        row.setSpacing(18)
        row.setContentsMargins(0, 0, 0, 0)

        col_user = QVBoxLayout()
        col_user.setSpacing(10)
        col_user.addWidget(self._make_field_label("用户名"))
        self.reg_username = self._make_input("用于登录")
        self.reg_username.returnPressed.connect(self._submit)
        col_user.addWidget(self.reg_username)

        col_nick = QVBoxLayout()
        col_nick.setSpacing(10)
        col_nick.addWidget(self._make_field_label("昵称"))
        self.reg_nickname = self._make_input("展示给他人")
        self.reg_nickname.returnPressed.connect(self._submit)
        col_nick.addWidget(self.reg_nickname)

        row.addLayout(col_user)
        row.addLayout(col_nick)
        layout.addLayout(row)
        layout.addSpacing(30)

        # 密码
        layout.addWidget(self._make_field_label("密码"))
        layout.addSpacing(16)
        self.reg_password = self._make_input("至少 6 位", echo=QLineEdit.Password)
        self.reg_password.returnPressed.connect(self._submit)
        layout.addWidget(self.reg_password)
        layout.addSpacing(30)

        # 确认密码
        layout.addWidget(self._make_field_label("确认密码"))
        layout.addSpacing(16)
        confirm_frame = QFrame()
        confirm_frame.setStyleSheet("background: transparent;")
        cf_layout = QHBoxLayout(confirm_frame)
        cf_layout.setContentsMargins(0, 0, 0, 0)
        cf_layout.setSpacing(0)

        self.reg_confirm = self._make_input("请再次输入密码",
                                             echo=QLineEdit.Password)
        self.reg_confirm.setStyleSheet("""
            QLineEdit {
                background-color: #F0FDF6;
                border: 2px solid #34D399;
                border-radius: 15px;
                font-size: 25px;
                color: #1E293B;
                padding: 0 17px;
            }
            QLineEdit::placeholder {
                color: #C0CADB;
            }
        """)
        self.reg_confirm.returnPressed.connect(self._submit)
        cf_layout.addWidget(self.reg_confirm)

        self.confirm_status = QLabel("✓ 匹配")
        self.confirm_status.setStyleSheet("""
            font-size: 20px;
            font-weight: 600;
            color: #34D399;
            padding: 0 10px 0 5px;
        """)
        self.confirm_status.hide()
        cf_layout.addWidget(self.confirm_status)

        self.reg_confirm.textChanged.connect(self._on_confirm_changed)
        layout.addWidget(confirm_frame)
        layout.addSpacing(38)

        self.register_btn = self._make_primary_btn("创建账户 →")
        layout.addWidget(self.register_btn)
        layout.addSpacing(29)

        layout.addLayout(self._make_divider("已有账号？"))
        layout.addSpacing(29)

        self.to_login_btn = self._make_switch_btn("→ 立即登录")
        layout.addWidget(self.to_login_btn)
        layout.addSpacing(34)

        self.reg_status_label = QLabel("")
        self.reg_status_label.setAlignment(Qt.AlignCenter)
        self.reg_status_label.setStyleSheet("""
            font-size: 20px;
            color: #FB7185;
            background-color: #FFF1F2;
            border-radius: 12px;
            padding: 10px;
        """)
        self.reg_status_label.hide()
        layout.addWidget(self.reg_status_label)

        layout.addStretch()
        layout.addSpacing(16)
        layout.addLayout(self._make_status_bar())

        return card

    # ── 事件 ──────────────────────────────────

    def _on_confirm_changed(self, text):
        pwd = self.reg_password.text()
        if not text:
            self.confirm_status.hide()
        elif text == pwd:
            self.confirm_status.setText("✓ 匹配")
            self.confirm_status.setStyleSheet(
                "font-size: 20px; font-weight: 600; color: #34D399; padding: 0 10px 0 5px;")
            self.confirm_status.show()
        else:
            self.confirm_status.setText("✗ 不匹配")
            self.confirm_status.setStyleSheet(
                "font-size: 20px; font-weight: 600; color: #FB7185; padding: 0 10px 0 5px;")
            self.confirm_status.show()

    def _toggle_mode(self):
        if self._mode == self.MODE_LOGIN:
            self._mode = self.MODE_REGISTER
            self.login_card.hide()
            self.register_card.show()
        else:
            self._mode = self.MODE_LOGIN
            self.register_card.hide()
            self.login_card.show()
        self._clear_status()
        self.adjustSize()

    def _clear_status(self):
        self.status_label.hide()
        self.reg_status_label.hide()

    def _submit(self):
        if self._mode == self.MODE_LOGIN:
            self._submit_login()
        else:
            self._submit_register()

    def _submit_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()

        if not username or not password:
            self.status_label.setText("用户名和密码不能为空")
            self.status_label.show()
            return

        self.net.send({
            "type": MT.LOGIN,
            "username": username,
            "password": password
        })
        self.login_btn.setText("登录中...")
        self.login_btn.setEnabled(False)
        self.status_label.setText("")
        self.status_label.hide()

    def _submit_register(self):
        username = self.reg_username.text().strip()
        nickname = self.reg_nickname.text().strip()
        password = self.reg_password.text().strip()
        confirm = self.reg_confirm.text().strip()

        if not username:
            self.reg_status_label.setText("用户名不能为空")
            self.reg_status_label.show()
            return
        if not password:
            self.reg_status_label.setText("密码不能为空")
            self.reg_status_label.show()
            return
        if password != confirm:
            self.reg_status_label.setText("两次输入的密码不一致")
            self.reg_status_label.show()
            return
        if len(password) < 6:
            self.reg_status_label.setText("密码长度不能少于6位")
            self.reg_status_label.show()
            return

        if not nickname:
            nickname = username

        self.net.send({
            "type": MT.REGISTER,
            "username": username,
            "password": password,
            "nickname": nickname
        })
        self.register_btn.setText("注册中...")
        self.register_btn.setEnabled(False)
        self.reg_status_label.setText("")
        self.reg_status_label.hide()

    def _on_login_resp(self, msg):
        self.login_btn.setText("登录 →")
        self.login_btn.setEnabled(True)

        if msg.get("ok"):
            self.state.user_id = msg["user_id"]
            self.state.username = msg.get("nickname", msg.get("username", ""))
            self.state.online_users = msg.get("online_users", [])
            self.state.all_users = msg.get("all_users", [])

            username = self.login_username.text().strip()
            password = self.login_password.text().strip()
            if self.remember_cb.isChecked():
                self._settings.setValue(username, password)
            else:
                self._settings.remove(username)

            self.hide()
            self.app.main.show_main()
        else:
            reason = msg.get("reason", "登录失败")
            self.status_label.setText(reason)
            self.status_label.show()

    def _on_register_resp(self, msg):
        self.register_btn.setText("创建账户 →")
        self.register_btn.setEnabled(True)

        if msg.get("ok"):
            self._toggle_mode()
            self.status_label.setStyleSheet("""
                font-size: 20px;
                color: #10B981;
                background-color: #ECFDF5;
                border-radius: 12px;
                padding: 10px;
            """)
            self.status_label.setText("注册成功，请登录")
            self.status_label.show()
        else:
            reason = msg.get("reason", "注册失败")
            self.reg_status_label.setStyleSheet("""
                font-size: 20px;
                color: #FB7185;
                background-color: #FFF1F2;
                border-radius: 12px;
                padding: 10px;
            """)
            self.reg_status_label.setText(reason)
            self.reg_status_label.show()
