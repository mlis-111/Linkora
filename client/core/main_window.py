import customtkinter as ctk
from common.messages import MT


class MainWindow(ctk.CTkFrame):
    """主窗口（侧栏 + 面板容器 + 在线列表）"""

    def __init__(self, master, app):
        """初始化主窗口

        Args:
            master: 父容器
            app: ChatClient实例
        """
        super().__init__(master)
        self.app = app
        self.pack(fill="both", expand=True)

        # 订阅在线列表更新
        self.app.net.on(MT.USER_LIST, self._on_user_list)

        # 左侧边栏
        self.sidebar = ctk.CTkFrame(self, width=200)
        self.sidebar.pack(side="left", fill="y", padx=5, pady=5)

        # 在线用户标题
        ctk.CTkLabel(self.sidebar, text="在线用户", font=("Arial", 14, "bold")).pack(pady=10)

        # 在线用户列表
        self.user_listbox = ctk.CTkTextbox(self.sidebar, width=180, height=300)
        self.user_listbox.pack(pady=5, padx=5)
        self.user_listbox.configure(state="disabled")

        # 功能按钮区域
        btn_frame = ctk.CTkFrame(self.sidebar)
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="聊天", width=80, command=lambda: self.show_panel("chat")).pack(pady=2)
        ctk.CTkButton(btn_frame, text="好友", width=80, command=lambda: self.show_panel("friend")).pack(pady=2)
        ctk.CTkButton(btn_frame, text="文件", width=80, command=lambda: self.show_panel("file")).pack(pady=2)
        ctk.CTkButton(btn_frame, text="AI", width=80, command=lambda: self.show_panel("ai")).pack(pady=2)

        # 右侧内容区域
        self.content = ctk.CTkFrame(self)
        self.content.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # 当前显示的面板
        self.current_panel = None

    def show_main(self):
        """登录成功后显示主界面"""
        self.pack(fill="both", expand=True)

    def show_panel(self, panel_name):
        """切换到指定面板

        Args:
            panel_name: 面板名称
        """
        if self.current_panel:
            self.current_panel.pack_forget()

        panel = self.app.panels.get(panel_name)
        if panel:
            panel.pack(in_=self.content, fill="both", expand=True)
            self.current_panel = panel

    def _on_user_list(self, msg):
        """处理在线列表更新

        Args:
            msg: 消息字典
        """
        online_users = msg.get("online_users", [])
        self.app.state.online_users = online_users

        # 更新显示
        self.user_listbox.configure(state="normal")
        self.user_listbox.delete("1.0", "end")
        for user in online_users:
            nickname = user.get("nickname", user.get("username", ""))
            self.user_listbox.insert("end", f"• {nickname}\n")
        self.user_listbox.configure(state="disabled")
