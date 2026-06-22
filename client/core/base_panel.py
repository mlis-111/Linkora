from PyQt5.QtWidgets import QWidget


class BasePanel(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app   = app
        self.net   = app.net
        self.state = app.state
        self.subscribe()

    def subscribe(self):
        pass
