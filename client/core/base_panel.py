import customtkinter as ctk


class BasePanel(ctk.CTkFrame):
    """面板基类"""

    def __init__(self, master, app):
        """初始化面板

        Args:
            master: 父容器
            app: ChatClient实例
        """
        super().__init__(master)
        self.app = app
        self.net = app.net
        self.state = app.state
        self.subscribe()

    def subscribe(self):
        """子类重写此方法，订阅关心的消息类型"""
        pass
