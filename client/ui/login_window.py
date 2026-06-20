import customtkinter as ctk
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
        self.pack(fill="both", expand=True)

        # 标题
        ctk.CTkLabel(self, text="校园IM登录", font=("Arial", 20, "bold")).pack(pady=30)

        # 用户名输入
        ctk.CTkLabel(self, text="用户名:").pack(pady=5)
        self.username_entry = ctk.CTkEntry(self, width=250, placeholder_text="请输入用户名")
        self.username_entry.pack(pady=5)

        # 密码输入
        ctk.CTkLabel(self, text="密码:").pack(pady=5)
        self.password_entry = ctk.CTkEntry(self, width=250, placeholder_text="请输入密码", show="*")
        self.password_entry.pack(pady=5)

        # 登录按钮
        ctk.CTkButton(self, text="登录", width=250, command=self._login).pack(pady=20)

        # 状态标签
        self.status_label = ctk.CTkLabel(self, text="", text_color="red")
        self.status_label.pack(pady=5)

    def _login(self):
        """处理登录按钮点击"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.status_label.configure(text="用户名和密码不能为空")
            return

        self.net.send({
            "type": MT.LOGIN,
            "username": username,
            "password": password
        })
        self.status_label.configure(text="登录中...")

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
            self.pack_forget()
            self.app.main.show_main()
        else:
            # 登录失败
            reason = msg.get("reason", "登录失败")
            self.status_label.configure(text=reason)
