"""群设置对话框

显示群成员列表、编辑群名称（管理员）、设置个人备注、添加/移除成员、指派管理员。

author: 董钧豪
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget, QDialog,
    QMessageBox, QInputDialog,
)
from PyQt5.QtCore import Qt
from common.messages import MT


# 头像颜色池
_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]


class GroupSettingsDialog(QDialog):
    """群设置对话框

    功能：
        - 查看/修改群名（群主/管理员可修改）
        - 设置个人备注
        - 查看成员列表（角色、在线状态）
        - 添加成员、移除成员、指派管理员
    """

    # 角色常量
    ROLE_MEMBER = 0
    ROLE_ADMIN = 1

    def __init__(self, app, group_id, group_name, parent=None):
        """初始化

        Args:
            app: ChatClient 实例
            group_id: 群聊ID
            group_name: 当前群名
            parent: 父窗口
        """
        super().__init__(parent)
        self._app = app
        self._group_id = group_id
        self._group_name = group_name
        self._owner_id = None
        self._my_role = self.ROLE_MEMBER
        self._members = []  # 成员列表缓存

        self.setWindowTitle("群设置")
        self.setFixedSize(460, 640)
        self.setStyleSheet("""
            QDialog { background-color: #F7F9FD; border-radius: 16px; }
        """)
        self._build_ui()

        # 发送请求获取群设置信息
        self._app.net.send({
            "type": MT.GROUP_INFO,
            "group_id": self._group_id,
        })

    def _build_ui(self):
        """构建对话框界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("群设置")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #1E293B;")
        layout.addWidget(title)

        # 滚动区域
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
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        self._content_layout.setAlignment(Qt.AlignTop)

        # ========== 基本信息 ==========
        self._build_basic_info()
        self._content_layout.addWidget(self._section_separator())

        # ========== 成员列表（占位，等待数据） ==========
        self._member_title = QLabel("成员列表（加载中…）")
        self._member_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        self._content_layout.addWidget(self._member_title)

        self._member_container = QVBoxLayout()
        self._member_container.setSpacing(4)
        self._content_layout.addLayout(self._member_container)

        # ========== 添加成员 ==========
        add_member_btn = QPushButton("＋ 添加成员")
        add_member_btn.setFixedHeight(48)
        add_member_btn.setCursor(Qt.PointingHandCursor)
        add_member_btn.setStyleSheet("""
            QPushButton {
                background: #fff; color: #2D6CF6; border: 2px dashed #CBD5E1;
                border-radius: 14px; font-size: 15px; font-weight: 700;
            }
            QPushButton:hover { background: #F0F5FF; border-color: #2D6CF6; }
        """)
        add_member_btn.clicked.connect(self._on_add_member)
        self._content_layout.addWidget(add_member_btn)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 底部关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(48)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
                font-size: 16px; font-weight: 700;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _build_basic_info(self):
        """构建基本信息区域"""
        # 群名
        name_label = QLabel("群聊名称")
        name_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        self._content_layout.addWidget(name_label)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        self._name_input = QLineEdit(self._group_name)
        self._name_input.setFixedHeight(48)
        self._name_input.setReadOnly(True)  # 默认只读，管理员可编辑
        self._name_input.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: 2px solid #E5EAF3;
                border-radius: 12px; font-size: 16px; color: #1E293B;
                padding: 0 16px;
            }
            QLineEdit:focus { border: 2px solid #4F8DFD; }
            QLineEdit[readOnly="true"] { background: #F1F5FB; color: #94A3B8; }
        """)
        name_row.addWidget(self._name_input, 1)

        self._save_name_btn = QPushButton("保存")
        self._save_name_btn.setFixedSize(70, 48)
        self._save_name_btn.setCursor(Qt.PointingHandCursor)
        self._save_name_btn.setVisible(False)
        self._save_name_btn.setStyleSheet("""
            QPushButton {
                background: #2D6CF6; color: white; border: none;
                border-radius: 12px; font-size: 15px; font-weight: 700;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        self._save_name_btn.clicked.connect(self._on_save_name)
        name_row.addWidget(self._save_name_btn)

        self._content_layout.addLayout(name_row)

        # 个人备注
        remark_label = QLabel("我的群备注（仅自己可见）")
        remark_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        self._content_layout.addWidget(remark_label)

        remark_row = QHBoxLayout()
        remark_row.setSpacing(8)

        self._remark_input = QLineEdit()
        self._remark_input.setPlaceholderText("设置个人备注，方便识别")
        self._remark_input.setFixedHeight(48)
        self._remark_input.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: 2px solid #E5EAF3;
                border-radius: 12px; font-size: 16px; color: #1E293B;
                padding: 0 16px;
            }
            QLineEdit:focus { border: 2px solid #4F8DFD; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        remark_row.addWidget(self._remark_input, 1)

        save_remark_btn = QPushButton("保存")
        save_remark_btn.setFixedSize(70, 48)
        save_remark_btn.setCursor(Qt.PointingHandCursor)
        save_remark_btn.setStyleSheet("""
            QPushButton {
                background: #2D6CF6; color: white; border: none;
                border-radius: 12px; font-size: 15px; font-weight: 700;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        save_remark_btn.clicked.connect(self._on_save_remark)
        remark_row.addWidget(save_remark_btn)

        self._content_layout.addLayout(remark_row)

    def _section_separator(self):
        """创建分组分隔线"""
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #E5EAF3;")
        return sep

    def _render_members(self):
        """渲染成员列表"""
        # 清除旧列表
        while self._member_container.count():
            item = self._member_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._member_title.setText(f"成员列表（{len(self._members)} 人）")

        for i, member in enumerate(self._members):
            self._add_member_row(member, _AVATAR_COLORS[i % len(_AVATAR_COLORS)])

    def _add_member_row(self, member, color):
        """添加成员行"""
        container = QFrame()
        container.setFixedHeight(60)
        container.setStyleSheet("""
            QFrame { background-color: #fff; border-radius: 12px; }
            QFrame:hover { background-color: #F7F9FD; }
        """)

        row = QHBoxLayout(container)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(10)

        # 圆形头像
        name = member.get("nickname") or member.get("username", "?")
        avatar = QLabel(name[0] if name else "?")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            font-size: 18px; font-weight: 600; color: white;
            border-radius: 21px; background-color: {color};
        """)
        row.addWidget(avatar)

        # 名称 + 角色标签 + 在线状态
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_row_widget = QWidget()
        name_row_widget.setStyleSheet("background: transparent;")
        name_row_layout = QHBoxLayout(name_row_widget)
        name_row_layout.setContentsMargins(0, 0, 0, 0)
        name_row_layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1E293B; background: transparent;")
        name_row_layout.addWidget(name_label)

        # 角色标签
        role = member.get("role", 0)
        uid = member.get("user_id")
        if uid == self._owner_id:
            badge = QLabel("👑 群主")
            badge.setStyleSheet("font-size: 12px; color: #F59E0B; background: #FFFBEB; "
                                "padding: 1px 8px; border-radius: 8px;")
            name_row_layout.addWidget(badge)
        elif role == self.ROLE_ADMIN:
            badge = QLabel("⭐ 管理员")
            badge.setStyleSheet("font-size: 12px; color: #6366F1; background: #EEF2FF; "
                                "padding: 1px 8px; border-radius: 8px;")
            name_row_layout.addWidget(badge)

        name_row_layout.addStretch()
        info_col.addWidget(name_row_widget)

        # 在线状态
        online = member.get("online", False)
        status_label = QLabel("🟢 在线" if online else "⚪ 离线")
        status_label.setStyleSheet(
            "font-size: 12px; color: #64748B; background: transparent;")
        info_col.addWidget(status_label)

        row.addLayout(info_col, 1)

        # 操作按钮（仅管理员/群主可见）
        is_owner = (self._app.state.user_id == self._owner_id)
        is_admin = (self._my_role == self.ROLE_ADMIN)

        if (is_owner or is_admin) and uid != self._app.state.user_id:
            # 不能操作群主
            if uid != self._owner_id:
                # 移除按钮（管理员不能移管理员）
                can_remove = is_owner or (not is_owner and member.get("role") != self.ROLE_ADMIN)
                if can_remove:
                    remove_btn = QPushButton("移除")
                    remove_btn.setFixedSize(56, 32)
                    remove_btn.setCursor(Qt.PointingHandCursor)
                    remove_btn.setStyleSheet("""
                        QPushButton {
                            background: #FEF2F2; color: #EF4444; border: none;
                            border-radius: 8px; font-size: 12px; font-weight: 600;
                        }
                        QPushButton:hover { background: #FEE2E2; }
                    """)
                    remove_btn.clicked.connect(lambda checked, tid=uid: self._on_remove_member(tid))
                    row.addWidget(remove_btn)

        # 设置管理员（仅群主可见）
        if is_owner and uid != self._app.state.user_id and uid != self._owner_id:
            if member.get("role") == self.ROLE_ADMIN:
                admin_btn = QPushButton("取消管理")
                admin_btn.setFixedSize(72, 32)
                admin_btn.clicked.connect(lambda checked, tid=uid: self._on_set_admin(tid, 0))
            else:
                admin_btn = QPushButton("设为管理")
                admin_btn.setFixedSize(72, 32)
                admin_btn.clicked.connect(lambda checked, tid=uid: self._on_set_admin(tid, 1))

            admin_btn.setCursor(Qt.PointingHandCursor)
            admin_btn.setStyleSheet("""
                QPushButton {
                    background: #EEF2FF; color: #6366F1; border: none;
                    border-radius: 8px; font-size: 12px; font-weight: 600;
                }
                QPushButton:hover { background: #E0E7FF; }
            """)
            row.addWidget(admin_btn)

        self._member_container.addWidget(container)

    def _on_save_name(self):
        """保存群名"""
        new_name = self._name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "提示", "群名不能为空")
            return
        if new_name == self._group_name:
            self._name_input.setReadOnly(True)
            self._save_name_btn.setVisible(False)
            return

        self._app.net.send({
            "type": MT.GROUP_UPDATE_NAME,
            "group_id": self._group_id,
            "group_name": new_name,
        })
        self._group_name = new_name
        self._name_input.setReadOnly(True)
        self._save_name_btn.setVisible(False)

    def _on_save_remark(self):
        """保存个人备注并刷新群列表"""
        remark = self._remark_input.text().strip()
        self._app.net.send({
            "type": MT.GROUP_SET_REMARK,
            "group_id": self._group_id,
            "remark": remark,
        })
        # 直接刷新群列表，让左侧和头部显示备注
        self._app.net.send({"type": MT.GROUP_LIST})

    def _on_add_member(self):
        """添加成员 — 弹出好友选择对话框"""
        friends = self._app.state.friends or []
        if not friends:
            QMessageBox.information(self, "提示", "没有好友可添加")
            return

        # 过滤已在群中的好友
        member_ids = {m["user_id"] for m in self._members}
        available = [f for f in friends if f["user_id"] not in member_ids]

        if not available:
            QMessageBox.information(self, "提示", "所有好友都已在群中")
            return

        names = [f.get("remark") or f.get("username", f"用户{f['user_id']}")
                 for f in available]
        item, ok = QInputDialog.getItem(
            self, "添加成员", "选择要添加的好友：", names, 0, False
        )
        if ok and item:
            idx = names.index(item)
            target_id = available[idx]["user_id"]
            self._app.net.send({
                "type": MT.GROUP_INVITE,
                "group_id": self._group_id,
                "invitees": [target_id],
            })

    def _on_remove_member(self, target_id):
        """移除成员"""
        reply = QMessageBox.question(
            self, "确认移除", "确定将该成员移出群聊？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._app.net.send({
                "type": MT.GROUP_REMOVE_MEMBER,
                "group_id": self._group_id,
                "target_id": target_id,
            })

    def _on_set_admin(self, target_id, role):
        """设置/取消管理员"""
        action = "设为" if role == 1 else "取消"
        reply = QMessageBox.question(
            self, "确认", f"确定{action}该成员的管理员权限？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._app.net.send({
                "type": MT.GROUP_SET_ADMIN,
                "group_id": self._group_id,
                "target_id": target_id,
                "role": role,
            })

    def _on_info_resp(self, msg):
        """收到群设置信息响应"""
        if msg.get("group_id") != self._group_id:
            return

        self._group_name = msg.get("group_name", self._group_name)
        self._owner_id = msg.get("owner_id")
        self._my_role = msg.get("my_role", self.ROLE_MEMBER)
        self._members = msg.get("members", [])

        # 更新群名输入框
        self._name_input.setText(self._group_name)

        # 更新个人备注输入框
        my_remark = msg.get("my_remark", "")
        self._remark_input.setText(my_remark)

        # 管理员/群主可编辑群名
        can_edit_name = (
            self._my_role == self.ROLE_ADMIN
            or self._app.state.user_id == self._owner_id
        )
        self._name_input.setReadOnly(not can_edit_name)
        self._save_name_btn.setVisible(can_edit_name)
        if can_edit_name:
            self._name_input.setStyleSheet("""
                QLineEdit {
                    background-color: #fff; border: 2px solid #E5EAF3;
                    border-radius: 12px; font-size: 16px; color: #1E293B;
                    padding: 0 16px;
                }
                QLineEdit:focus { border: 2px solid #4F8DFD; }
            """)

        # 渲染成员列表
        self._render_members()

    def _on_name_updated(self, msg):
        """收到群名变更广播"""
        if msg.get("group_id") != self._group_id:
            return
        new_name = msg.get("group_name", "")
        self._group_name = new_name
        self._name_input.setText(new_name)


    def _on_admin_set(self, msg):
        """收到设置管理员响应"""
        if msg.get("ok"):
            role = msg.get("role", 0)
            action = "设为管理员" if role == 1 else "取消管理员"
            QMessageBox.information(self, "成功", f"已{action}")
            # 重新获取群设置信息以刷新界面
            self._app.net.send({
                "type": MT.GROUP_INFO,
                "group_id": self._group_id,
            })

    def showEvent(self, event):
        """显示时订阅消息"""
        super().showEvent(event)
        self._app.net.on(MT.GROUP_INFO_RESP, self._on_info_resp)
        self._app.net.on(MT.GROUP_NAME_UPDATED, self._on_name_updated)
        self._app.net.on(MT.GROUP_SET_ADMIN, self._on_admin_set)

    def hideEvent(self, event):
        """隐藏时取消订阅"""
        super().hideEvent(event)
