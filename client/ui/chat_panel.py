"""聊天面板（客户端）

支持私聊和公共聊天室，提供消息收发、历史记录查询功能。
消息发送前自动加密，接收后自动解密显示。
UI 风格对齐设计稿：蓝色渐变主色、圆形头像、白底圆角气泡。

author: 董钧豪
"""

import time
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt
from client.core.base_panel import BasePanel
from common.messages import MT, PUBLIC_ROOM_ID


# 头像颜色池
_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]


class ChatPanel(BasePanel):
    """聊天面板

    左侧对话列表（公共聊天室 + 在线用户），
    右侧聊天区域（消息显示 + 输入发送）。
    """

    def __init__(self, parent, app):
        self._current_target = None  # {"id": ..., "name": ..., "type": "p2p"/"room"}
        self._conv_items = {}        # key -> QFrame
        self._unread_counts = {}     # key -> 未读消息数
        self._last_msg_times = {}    # key -> 最近消息时间戳（用于排序）
        self._last_msg_previews = {}  # key -> 最近消息预览文字
        self._my_groups = []          # 我加入的群聊列表
        self._available_groups = []   # 可加入的群聊列表
        super().__init__(parent, app)

    def subscribe(self):
        """订阅聊天相关消息"""
        self.net.on(MT.CHAT, self._on_chat)
        self.net.on(MT.ROOM_CHAT, self._on_room_chat)
        self.net.on(MT.HISTORY_RESP, self._on_history)
        self.net.on(MT.USER_LIST, self._on_user_list)
        self.net.on(MT.FRIEND_LIST_RESP, self._on_friend_list)
        self.net.on(MT.GROUP_LIST_RESP, self._on_group_list)
        self.net.on(MT.GROUP_JOIN_RESP, self._on_group_join)
        self._build_ui()
        # 请求好友列表和群聊列表
        self.net.send({"type": MT.FRIEND_LIST})
        self.net.send({"type": MT.GROUP_LIST})

    # ==================== 整体UI构建 ====================

    def _build_ui(self):
        """构建聊天界面：左侧对话列表 + 右侧聊天区域"""
        self.setStyleSheet("background-color: #EEF2FA;")
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧：对话列表
        self._build_conversation_list()
        main_layout.addWidget(self._conv_panel)

        # 分割线
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background-color: #E5EAF3;")
        main_layout.addWidget(divider)

        # 右侧：聊天区域
        self._build_chat_area()
        main_layout.addWidget(self._chat_panel, 1)

        # 默认选中在 _on_group_list 中处理（等待群聊列表返回）

    # ==================== 圆形头像 ====================

    def _create_avatar(self, size, text, color, gradient=False):
        """创建圆形头像

        Args:
            size: 头像尺寸
            text: 显示文字（首字）
            color: 背景色
            gradient: 是否使用蓝渐变

        Returns:
            QLabel: 圆形头像
        """
        avatar = QLabel(text)
        avatar.setFixedSize(size, size)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            font-size: {size // 2 - 2}px;
            font-weight: 600;
            color: white;
            border-radius: {size // 2}px;
            background: {'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4F8DFD, stop:1 #2D6CF6)' if gradient else color};
        """)
        return avatar

    # ==================== 左侧：对话列表 ====================

    def _build_conversation_list(self):
        """构建对话列表"""
        self._conv_panel = QFrame()
        self._conv_panel.setFixedWidth(360)
        self._conv_panel.setStyleSheet("background-color: #F7F9FD;")

        layout = QVBoxLayout(self._conv_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题：消息
        header = QFrame()
        header.setFixedHeight(70)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        title = QLabel("消息")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B;")
        hl.addWidget(title)
        hl.addStretch()

        # 加入群聊按钮
        join_btn = QPushButton("＋")
        join_btn.setFixedSize(40, 40)
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; color: #2D6CF6;
                border: none; border-radius: 13px; font-size: 22px; font-weight: 700;
            }
            QPushButton:hover { background: #D1E3FA; }
        """)
        join_btn.clicked.connect(self._show_join_group_dialog)
        hl.addWidget(join_btn)

        layout.addWidget(header)

        # 搜索框
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索")
        self._search_box.setFixedHeight(50)
        self._search_box.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: none; border-radius: 14px;
                font-size: 15px; color: #1E293B; padding: 0 16px;
                margin: 0 20px 16px 20px;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        layout.addWidget(self._search_box)

        # 对话列表（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        self._conv_content = QWidget()
        self._conv_layout = QVBoxLayout(self._conv_content)
        self._conv_layout.setContentsMargins(12, 0, 12, 0)
        self._conv_layout.setSpacing(4)
        self._conv_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._conv_content)
        layout.addWidget(scroll, 1)

    def _add_conv_item(self, key, avatar_text, avatar_color, name, subtitle, time_text, target, gradient=False, unread_count=0):
        """添加一个对话列表项"""
        is_active = (self._current_target and
                     self._current_target["type"] == target["type"] and
                     self._current_target["id"] == target["id"])

        container = QFrame()
        container.setFixedHeight(90)
        if is_active:
            container.setStyleSheet("QFrame { background-color: #fff; border-radius: 18px; }")
        else:
            container.setStyleSheet("""
                QFrame { background-color: transparent; border-radius: 18px; }
                QFrame:hover { background-color: rgba(255,255,255,0.5); }
            """)

        row = QHBoxLayout(container)
        row.setContentsMargins(14, 13, 14, 13)
        row.setSpacing(14)

        # 圆形头像（带未读角标）
        avatar_container = QWidget()
        avatar_container.setFixedSize(56, 56)
        avatar_container.setStyleSheet("background: transparent;")

        avatar = self._create_avatar(56, avatar_text, avatar_color, gradient)
        avatar.setParent(avatar_container)

        if unread_count > 0:
            badge = QLabel(str(min(unread_count, 99)), avatar_container)
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("""
                background-color: #EF4444; color: white; border-radius: 11px;
                font-size: 11px; font-weight: 700; border: 2px solid #F7F9FD;
            """)
            badge.move(36, -2)

        row.addWidget(avatar_container)

        # 文字区域
        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        name_row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet(
            f"font-size: 18px; font-weight: {'700' if is_active else '600'}; color: #1E293B; background: transparent;")
        name_row.addWidget(name_label)
        name_row.addStretch()

        if time_text:
            time_label = QLabel(time_text)
            time_label.setStyleSheet(
                f"font-size: 14px; color: {'#2D6CF6' if is_active else '#A9B6C8'}; background: transparent;")
            name_row.addWidget(time_label)

        text_col.addLayout(name_row)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("font-size: 15px; color: #6B7A90; background: transparent;")
        text_col.addWidget(sub_label)

        row.addLayout(text_col, 1)

        # 点击切换聊天
        container.mousePressEvent = lambda e, t=target: self._on_contact_selected(t)

        self._conv_items[key] = container
        self._conv_layout.addWidget(container)

    def _refresh_conv_list(self):
        """刷新对话列表，排序：当前查看的对话 > 有未读的其他对话 > 好友"""
        # 清空整个布局
        while self._conv_layout.count():
            item = self._conv_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._conv_items.clear()

        online_ids = {u.get("user_id") for u in self.state.online_users}
        active_key = None
        if self._current_target:
            active_key = f"{self._current_target['type']}_{self._current_target['id']}"

        shown_keys = set()

        # ========== 1. 当前正在查看的对话（最顶部） ==========
        if active_key:
            shown_keys.add(active_key)
            self._add_conv_item_for_key(active_key, online_ids, is_active=True)

        # ========== 2. 有未读消息的其他对话 ==========
        unread_keys = sorted(
            [k for k in self._unread_counts if k != active_key],
            key=lambda k: self._last_msg_times.get(k, 0),
            reverse=True
        )
        for key in unread_keys:
            if key not in shown_keys:
                shown_keys.add(key)
                self._add_conv_item_for_key(key, online_ids, is_active=False)

        # ========== 3. 已加入的群聊（未显示出来的） ==========
        for g in self._my_groups:
            key = f"room_{g['group_id']}"
            if key not in shown_keys:
                shown_keys.add(key)
                preview = self._last_msg_previews.get(key, "")
                subtitle = preview if preview else "点击进入群聊"
                self._add_conv_item(
                    key, "👥", "", g["group_name"],
                    subtitle, "",
                    {"id": g["group_id"], "name": g["group_name"], "type": "room"},
                    gradient=True,
                )

        # ========== 4. 好友列表 ==========
        remaining = []
        for f in (self.state.friends or []):
            uid = f["user_id"]
            if uid == self.state.user_id:
                continue
            uname = f.get("remark") or f.get("username", "未知")
            key = f"p2p_{uid}"
            if key in shown_keys:
                continue
            last_time = self._last_msg_times.get(key, 0)
            is_online = f.get("online", False)
            remaining.append((uid, uname, key, last_time, is_online))

        remaining.sort(key=lambda x: x[3] if x[3] else 0, reverse=True)
        for uid, uname, key, _, is_online in remaining:
            shown_keys.add(key)
            preview = self._last_msg_previews.get(key, "")
            subtitle = preview if preview else ("🟢 在线" if is_online else "⚪ 离线")
            self._add_conv_item(
                key, uname[0] if uname else "?",
                _AVATAR_COLORS[uid % len(_AVATAR_COLORS)],
                uname, subtitle, "",
                {"id": uid, "name": uname, "type": "p2p"},
            )

        self._conv_layout.addStretch()

    def _add_conv_item_for_key(self, key, online_ids, is_active=False):
        """根据 key 添加对话列表项

        Args:
            key: 对话 key（格式 room_xxx 或 p2p_xxx）
            online_ids: 在线用户ID集合
            is_active: 是否为当前查看的对话
        """
        if key.startswith("room_"):
            group_id = key[5:]
            group_name = group_id
            for g in self._my_groups:
                if g["group_id"] == group_id:
                    group_name = g["group_name"]
                    break
            preview = self._last_msg_previews.get(key, "")
            count = self._unread_counts.get(key, 0)
            subtitle = preview if preview else "点击进入群聊"
            self._add_conv_item(
                key, "👥", "", group_name,
                subtitle, "",
                {"id": group_id, "name": group_name, "type": "room"},
                gradient=True,
                unread_count=count,
            )
        elif key.startswith("p2p_"):
            uid = int(key[4:])
            uname = self._find_user_name(uid)
            is_online = uid in online_ids
            preview = self._last_msg_previews.get(key, "")
            count = self._unread_counts.get(key, 0)
            subtitle = preview if preview else ("🟢 在线" if is_online else "⚪ 离线")
            self._add_conv_item(
                key, uname[0] if uname else "?",
                _AVATAR_COLORS[uid % len(_AVATAR_COLORS)],
                uname, subtitle, "",
                {"id": uid, "name": uname, "type": "p2p"},
                unread_count=count,
            )

    def _on_friend_list(self, msg):
        """收到好友列表时刷新对话列表（用于过滤非好友）"""
        self.state.friends = msg.get("friends", [])

    # ==================== 群聊管理 ====================

    def _on_group_list(self, msg):
        """收到群聊列表"""
        self._my_groups = msg.get("my_groups", [])
        self._available_groups = msg.get("available", [])
        # 首次加载时默认选中公共聊天室
        if self._current_target is None:
            self._select_room()
        else:
            self._refresh_conv_list()

    def _on_group_join(self, msg):
        """收到加入群聊结果"""
        if msg.get("ok"):
            self.net.send({"type": MT.GROUP_LIST})  # 刷新群聊列表
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "失败", msg.get("message", "加入群聊失败"))

    def _show_join_group_dialog(self):
        """显示加入群聊对话框"""
        if not self._available_groups:
            # 重新请求群聊列表
            self.net.send({"type": MT.GROUP_LIST})
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "没有可加入的群聊")
            return

        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QListWidgetItem

        dialog = QDialog(self)
        dialog.setWindowTitle("加入群聊")
        dialog.setFixedSize(360, 420)
        dialog.setStyleSheet("""
            QDialog { background-color: #F7F9FD; border-radius: 16px; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background: #fff; border: none; border-radius: 12px;
                font-size: 16px; padding: 8px;
            }
            QListWidget::item {
                padding: 12px 16px; border-radius: 8px;
            }
            QListWidget::item:hover { background: #F7F9FD; }
            QListWidget::item:selected { background: #E7EFFC; color: #1E293B; }
        """)

        for g in self._available_groups:
            item = QListWidgetItem(f"👥  {g['group_name']}  ({g['group_id']})")
            item.setData(1, g["group_id"])
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        join_btn = QPushButton("加入")
        join_btn.setFixedHeight(48)
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
                font-size: 16px; font-weight: 700;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        join_btn.clicked.connect(lambda: self._do_join_group(dialog, list_widget))
        layout.addWidget(join_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(48)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #fff; color: #94A3B8; border: 1px solid #E5EAF3;
                border-radius: 14px; font-size: 16px;
            }
            QPushButton:hover { background: #F7F9FD; color: #64748B; }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)

        dialog.exec_()

    def _do_join_group(self, dialog, list_widget):
        """执行加入群聊"""
        selected = list_widget.currentItem()
        if not selected:
            return
        group_id = selected.data(1)
        self.net.send({"type": MT.GROUP_JOIN, "group_id": group_id})
        dialog.accept()

    # ==================== 右侧：聊天区域 ====================

    def _build_chat_area(self):
        """构建右侧聊天区域"""
        self._chat_panel = QFrame()
        self._chat_panel.setStyleSheet("background-color: #F7F9FD;")

        layout = QVBoxLayout(self._chat_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 聊天头部
        self._header = QFrame()
        self._header.setFixedHeight(70)
        self._header.setStyleSheet("background-color: #fff; border-bottom: 1px solid #EEF1F7;")

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(28, 0, 28, 0)

        self._chat_title = QLabel("公共聊天室")
        self._chat_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #1E293B;")
        hl.addWidget(self._chat_title)

        self._chat_badge = QLabel("")
        self._chat_badge.setStyleSheet(
            "font-size: 13px; color: #94A3B8; background: #F1F5FB; padding: 3px 10px; border-radius: 9px;")
        hl.addWidget(self._chat_badge)
        hl.addStretch()

        self._online_label = QLabel("")
        self._online_label.setStyleSheet("font-size: 15px; color: #64748B;")
        hl.addWidget(self._online_label)

        self._my_avatar = self._create_avatar(44, "我", "", gradient=True)
        hl.addWidget(self._my_avatar)

        layout.addWidget(self._header)

        # 消息滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #F7F9FD; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(content)
        self._msg_layout.setContentsMargins(46, 20, 26, 20)
        self._msg_layout.setSpacing(16)
        self._msg_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(content)
        self._scroll = scroll
        layout.addWidget(scroll, 1)

        # 新消息提示按钮（不在底部时有新消息才显示）
        self._new_msg_hint = QPushButton("↓ 新消息")
        self._new_msg_hint.setFixedHeight(38)
        self._new_msg_hint.setCursor(Qt.PointingHandCursor)
        self._new_msg_hint.hide()
        self._new_msg_hint.setStyleSheet("""
            QPushButton {
                background: #2D6CF6; color: white; border: none;
                border-radius: 19px; font-size: 14px; font-weight: 700;
                padding: 0 22px; margin-right: 24px; margin-bottom: 4px;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        self._new_msg_hint.clicked.connect(self._scroll_to_bottom)
        layout.addWidget(self._new_msg_hint, alignment=Qt.AlignRight)

        # 监听滚动位置
        scroll.verticalScrollBar().valueChanged.connect(self._on_chat_scrolled)

        # 消息输入区
        composer = QFrame()
        composer.setFixedHeight(90)
        composer.setStyleSheet("background-color: #fff; border-top: 1px solid #EEF1F7;")

        cl = QHBoxLayout(composer)
        cl.setContentsMargins(28, 18, 28, 18)
        cl.setSpacing(14)

        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("输入消息，Enter 发送…")
        self._text_input.setFixedHeight(52)
        self._text_input.setStyleSheet("""
            QLineEdit {
                background-color: #F7F9FD; border: 2px solid #E7EFFC;
                border-radius: 14px; font-size: 16px; color: #1E293B; padding: 0 16px;
            }
            QLineEdit:focus { border: 2px solid #4F8DFD; background-color: #fff; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        self._text_input.returnPressed.connect(self._send_message)
        cl.addWidget(self._text_input)

        send_btn = QPushButton("发送")
        send_btn.setFixedHeight(52)
        send_btn.setMinimumWidth(100)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
                font-size: 14px; font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        send_btn.clicked.connect(self._send_message)
        cl.addWidget(send_btn)

        layout.addWidget(composer)

    # ==================== 联系人切换 ====================

    def _on_contact_selected(self, target):
        """点击联系人切换聊天"""
        self._current_target = target

        if target["type"] == "room":
            self._chat_title.setText(target["name"])
            self._chat_badge.setText("群聊")
        else:
            self._chat_title.setText(target["name"])
            self._chat_badge.setText("")

        online_count = len(self.state.online_users)
        self._online_label.setText(f"● {online_count} 人在线")

        # 清空该对话的未读计数
        key = f"{target['type']}_{target['id']}"
        self._unread_counts.pop(key, None)

        self._clear_messages()
        # 网络连接后才加载历史（初始化时网络尚未就绪）
        if self.state.user_id is not None:
            self._load_history()
        self._refresh_conv_list()

    def _select_room(self):
        """默认选中第一个群聊（公共聊天室优先）"""
        for g in self._my_groups:
            if g["group_id"] == PUBLIC_ROOM_ID:
                self._on_contact_selected({"id": g["group_id"], "name": g["group_name"], "type": "room"})
                return
        if self._my_groups:
            g = self._my_groups[0]
            self._on_contact_selected({"id": g["group_id"], "name": g["group_name"], "type": "room"})
            return

    # ==================== 消息收发 ====================

    def _send_message(self):
        """发送消息"""
        if not self._current_target:
            return

        text = self._text_input.text().strip()
        if not text:
            return

        encrypted = self.app.crypto.encrypt(text)
        ts = int(time.time())
        target = self._current_target
        key = f"{target['type']}_{target['id']}"

        if target["type"] == "room":
            self.net.send({"type": MT.ROOM_CHAT, "room_id": target["id"], "content": encrypted, "ts": ts})
        else:
            self.net.send({"type": MT.CHAT, "to": target["id"], "content": encrypted, "ts": ts})

        # 更新左侧列表的预览和时间
        preview_text = (text[:28] + "…") if len(text) > 28 else text
        if target["type"] == "room":
            self._last_msg_previews[key] = f"我: {preview_text}"
        else:
            self._last_msg_previews[key] = preview_text
        self._last_msg_times[key] = ts
        self._refresh_conv_list()

        self._append_msg_bubble("我", text, "", is_self=True)
        self._text_input.clear()

    def _on_chat(self, msg):
        """收到私聊消息"""
        sender_id = msg.get("from")
        if sender_id == self.state.user_id:
            return
        plain = self.app.crypto.decrypt(msg.get("content", ""))
        ts = msg.get("ts", "")
        sender_name = self._find_user_name(sender_id)

        # 判断是否正在查看该对话
        viewing = (self._current_target and
                   self._current_target["type"] == "p2p" and
                   self._current_target["id"] == sender_id)

        # 更新预览和时间（无论是否正在查看）
        key = f"p2p_{sender_id}"
        preview = (plain[:28] + "…") if len(plain) > 28 else plain
        self._last_msg_previews[key] = preview
        self._last_msg_times[key] = ts or int(time.time())

        if viewing:
            self._append_msg_bubble(sender_name, plain, str(ts))
            # 在底部则自动滚到底，否则显示「新消息」提示
            if self._is_at_bottom():
                self._scroll_to_bottom()
            else:
                self._new_msg_hint.show()
        else:
            self._unread_counts[key] = self._unread_counts.get(key, 0) + 1
            self._refresh_conv_list()

    def _on_room_chat(self, msg):
        """收到群聊消息，按 room_id 路由"""
        sender_id = msg.get("from")
        if sender_id == self.state.user_id:
            return
        room_id = msg.get("room_id", "")
        if not room_id:
            return

        plain = self.app.crypto.decrypt(msg.get("content", ""))
        ts = msg.get("ts", "")
        sender_name = self._find_user_name(sender_id)
        key = f"room_{room_id}"

        # 更新对应群聊的预览和时间
        preview = (plain[:28] + "…") if len(plain) > 28 else plain
        self._last_msg_previews[key] = f"{sender_name}: {preview}"
        self._last_msg_times[key] = ts or int(time.time())

        viewing_this_room = (
            self._current_target
            and self._current_target["type"] == "room"
            and self._current_target["id"] == room_id
        )
        if viewing_this_room:
            self._append_msg_bubble(sender_name, plain, str(ts))
            if self._is_at_bottom():
                self._scroll_to_bottom()
            else:
                self._new_msg_hint.show()
        else:
            self._unread_counts[key] = self._unread_counts.get(key, 0) + 1
            self._refresh_conv_list()

    def _on_user_list(self, msg):
        """在线列表更新"""
        self.state.online_users = msg.get("online_users", [])
        self._refresh_conv_list()
        online_count = len(self.state.online_users)
        self._online_label.setText(f"● {online_count} 人在线")

    # ==================== 历史记录 ====================

    def _load_history(self):
        """加载历史记录"""
        if not self._current_target:
            return
        t = self._current_target
        if t["type"] == "room":
            self.net.send({"type": MT.HISTORY_REQ, "scope": "room", "room_id": t["id"]})
        else:
            self.net.send({"type": MT.HISTORY_REQ, "scope": "p2p", "target": t["id"]})

    def _on_history(self, msg):
        """收到历史记录响应"""
        records = msg.get("records", [])
        self._clear_messages()
        if not records:
            self._append_system_msg("暂无聊天记录")
            return

        for r in records:
            plain = self.app.crypto.decrypt(r.get("content", ""))
            sender_id = r.get("from")
            ts = r.get("ts", "")
            is_self = (sender_id == self.state.user_id)
            sender_name = "我" if is_self else self._find_user_name(sender_id)
            self._append_msg_bubble(sender_name, plain, ts, is_self)

        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    # ==================== 消息气泡 ====================

    def _clear_messages(self):
        """清空消息区域"""
        while self._msg_layout.count():
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _append_msg_bubble(self, sender_name, content, ts="", is_self=False):
        """添加消息气泡"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        if is_self:
            layout.setDirection(QHBoxLayout.RightToLeft)

        # 圆形头像
        avatar_text = sender_name[0] if sender_name else "?"
        avatar = self._create_avatar(44, avatar_text, "#6366F1")
        layout.addWidget(avatar)

        # 气泡
        bubble_col = QVBoxLayout()
        bubble_col.setSpacing(4)

        info_label = QLabel(f"{sender_name}  {ts}" if ts else sender_name)
        info_label.setStyleSheet("font-size: 14px; color: #94A3B8; background: transparent;")
        bubble_col.addWidget(info_label)

        bubble = QLabel(content)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(560)
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        bubble.setContentsMargins(18, 12, 18, 12)

        if is_self:
            bubble.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #4F8DFD, stop:1 #2D6CF6);
                    color: white; border-radius: 18px; font-size: 16px;
                }
            """)
        else:
            bubble.setStyleSheet("""
                QLabel {
                    background-color: #fff; color: #1E293B;
                    border: 1px solid #E7EFFC; border-radius: 18px; font-size: 16px;
                }
            """)

        bubble_col.addWidget(bubble, alignment=Qt.AlignLeft if not is_self else Qt.AlignRight)
        layout.addLayout(bubble_col)
        layout.addStretch()

        self._msg_layout.addWidget(container)

    def _append_system_msg(self, text):
        """添加系统提示"""
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 12px; color: #94A3B8; padding: 20px 0; background: transparent;")
        self._msg_layout.addWidget(label)

    def _find_user_name(self, user_id):
        """根据用户ID查找名称"""
        if user_id == self.state.user_id:
            return self.state.username or "我"
        for u in self.state.online_users:
            if u.get("user_id") == user_id:
                return u.get("nickname") or u.get("username", f"用户{user_id}")
        return f"用户{user_id}"

    # ==================== 滚动控制 ====================

    def _is_at_bottom(self):
        """判断是否在聊天区域最底部（有 30px 容差）"""
        sb = self._scroll.verticalScrollBar()
        return sb.maximum() - sb.value() < 30

    def _scroll_to_bottom(self):
        """滚到聊天区域最底部，隐藏新消息提示"""
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
        self._new_msg_hint.hide()

    def _on_chat_scrolled(self, value):
        """滚动位置变化时，如果滚回底部则隐藏新消息提示"""
        if self._is_at_bottom():
            self._new_msg_hint.hide()
