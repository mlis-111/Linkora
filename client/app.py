import customtkinter as ctk
from client.config import HOST, PORT, AES_KEY
from common.crypto import CryptoUtil
from client.state import ClientState
from client.core.network import NetworkClient
from client.core.main_window import MainWindow
from client.ui.login_window import LoginWindow
from client.ui.chat_panel import ChatPanel
from client.ui.friend_panel import FriendPanel
from client.ui.file_panel import FilePanel
from client.ui.ai_panel import AIPanel


class ChatClient:
    """客户端应用装配"""

    def __init__(self):
        """初始化客户端"""
        self.root = ctk.CTk()
        self.root.title("校园即时通信系统")
        self.root.geometry("800x600")

        self.crypto = CryptoUtil(AES_KEY)
        self.state = ClientState()
        self.net = NetworkClient(HOST, PORT, self.root)

        # 创建主窗口（但先不显示）
        self.main = MainWindow(self.root, self)
        self.main.pack_forget()

        # 创建所有面板
        self.panels = {
            "login": LoginWindow(self.root, self),
            "chat": ChatPanel(self.main.content, self),
            "friend": FriendPanel(self.main.content, self),
            "file": FilePanel(self.main.content, self),
            "ai": AIPanel(self.main.content, self),
        }

        # 默认显示登录窗口
        self.panels["login"].pack(fill="both", expand=True)

    def run(self):
        """启动客户端"""
        self.net.connect()
        self.root.mainloop()


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ChatClient().run()
