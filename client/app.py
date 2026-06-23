import sys
from PyQt5.QtWidgets import QApplication
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
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.crypto = CryptoUtil(AES_KEY)
        self.state  = ClientState()
        self.net    = NetworkClient(HOST, PORT)
        self.panels = {}

        self.main      = MainWindow(self)
        self.login_win = LoginWindow(None, self)

        for key, cls in [
            ("chat",   ChatPanel),
            ("friend", FriendPanel),
            ("file",   FilePanel),
            ("ai",     AIPanel),
        ]:
            self.main.add_panel(key, cls(self.main, self))

    def show_login(self):
        """回到登录界面（断线时调用）"""
        self.main.hide()
        self.login_win.show()

    def run(self):
        self.net.connect()
        self.login_win.show()
        sys.exit(self.qt_app.exec_())


if __name__ == "__main__":
    ChatClient().run()
