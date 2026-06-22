from PyQt5.QtWidgets import QMainWindow, QWidget
from common.messages import MT


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        # TODO(郭玄同): 在这里画界面布局
        self.app.net.on(MT.USER_LIST, self._on_user_list)

    def add_panel(self, key, panel):
        """由app.py调用注册面板，接口与原方案一致"""
        self.app.panels[key] = panel
        # TODO: 把panel加入StackedWidget

    def show_main(self):
        """登录成功后由login面板调用，接口与原方案一致"""
        self.show()

    def _on_user_list(self, msg):
        self.app.state.online_users = msg.get("online_users", [])
        # TODO: 刷新在线列表控件
