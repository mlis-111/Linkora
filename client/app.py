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

        # 全局样式
        self.qt_app.setStyleSheet("""
            QWidget#LeftSidebar  { background-color: #FFFFFF; }
            QWidget#RightPanel   { background-color: #F4F6FA; }

            QFrame#AIBubble {
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 12px;
                border-top-left-radius: 4px;
                padding: 12px 16px;
                font-size: 15px;
            }
            QLabel#AIBubbleText { font-size: 15px; color: #222222; }

            QFrame#UserBubble {
                background-color: #5971F2;
                color: #FFFFFF;
                border-radius: 12px;
                border-top-right-radius: 4px;
                padding: 12px 16px;
            }
            QLabel#UserBubbleText { font-size: 15px; color: #FFFFFF; }

            QPushButton#RecommendBtn {
                background-color: #FFFFFF;
                border: 1px solid #E5E5E5;
                border-radius: 16px;
                padding: 6px 12px;
                font-size: 13px;
            }

            QLineEdit#InputField {
                font-size: 15px;
                padding-left: 16px;
                padding-right: 16px;
                border-radius: 24px;
            }

            QWidget#HistoryItem {
                margin: 4px 12px;
                padding: 10px 14px;
                border-radius: 8px;
            }
            QWidget#HistoryItem[selected=\"true\"] { background-color: #E6E6FA; }
        """)

    def run(self):
        self.net.connect()
        self.login_win.show()
        sys.exit(self.qt_app.exec_())


if __name__ == "__main__":
    ChatClient().run()
