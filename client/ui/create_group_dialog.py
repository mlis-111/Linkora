"""创建群聊对话框

提供勾选好友、输入群名的界面，点击确定发起群聊创建请求。

author: 董钧豪
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget, QCheckBox,
    QDialog,
)
from PyQt5.QtCore import Qt
from common.messages import MT


# 头像颜色池
_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]


class CreateGroupDialog(QDialog):
    """创建群聊对话框

    显示好友列表（带复选框），输入群名，确定后发送创建请求。
    """

    def __init__(self, friends, parent=None):
        """初始化对话框

        Args:
            friends: 好友列表 [{"user_id": ..., "username": ..., "remark": ...}, ...]
            parent: 父窗口
        """
        super().__init__(parent)
        self._friends = friends
        self._selected_ids = set()
        self._group_name = ""
        self.setWindowTitle("创建群聊")
        self.setFixedSize(420, 540)
        self.setStyleSheet("""
            QDialog { background-color: #F7F9FD; border-radius: 16px; }
        """)
        self._build_ui()

    def get_result(self):
        """获取创建结果

        Returns:
            dict or None: {"group_name": ..., "invitees": [...]} 或 None（用户取消）
        """
        if self._group_name:
            return {
                "group_name": self._group_name,
                "invitees": list(self._selected_ids),
            }
        return None

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建对话框界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("创建群聊")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #1E293B;")
        layout.addWidget(title)

        # 群名输入
        name_label = QLabel("群聊名称")
        name_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        layout.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("输入群聊名称")
        self._name_input.setFixedHeight(48)
        self._name_input.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: 2px solid #E5EAF3;
                border-radius: 12px; font-size: 16px; color: #1E293B;
                padding: 0 16px;
            }
            QLineEdit:focus { border: 2px solid #4F8DFD; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        layout.addWidget(self._name_input)

        # 好友列表标题
        friend_label = QLabel("选择成员")
        friend_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        layout.addWidget(friend_label)

        # 好友列表（滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._friend_layout = QVBoxLayout(content)
        self._friend_layout.setContentsMargins(0, 0, 0, 0)
        self._friend_layout.setSpacing(4)
        self._friend_layout.setAlignment(Qt.AlignTop)

        for i, f in enumerate(self._friends):
            self._add_friend_checkbox(f, _AVATAR_COLORS[i % len(_AVATAR_COLORS)])

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(48)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #fff; color: #94A3B8; border: 1px solid #E5EAF3;
                border-radius: 14px; font-size: 16px; font-weight: 700;
            }
            QPushButton:hover { background: #F7F9FD; color: #64748B; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        create_btn = QPushButton("创建")
        create_btn.setFixedHeight(48)
        create_btn.setCursor(Qt.PointingHandCursor)
        create_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
                font-size: 16px; font-weight: 700;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(create_btn)

        layout.addLayout(btn_row)

    def _add_friend_checkbox(self, friend, color):
        """添加好友复选框行"""
        container = QFrame()
        container.setFixedHeight(60)
        container.setStyleSheet("""
            QFrame { background-color: #fff; border-radius: 12px; }
            QFrame:hover { background-color: #F7F9FD; }
        """)

        row = QHBoxLayout(container)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)

        cb = QCheckBox()
        cb.setFixedSize(22, 22)
        cb.setStyleSheet("""
            QCheckBox::indicator {
                width: 22px; height: 22px;
                border: 2px solid #CBD5E1; border-radius: 6px;
                background: #fff;
            }
            QCheckBox::indicator:checked {
                background-color: #2D6CF6; border-color: #2D6CF6;
            }
        """)
        uid = friend.get("user_id")
        cb.toggled.connect(lambda checked, fid=uid: self._on_toggle(fid, checked))
        row.addWidget(cb)

        # 圆形头像
        name = friend.get("remark") or friend.get("username", "?")
        avatar = QLabel(name[0] if name else "?")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            font-size: 18px; font-weight: 600; color: white;
            border-radius: 21px; background-color: {color};
        """)
        row.addWidget(avatar)

        # 名称
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1E293B; background: transparent;")
        row.addWidget(name_label, 1)

        self._friend_layout.addWidget(container)

    def _on_toggle(self, user_id, checked):
        """复选框切换"""
        if checked:
            self._selected_ids.add(user_id)
        else:
            self._selected_ids.discard(user_id)

    def _on_create(self):
        """点击创建按钮"""
        group_name = self._name_input.text().strip()
        if not group_name:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请输入群聊名称")
            self._name_input.setFocus()
            return

        self._group_name = group_name
        self.accept()
