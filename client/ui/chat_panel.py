"""聊天面板（客户端）

支持私聊和群聊，提供消息收发、历史记录查询功能。
消息发送前自动加密，接收后自动解密显示。
UI 对齐设计稿：蓝渐变主色、圆形头像、白底圆角气泡、卡片式输入区。

author: 董钧豪
"""

import time
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget, QSizePolicy,
    QMenu, QAction, QMessageBox, QDialog,
)
from PyQt5.QtCore import Qt
from client.core.base_panel import BasePanel
from common.messages import MT, PUBLIC_ROOM_ID
from client.ui.group_settings_dialog import GroupSettingsDialog


# 头像颜色池
_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]


class ChatPanel(BasePanel):
    """聊天面板

    左侧对话列表（公共聊天室 + 群聊 + 好友），
    右侧聊天区域（消息显示 + 卡片式输入区），
    私聊时右侧多一个信息面板。
    """

    def __init__(self, parent, app):
        self._current_target = None  # {"id": ..., "name": ..., "type": "p2p"/"room"}
        self._conv_items = {}        # key -> QFrame
        self._unread_counts = {}     # key -> 未读消息数
        self._last_msg_times = {}    # key -> 最近消息时间戳（用于排序）
        self._last_msg_previews = {}  # key -> 最近消息预览文字
        self._my_groups = []          # 我加入的群聊列表
        self._available_groups = []   # 可加入的群聊列表
        self._pending_join_dialog = False  # 用户点了"＋"但数据还没加载完
        self._search_text = ""        # 搜索框文字，用于过滤对话列表
        self._pending_members_group = None  # 等待成员列表响应的群ID
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
        self.net.on(MT.GROUP_NAME_UPDATED, self._on_group_name_updated)
        self.net.on(MT.GROUP_MEMBERS_RESP, self._on_group_members_resp)
        self.net.on(MT.GROUP_INVITE, self._on_invited_to_group)
        self.net.on(MT.FRIEND_REMOVE_RESP, self._on_friend_remove_resp)
        self._build_ui()

    def showEvent(self, event):
        """面板显示时请求初始数据"""
        super().showEvent(event)
        if self.state.user_id is not None and not self._my_groups:
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

        # 中间：聊天区域
        self._build_chat_area()
        main_layout.addWidget(self._chat_panel, 1)

        # 右侧：信息面板（私聊时显示）
        self._build_info_panel()
        self._info_panel.hide()  # 默认隐藏
        main_layout.addWidget(self._info_panel)

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
        """构建对话列表（宽度 450px，对齐设计稿）"""
        self._conv_panel = QFrame()
        self._conv_panel.setFixedWidth(450)
        self._conv_panel.setStyleSheet("background-color: #F7F9FD;")

        layout = QVBoxLayout(self._conv_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题：消息
        header = QFrame()
        header.setFixedHeight(68)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        title = QLabel("消息")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B;")
        hl.addWidget(title)

        self._total_unread_badge = QLabel("")
        self._total_unread_badge.setStyleSheet("""
            font-size: 24px; font-weight: 700; color: #EF4444;
            background: #FEE2E2; padding: 2px 10px; border-radius: 10px;
        """)
        self._total_unread_badge.hide()
        hl.addWidget(self._total_unread_badge)

        hl.addStretch()

        # 加入群聊按钮（＋图标）
        join_btn = QPushButton("＋")
        join_btn.setFixedSize(36, 36)
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; color: #2D6CF6;
                border: none; border-radius: 12px; font-size: 26px; font-weight: 700;
            }
            QPushButton:hover { background: #D1E3FA; }
        """)
        join_btn.clicked.connect(self._show_join_group_dialog)
        hl.addWidget(join_btn)

        layout.addWidget(header)

        # 搜索框
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索用户或消息")
        self._search_box.setFixedHeight(44)
        self._search_box.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: none; border-radius: 14px;
                font-size: 24px; color: #1E293B; padding: 0 15px;
                margin: 0 20px 14px 20px;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        self._search_box.textChanged.connect(self._on_search_text_changed)
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
        self._conv_layout.setSpacing(2)
        self._conv_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._conv_content)
        layout.addWidget(scroll, 1)

    def _add_conv_item(self, key, avatar_text, avatar_color, name, subtitle, time_text, target, gradient=False, unread_count=0, is_online=None):
        """添加一个对话列表项

        Args:
            key: 唯一标识
            avatar_text: 头像文字
            avatar_color: 头像背景色
            name: 显示名称
            subtitle: 预览文字
            time_text: 时间文字
            target: 目标 {"id":..., "name":..., "type":...}
            gradient: 是否蓝渐变头像
            unread_count: 未读数
            is_online: 好友在线状态（None 不显示，True 绿点，False 灰点）
        """
        is_active = (self._current_target and
                     self._current_target["type"] == target["type"] and
                     self._current_target["id"] == target["id"])

        container = QFrame()
        container.setFixedHeight(76)
        if is_active:
            container.setStyleSheet("""
                QFrame {
                    background-color: #fff; border-radius: 18px;
                }
            """)
        else:
            container.setStyleSheet("""
                QFrame { background-color: transparent; border-radius: 18px; }
                QFrame:hover { background-color: rgba(255,255,255,0.5); }
            """)

        row = QHBoxLayout(container)
        row.setContentsMargins(13, 13, 13, 13)
        row.setSpacing(13)

        # 圆形头像（带在线状态点）
        avatar_container = QWidget()
        avatar_container.setFixedSize(52, 52)
        avatar_container.setStyleSheet("background: transparent;")

        avatar = self._create_avatar(52, avatar_text, avatar_color, gradient)
        avatar.setParent(avatar_container)

        if unread_count > 0:
            badge = QLabel(str(min(unread_count, 99)), avatar_container)
            badge.setFixedSize(20, 20)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("""
                background-color: #EF4444; color: white; border-radius: 10px;
                font-size: 24px; font-weight: 700; border: 2px solid #F7F9FD;
            """)
            badge.move(34, -2)

        # 在线状态圆点（好友）
        if is_online is not None:
            dot = QLabel(avatar_container)
            dot.setFixedSize(13, 13)
            dot.setStyleSheet(
                f"background-color: {'#34D399' if is_online else '#CBD5E1'}; "
                f"border-radius: 6px; border: 2.5px solid {'#fff' if is_active else '#F7F9FD'};"
            )
            dot.move(39, 39)

        row.addWidget(avatar_container)

        # 文字区域
        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        name_row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet(
            f"font-size: 24px; font-weight: {'700' if is_active else '600'}; color: {'#2D6CF6' if is_active else '#1E293B'}; background: transparent;")
        name_row.addWidget(name_label)
        name_row.addStretch()

        if time_text:
            time_label = QLabel(time_text)
            time_label.setStyleSheet(
                f"font-size: 24px; color: {'#2D6CF6' if is_active else '#A9B6C8'}; background: transparent; font-weight: {'600' if is_active else '400'};")
            name_row.addWidget(time_label)

        text_col.addLayout(name_row)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet("font-size: 24px; color: #6B7A90; background: transparent;")
        text_col.addWidget(sub_label)

        row.addLayout(text_col, 1)

        # 让所有子控件不拦截鼠标事件，确保点击能到达容器
        for child in container.findChildren(QWidget):
            child.setAttribute(Qt.WA_TransparentForMouseEvents, True)

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

        # 更新左侧「消息」标题旁的总未读角标
        total_unread = sum(self._unread_counts.values())
        if total_unread > 0:
            self._total_unread_badge.setText(f"{total_unread} 条未读")
            self._total_unread_badge.show()
        else:
            self._total_unread_badge.hide()

        online_ids = {u.get("user_id") for u in self.state.online_users}
        active_key = None
        if self._current_target:
            active_key = f"{self._current_target['type']}_{self._current_target['id']}"

        shown_keys = set()

        # ========== 1. 有未读消息的对话（按时间排序） ==========
        unread_keys = sorted(
            [k for k in self._unread_counts],
            key=lambda k: self._last_msg_times.get(k, 0),
            reverse=True
        )
        for key in unread_keys:
            if key not in shown_keys:
                shown_keys.add(key)
                # 检查是否匹配搜索
                if self._search_text:
                    name = self._get_conv_name(key)
                    preview = self._last_msg_previews.get(key, "")
                    if not self.matches_search(name, preview):
                        continue
                self._add_conv_item_for_key(key, online_ids, is_active=False)

        # ========== 3. 已加入的群聊（搜索过滤） ==========
        for g in self._my_groups:
            key = f"room_{g['group_id']}"
            if key not in shown_keys:
                display_name = g.get("remark") or g["group_name"]
                preview = self._last_msg_previews.get(key, "")
                subtitle = preview if preview else "点击进入群聊"
                # 搜索过滤
                if self._search_text and not self.matches_search(display_name, subtitle):
                    continue
                shown_keys.add(key)
                self._add_conv_item(
                    key, "👥", "", display_name,
                    subtitle, "",
                    {"id": g["group_id"], "name": display_name, "type": "room"},
                    gradient=True,
                )

        # ========== 4. 好友列表（搜索过滤） ==========
        remaining = []
        for f in (self.state.friends or []):
            uid = f["user_id"]
            if uid == self.state.user_id:
                continue
            uname = f.get("remark") or f.get("username", "未知")
            key = f"p2p_{uid}"
            if key in shown_keys:
                continue
            # 搜索过滤
            if self._search_text and not self.matches_search(uname, ""):
                continue
            last_time = self._last_msg_times.get(key, 0)
            is_online = f.get("online", False) or uid in online_ids
            remaining.append((uid, uname, key, last_time, is_online))

        remaining.sort(key=lambda x: x[3] if x[3] else 0, reverse=True)
        for uid, uname, key, _, is_online in remaining:
            shown_keys.add(key)
            preview = self._last_msg_previews.get(key, "")
            subtitle = preview if preview else ("在线" if is_online else "离线")
            self._add_conv_item(
                key, uname[0] if uname else "?",
                _AVATAR_COLORS[uid % len(_AVATAR_COLORS)],
                uname, subtitle, "",
                {"id": uid, "name": uname, "type": "p2p"},
                is_online=is_online,
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
            group_id = int(key[5:])
            group_name = str(group_id)
            for g in self._my_groups:
                if g["group_id"] == group_id:
                    group_name = g.get("remark") or g["group_name"]
                    break
            # 群聊数据尚未加载时，显示"加载中…"而不是群ID
            if group_name == str(group_id):
                group_name = "加载中…"
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
            subtitle = preview if preview else ("在线" if is_online else "离线")
            self._add_conv_item(
                key, uname[0] if uname else "?",
                _AVATAR_COLORS[uid % len(_AVATAR_COLORS)],
                uname, subtitle, "",
                {"id": uid, "name": uname, "type": "p2p"},
                unread_count=count,
                is_online=is_online,
            )

    def _on_search_text_changed(self, text):
        """搜索框文字变化时过滤对话列表"""
        self._search_text = text.strip().lower()
        self._refresh_conv_list()

    def matches_search(self, name, subtitle):
        """判断名称或预览是否匹配搜索文字"""
        if not self._search_text:
            return True
        return self._search_text in name.lower() or self._search_text in subtitle.lower()

    def _get_conv_name(self, key):
        """根据 key 获取对话显示名称"""
        if key.startswith("room_"):
            group_id = int(key[5:])
            for g in self._my_groups:
                if g["group_id"] == group_id:
                    return g.get("remark") or g["group_name"]
            return f"群聊{group_id}"
        elif key.startswith("p2p_"):
            uid = int(key[4:])
            return self._find_user_name(uid)
        return key

    def _on_friend_list(self, msg):
        """收到好友列表时刷新对话列表（用于过滤非好友）"""
        self.state.friends = msg.get("friends", [])

        # 如果当前正在和好友聊天，更新头部显示名称（备注可能在好友面板已修改）
        if self._current_target and self._current_target["type"] == "p2p":
            uid = self._current_target["id"]
            for f in self.state.friends:
                if f.get("user_id") == uid:
                    new_name = f.get("remark") or f.get("username", f"用户{uid}")
                    if new_name != self._current_target["name"]:
                        self._current_target["name"] = new_name
                        self._chat_title.setText(new_name)
                        # 同步更新头像文字
                        avatar_text = new_name[0] if new_name else "?"
                        color = _AVATAR_COLORS[uid % len(_AVATAR_COLORS)]
                        self._header_avatar.setText(avatar_text)
                        self._header_avatar.setStyleSheet(f"""
                            font-size: 24px; font-weight: 600; color: white;
                            border-radius: 24px; background-color: {color};
                        """)
                        self._update_info_panel()
                    break
            self._refresh_conv_list()

    # ==================== 群聊管理 ====================

    def _on_group_list(self, msg):
        """收到群聊列表"""
        self._my_groups = msg.get("my_groups", [])
        self._available_groups = msg.get("available", [])

        # 如果当前正在查看某个群，更新其显示名称（备注优先）
        if self._current_target and self._current_target["type"] == "room":
            gid = self._current_target["id"]
            for g in self._my_groups:
                if g["group_id"] == gid:
                    new_name = g.get("remark") or g.get("group_name", "")
                    if new_name and new_name != self._current_target["name"]:
                        self._current_target["name"] = new_name
                        self._chat_title.setText(new_name)
                    break

        # 如果用户在等待加入群聊，自动弹出对话框
        if self._pending_join_dialog:
            self._pending_join_dialog = False
            if self._available_groups:
                self._show_join_group_dialog()

        # 首次加载时默认选中公共聊天室
        if self._current_target is None:
            self._select_room()
        else:
            self._refresh_conv_list()

    def _on_invited_to_group(self, msg):
        """被邀请加入群聊 — 自动刷新群聊列表使群聊出现在对话列表"""
        group_id = msg.get("group_id")
        group_name = msg.get("group_name")
        if group_id and group_name:
            # 先直接加入本地缓存，立即显示
            exists = any(g["group_id"] == group_id for g in self._my_groups)
            if not exists:
                self._my_groups.append({
                    "group_id": group_id,
                    "group_name": group_name,
                })
                self._refresh_conv_list()
            # 再从服务器获取完整列表确保数据一致
            self.net.send({"type": MT.GROUP_LIST})

    def _on_group_join(self, msg):
        """收到加入群聊结果"""
        if msg.get("ok"):
            self.net.send({"type": MT.GROUP_LIST})  # 刷新群聊列表
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "失败", msg.get("message", "加入群聊失败"))

    def _show_join_group_dialog(self):
        """显示加入群聊对话框"""
        # 如果可用列表为空，先请求并标记等待自动弹出
        if not self._available_groups:
            self._pending_join_dialog = True
            self.net.send({"type": MT.GROUP_LIST})
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "正在加载群聊列表…")
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
                font-size: 24px; padding: 8px;
            }
            QListWidget::item {
                padding: 12px 16px; border-radius: 8px;
            }
            QListWidget::item:hover { background: #F7F9FD; }
            QListWidget::item:selected { background: #E7EFFC; color: #1E293B; }
        """)

        for g in self._available_groups:
            item = QListWidgetItem(f"👥  {g['group_name']}  ({g['group_id']})")
            item.setData(Qt.UserRole, g["group_id"])
            list_widget.addItem(item)

        # 默认选中第一项
        if list_widget.count() > 0:
            list_widget.setCurrentRow(0)

        layout.addWidget(list_widget)

        join_btn = QPushButton("加入")
        join_btn.setFixedHeight(48)
        join_btn.setCursor(Qt.PointingHandCursor)
        join_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
            font-size: 24px; font-weight: 700;
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
                border-radius: 14px; font-size: 24px;
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
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先选择一个群聊")
            return
        group_id = selected.data(Qt.UserRole)
        self.net.send({"type": MT.GROUP_JOIN, "group_id": group_id})
        dialog.accept()

    # ==================== 右侧：聊天区域 ====================

    def _build_chat_area(self):
        """构建右侧聊天区域（对齐设计稿）"""
        self._chat_panel = QFrame()
        self._chat_panel.setStyleSheet("background-color: #F7F9FD;")

        layout = QVBoxLayout(self._chat_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 聊天头部（72px）
        self._build_chat_header()
        layout.addWidget(self._header)

        # 消息滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #FAFBFE; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(content)
        self._msg_layout.setContentsMargins(32, 26, 32, 26)
        self._msg_layout.setSpacing(20)
        self._msg_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(content)
        self._scroll = scroll
        layout.addWidget(scroll, 1)

        # 新消息提示按钮
        self._new_msg_hint = QPushButton("↓ 新消息")
        self._new_msg_hint.setFixedHeight(38)
        self._new_msg_hint.setCursor(Qt.PointingHandCursor)
        self._new_msg_hint.hide()
        self._new_msg_hint.setStyleSheet("""
            QPushButton {
                background: #2D6CF6; color: white; border: none;
                border-radius: 19px; font-size: 24px; font-weight: 700;
                padding: 0 22px; margin-right: 24px; margin-bottom: 4px;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        self._new_msg_hint.clicked.connect(self._scroll_to_bottom)
        layout.addWidget(self._new_msg_hint, alignment=Qt.AlignRight)

        # 监听滚动位置
        scroll.verticalScrollBar().valueChanged.connect(self._on_chat_scrolled)

        # 消息输入区域（卡片式）
        self._build_composer()
        layout.addWidget(self._composer)

    def _build_chat_header(self):
        """构建聊天头部（72px，带头像、名称、状态、操作按钮）"""
        self._header = QFrame()
        self._header.setFixedHeight(72)
        self._header.setStyleSheet("background-color: #F7F9FD; border-bottom: 1px solid #EEF1F7;")

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(28, 0, 28, 0)
        hl.setSpacing(15)

        # 左侧：头像
        self._header_avatar = self._create_avatar(48, "", "#6366F1")
        hl.addWidget(self._header_avatar)

        # 中间：名称 + 状态文字
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        # 第一行：名称 + 状态标记 + 加密标签
        top_row = QHBoxLayout()
        top_row.setSpacing(9)

        self._chat_title = QLabel("公共聊天室")
        self._chat_title.setStyleSheet("font-size: 32px; font-weight: 800; color: #1E293B; background: transparent;")
        top_row.addWidget(self._chat_title)

        # 在线状态标签（私聊用）
        self._online_status_label = QLabel("")
        self._online_status_label.setStyleSheet("""
            font-size: 24px; font-weight: 600; color: #34D399;
            background: transparent;
        """)
        self._online_status_label.hide()
        top_row.addWidget(self._online_status_label)

        # 设置按钮（群聊用）
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(24, 24)
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setVisible(False)
        self._settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #94A3B8; border: none;
                border-radius: 8px; font-size: 24px;
            }
            QPushButton:hover { background: #F1F5FB; color: #64748B; }
        """)
        self._settings_btn.clicked.connect(self._on_open_settings)
        top_row.addWidget(self._settings_btn)

        top_row.addStretch()
        text_col.addLayout(top_row)

        # 第二行：描述 / 在线人数 / 加密标记
        bot_row = QHBoxLayout()
        bot_row.setSpacing(7)

        self._chat_subtitle = QLabel("")
        self._chat_subtitle.setStyleSheet("font-size: 25px; color: #6B7A90; background: transparent;")
        bot_row.addWidget(self._chat_subtitle)

        # 加密标识
        self._encryption_badge = QLabel("🔒 消息已加密")
        self._encryption_badge.setStyleSheet("""
            font-size: 24px; color: #2D6CF6; background: #E7EFFC;
            padding: 2px 9px; border-radius: 9px;
        """)
        self._encryption_badge.hide()
        bot_row.addWidget(self._encryption_badge)

        bot_row.addStretch()
        text_col.addLayout(bot_row)

        hl.addLayout(text_col, 1)

        # 右侧：操作按钮
        hl.addStretch()

        # 群成员按钮
        self._members_btn = QPushButton("👥")
        self._members_btn.setFixedSize(40, 40)
        self._members_btn.setCursor(Qt.PointingHandCursor)
        self._members_btn.setStyleSheet("""
            QPushButton {
                background: #fff; border: none; border-radius: 13px;
                font-size: 24px;
            }
            QPushButton:hover { background: #F1F5FB; }
        """)
        self._members_btn.hide()
        self._members_btn.clicked.connect(self._on_members_btn)
        hl.addWidget(self._members_btn)

        # 更多菜单按钮
        self._more_btn = QPushButton("⋯")
        self._more_btn.setFixedSize(40, 40)
        self._more_btn.setCursor(Qt.PointingHandCursor)
        self._more_btn.setStyleSheet("""
            QPushButton {
                background: #fff; border: none; border-radius: 13px;
                font-size: 26px; color: #6B7A90;
            }
            QPushButton:hover { background: #F1F5FB; }
        """)
        self._more_btn.clicked.connect(self._on_more_btn)
        hl.addWidget(self._more_btn)

    def _build_composer(self):
        """构建卡片式输入区域（对齐设计稿：白底圆角卡片 + 工具栏 + 输入行）"""
        self._composer = QFrame()
        self._composer.setStyleSheet("background-color: #EEF2FA;")

        cl = QVBoxLayout(self._composer)
        cl.setContentsMargins(24, 16, 24, 20)
        cl.setSpacing(0)

        # 白色卡片容器
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #fff; border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(0)

        # 工具栏行：附件 + 表情 + 文件 + 加密标识
        toolbar = QFrame()
        toolbar.setStyleSheet("background: transparent;")
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(4, 2, 4, 12)
        tl.setSpacing(18)

        # 工具栏图标
        toolbar_icons = [
            ("📎", "附件"),  # attachment
            ("😊", "表情"),  # emoji
            ("📄", "文件"),  # file
        ]
        for icon, tip in toolbar_icons:
            btn = QPushButton(icon)
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; border: none; font-size: 24px;
                    color: #94A3B8;
                }
                QPushButton:hover { color: #2D6CF6; }
            """)
            tl.addWidget(btn)

        tl.addStretch()

        # 加密标识（右对齐）
        encrypt_label = QLabel("🔒 端对端加密")
        encrypt_label.setStyleSheet("""
            font-size: 24px; color: #B0BAC8; background: transparent;
        """)
        tl.addWidget(encrypt_label)

        # 分隔线
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #F0F4F9;")

        # 输入行：文本框 + 发送按钮
        input_row = QFrame()
        input_row.setStyleSheet("background: transparent;")
        il = QHBoxLayout(input_row)
        il.setContentsMargins(4, 12, 4, 2)
        il.setSpacing(13)

        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("输入消息，Enter 发送…")
        self._text_input.setFixedHeight(48)
        self._text_input.setStyleSheet("""
            QLineEdit {
                background-color: transparent; border: none;
                font-size: 28px; color: #1E293B;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        self._text_input.returnPressed.connect(self._send_message)
        il.addWidget(self._text_input)

        # 发送按钮（圆角渐变）
        send_btn = QPushButton("➤")
        send_btn.setFixedSize(52, 52)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 16px;
                font-size: 28px; font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        send_btn.clicked.connect(self._send_message)
        il.addWidget(send_btn)

        card_layout.addWidget(toolbar)
        card_layout.addWidget(divider)
        card_layout.addWidget(input_row)

        cl.addWidget(card)

    # ==================== 右侧：信息面板 ====================

    def _build_info_panel(self):
        """构建右侧信息面板（私聊时显示用户信息和共享文件）"""
        self._info_panel = QFrame()
        self._info_panel.setFixedWidth(260)
        self._info_panel.setStyleSheet("background-color: #F7F9FD; border-left: 1px solid #EEF1F7;")

        layout = QVBoxLayout(self._info_panel)
        layout.setContentsMargins(20, 26, 20, 26)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)

        # ====== 用户信息区域 ======
        self._info_avatar_container = QWidget()
        self._info_avatar_container.setFixedSize(74, 74)
        self._info_avatar_container.setStyleSheet("background: transparent;")

        self._info_avatar = self._create_avatar(74, "", "#6366F1")
        self._info_avatar.setParent(self._info_avatar_container)

        layout.addWidget(self._info_avatar_container, alignment=Qt.AlignHCenter)

        self._info_name = QLabel("")
        self._info_name.setStyleSheet("font-size: 28px; font-weight: 700; color: #1E293B; background: transparent;")
        self._info_name.setAlignment(Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self._info_name)

        self._info_status = QLabel("")
        self._info_status.setStyleSheet("font-size: 24px; color: #6B7A90; background: transparent;")
        self._info_status.setAlignment(Qt.AlignCenter)
        layout.addSpacing(5)
        layout.addWidget(self._info_status)

        self._info_desc = QLabel("")
        self._info_desc.setStyleSheet("font-size: 24px; color: #94A3B8; background: transparent;")
        self._info_desc.setAlignment(Qt.AlignCenter)
        layout.addSpacing(4)
        layout.addWidget(self._info_desc)

        # 操作按钮
        layout.addSpacing(16)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(9)
        btn_row.setAlignment(Qt.AlignHCenter)

        chat_btn = QPushButton("💬")
        chat_btn.setFixedSize(40, 40)
        chat_btn.setCursor(Qt.PointingHandCursor)
        chat_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; border: none; border-radius: 13px;
                font-size: 24px;
            }
            QPushButton:hover { background: #D1E3FA; }
        """)
        btn_row.addWidget(chat_btn)

        self._info_remove_btn = QPushButton("✕")
        self._info_remove_btn.setFixedSize(40, 40)
        self._info_remove_btn.setCursor(Qt.PointingHandCursor)
        self._info_remove_btn.setStyleSheet("""
            QPushButton {
                background: #FEF2F2; border: none; border-radius: 13px;
                font-size: 24px; color: #EF4444;
            }
            QPushButton:hover { background: #FEE2E2; }
        """)
        self._info_remove_btn.clicked.connect(self._on_remove_friend)
        btn_row.addWidget(self._info_remove_btn)

        layout.addLayout(btn_row)

        # 分隔线
        layout.addSpacing(22)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #E5EAF3;")
        layout.addWidget(sep)

        # ====== 共享文件区域 ======
        layout.addSpacing(20)
        files_title = QLabel("共享文件")
        files_title.setStyleSheet("""
            font-size: 24px; font-weight: 700; color: #94A3B8;
            letter-spacing: 1px; background: transparent;
        """)
        layout.addWidget(files_title)

        layout.addSpacing(14)
        self._info_files_layout = QVBoxLayout()
        self._info_files_layout.setSpacing(9)
        self._info_files_layout.setAlignment(Qt.AlignTop)

        # 示例：暂无文件
        self._info_no_files = QLabel("暂无共享文件")
        self._info_no_files.setStyleSheet("font-size: 24px; color: #CBD5E1; background: transparent; padding: 10px 0;")
        self._info_no_files.setAlignment(Qt.AlignCenter)
        self._info_files_layout.addWidget(self._info_no_files)

        layout.addLayout(self._info_files_layout)
        layout.addStretch()

    def _update_info_panel(self):
        """根据当前聊天目标更新右侧信息面板"""
        if not self._current_target or self._current_target["type"] != "p2p":
            self._info_panel.hide()
            return

        self._info_panel.show()
        target = self._current_target
        uid = target["id"]
        uname = target["name"]

        # 更新头像
        avatar_text = uname[0] if uname else "?"
        color = _AVATAR_COLORS[uid % len(_AVATAR_COLORS)]
        self._info_avatar.setText(avatar_text)
        self._info_avatar.setStyleSheet(f"""
            font-size: 34px; font-weight: 600; color: white;
            border-radius: 37px; background-color: {color};
        """)

        self._info_name.setText(uname)

        # 在线状态
        online_ids = {u.get("user_id") for u in self.state.online_users}
        is_online = uid in online_ids
        if is_online:
            self._info_status.setText("🟢 在线")
        else:
            self._info_status.setText("⚪ 离线")

        # 查找好友信息中的班级
        desc = ""
        for f in (self.state.friends or []):
            if f.get("user_id") == uid:
                cls = f.get("class_name", "")
                if cls:
                    desc = cls
                break
        self._info_desc.setText(desc)

    # ==================== 联系人切换 ====================

    def _on_contact_selected(self, target):
        """点击联系人切换聊天"""
        self._current_target = target
        key = f"{target['type']}_{target['id']}"

        if target["type"] == "room":
            self._update_chat_header_for_group(target)
        else:
            self._update_chat_header_for_p2p(target)

        # 清空该对话的未读计数
        self._unread_counts.pop(key, None)

        self._clear_messages()
        # 网络连接后才加载历史（初始化时网络尚未就绪）
        if self.state.user_id is not None:
            self._load_history()
        self._refresh_conv_list()
        self._update_info_panel()

    def _update_chat_header_for_group(self, target):
        """更新聊天头部为群聊模式"""
        self._chat_title.setText(target["name"])

        # 群聊头像（渐变+图标）
        self._header_avatar.setText("👥")
        self._header_avatar.setStyleSheet("""
            font-size: 24px; font-weight: 600; color: white;
            border-radius: 24px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #4F8DFD, stop:1 #2D6CF6);
        """)

        # 状态标签隐藏
        self._online_status_label.hide()

        # 设置按钮可见
        self._settings_btn.show()

        # 子标题：在线人数
        online_count = len(self.state.online_users)
        total_count = len(self.state.friends or []) + 1  # 包含自己
        self._chat_subtitle.setText(f"● {total_count} 人 · {online_count} 在线")
        self._chat_subtitle.show()

        # 加密标识
        self._encryption_badge.show()
        self._members_btn.show()

    def _update_chat_header_for_p2p(self, target):
        """更新聊天头部为私聊模式"""
        self._chat_title.setText(target["name"])

        # 头像
        uid = target["id"]
        avatar_text = target["name"][0] if target["name"] else "?"
        color = _AVATAR_COLORS[uid % len(_AVATAR_COLORS)]
        self._header_avatar.setText(avatar_text)
        self._header_avatar.setStyleSheet(f"""
            font-size: 24px; font-weight: 600; color: white;
            border-radius: 24px; background-color: {color};
        """)

        # 在线状态
        online_ids = {u.get("user_id") for u in self.state.online_users}
        is_online = uid in online_ids
        self._online_status_label.setText("在线" if is_online else "离线")
        self._online_status_label.setStyleSheet(
            f"font-size: 24px; font-weight: 600; color: {'#34D399' if is_online else '#94A3B8'}; background: transparent;"
        )
        self._online_status_label.show()

        # 设置按钮隐藏（私聊没有群设置）
        self._settings_btn.hide()

        # 子标题：班级信息 + 加密
        desc = "端对端加密已启用"
        for f in (self.state.friends or []):
            if f.get("user_id") == uid:
                cls = f.get("class_name", "")
                if cls:
                    desc = f"{cls} · {desc}"
                break
        self._chat_subtitle.setText(desc)
        self._chat_subtitle.show()

        # 加密标识隐藏
        self._encryption_badge.hide()
        self._members_btn.hide()

    def _select_room(self):
        """默认选中第一个群聊（公共聊天室优先）"""
        for g in self._my_groups:
            if g["group_id"] == PUBLIC_ROOM_ID:
                display_name = g.get("remark") or g["group_name"]
                self._on_contact_selected({"id": g["group_id"], "name": display_name, "type": "room"})
                return
        if self._my_groups:
            g = self._my_groups[0]
            display_name = g.get("remark") or g["group_name"]
            self._on_contact_selected({"id": g["group_id"], "name": display_name, "type": "room"})
            return

    def _on_open_settings(self):
        """打开群设置对话框"""
        if not self._current_target or self._current_target["type"] != "room":
            return
        dlg = GroupSettingsDialog(
            self.app,
            self._current_target["id"],
            self._current_target["name"],
            self,
        )
        dlg.exec_()

    def _on_group_name_updated(self, msg):
        """收到群名变更广播 — 更新本地缓存的群名（用户设置了备注则不覆盖）"""
        group_id = msg.get("group_id", "")
        new_name = msg.get("group_name", "")
        if not group_id or not new_name:
            return

        # 更新 _my_groups 中的缓存
        has_remark = False
        for g in self._my_groups:
            if g["group_id"] == group_id:
                has_remark = bool(g.get("remark"))
                g["group_name"] = new_name   # 始终更新原始群名
                break

        # 如果正在查看该群聊，更新标题（备注优先）
        if (self._current_target
                and self._current_target["type"] == "room"
                and self._current_target["id"] == group_id):
            if not has_remark:
                self._current_target["name"] = new_name
                self._chat_title.setText(new_name)

        # 刷新左侧列表
        self._refresh_conv_list()

    # ==================== 群成员弹窗 ====================

    def _on_members_btn(self):
        """点击👥成员按钮 — 请求群成员列表"""
        if not self._current_target or self._current_target["type"] != "room":
            return
        group_id = self._current_target["id"]
        self._pending_members_group = group_id
        self.net.send({"type": MT.GROUP_MEMBERS, "group_id": group_id})

    def _on_group_members_resp(self, msg):
        """收到群成员列表响应 — 显示成员弹窗"""
        group_id = msg.get("group_id", "")
        if group_id != self._pending_members_group:
            return
        self._pending_members_group = None

        members = msg.get("members", [])
        group_name = msg.get("group_name", "")

        dialog = QDialog(self)
        dialog.setWindowTitle(f"群成员 - {group_name}")
        dialog.setFixedSize(360, 460)
        dialog.setStyleSheet("""
            QDialog { background-color: #F7F9FD; border-radius: 16px; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"👥  {group_name}  ({len(members)} 人)")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #1E293B;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        member_layout = QVBoxLayout(content)
        member_layout.setContentsMargins(0, 0, 0, 0)
        member_layout.setSpacing(6)
        member_layout.setAlignment(Qt.AlignTop)

        current_user_id = self.state.user_id
        for m in members:
            mid = m.get("user_id", 0)
            mname = m.get("remark") or m.get("nickname") or m.get("username", f"用户{mid}")
            is_me = mid == current_user_id
            role = m.get("role", 0)
            online = m.get("online", False)

            card = QFrame()
            card.setFixedHeight(60)
            card.setStyleSheet("""
                QFrame { background-color: #fff; border-radius: 14px; }
            """)
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 10, 14, 10)
            row.setSpacing(12)

            avatar = self._create_avatar(40, mname[0] if mname else "?",
                                          _AVATAR_COLORS[mid % len(_AVATAR_COLORS)])
            row.addWidget(avatar)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)

            name_row = QHBoxLayout()
            name_row.setSpacing(6)
            name_label = QLabel(f"{mname}{' (我)' if is_me else ''}")
            name_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #1E293B; background: transparent;")
            name_row.addWidget(name_label)

            if role == 1:
                role_label = QLabel("管理员")
                role_label.setStyleSheet("""
                    font-size: 24px; font-weight: 700; color: #2D6CF6;
                    background: #E7EFFC; padding: 1px 7px; border-radius: 6px;
                """)
                name_row.addWidget(role_label)
            elif m.get("user_id") == self.state.user_id:
                pass  # 自己显示"我"标签就够了
            else:
                pass

            name_row.addStretch()
            text_col.addLayout(name_row)

            status_label = QLabel("🟢 在线" if online else "⚪ 离线")
            status_label.setStyleSheet(
                f"font-size: 24px; color: {'#34D399' if online else '#94A3B8'}; background: transparent;")
            text_col.addWidget(status_label)

            row.addLayout(text_col, 1)
            member_layout.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(48)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #fff; color: #94A3B8; border: 1px solid #E5EAF3;
                border-radius: 14px; font-size: 24px;
            }
            QPushButton:hover { background: #F7F9FD; color: #64748B; }
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec_()

    # ==================== 更多菜单 ====================

    def _on_more_btn(self):
        """点击⋯更多按钮 — 弹出操作菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #fff; border: 1px solid #E5EAF3;
                border-radius: 12px; padding: 6px;
                font-size: 24px; color: #1E293B;
            }
            QMenu::item {
                padding: 10px 20px; border-radius: 8px;
            }
            QMenu::item:selected { background-color: #F1F5FB; }
        """)

        if self._current_target:
            target = self._current_target
            # 复制名称
            copy_action = QAction(f"📋 复制 {target['name']}", self)
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(target["name"]))
            menu.addAction(copy_action)

            if target["type"] == "p2p":
                # 查看好友信息
                info_action = QAction("ℹ️ 好友信息", self)
                info_action.triggered.connect(lambda: self._show_friend_info(target))
                menu.addAction(info_action)

                # 删除好友
                delete_action = QAction("🗑️ 删除好友", self)
                delete_action.triggered.connect(lambda: self._on_remove_friend())
                menu.addAction(delete_action)
            else:
                # 群聊信息
                info_action = QAction("ℹ️ 群聊信息", self)
                info_action.triggered.connect(self._on_open_settings)
                menu.addAction(info_action)

        menu.exec_(self._more_btn.mapToGlobal(
            self._more_btn.rect().bottomLeft()))

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _show_friend_info(self, target):
        """显示好友信息"""
        QMessageBox.information(self, "好友信息",
                                f"用户名: {target['name']}\nID: {target['id']}")

    # ==================== 删除好友 ====================

    def _on_remove_friend(self):
        """删除好友（发送请求并确认）"""
        if not self._current_target or self._current_target["type"] != "p2p":
            return
        target = self._current_target
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除好友 {target['name']} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.net.send({
                "type": MT.FRIEND_REMOVE,
                "friend_id": target["id"],
            })

    def _on_friend_remove_resp(self, msg):
        """收到删除好友响应"""
        if msg.get("ok"):
            # 刷新好友列表
            self.net.send({"type": MT.FRIEND_LIST})
            # 如果当前正在和该好友聊天，清空聊天区域
            if self._current_target and self._current_target["type"] == "p2p":
                self._current_target = None
                self._clear_messages()
                self._info_panel.hide()
        else:
            QMessageBox.warning(self, "删除失败", msg.get("reason", "删除好友失败"))

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
            self._refresh_conv_list()  # 刷新左侧预览
        else:
            self._unread_counts[key] = self._unread_counts.get(key, 0) + 1
            self._refresh_conv_list()

    def _on_room_chat(self, msg):
        """收到群聊消息，按 room_id 路由"""
        sender_id = msg.get("from")
        if sender_id == self.state.user_id:
            return
        room_id = msg.get("room_id", 0)
        if not room_id:
            return

        plain = self.app.crypto.decrypt(msg.get("content", ""))
        ts = msg.get("ts", "")
        key = f"room_{room_id}"

        # 如果收到的群聊消息来自一个尚未加载的群，主动获取列表
        if not any(g["group_id"] == room_id for g in self._my_groups):
            self.net.send({"type": MT.GROUP_LIST})

        # 系统消息（from=0，如群名变更通知）
        if sender_id == 0:
            self._last_msg_previews[key] = plain
            self._last_msg_times[key] = ts or int(time.time())
            viewing = (
                self._current_target
                and self._current_target["type"] == "room"
                and self._current_target["id"] == room_id
            )
            if viewing:
                self._append_system_msg(plain)
                if self._is_at_bottom():
                    self._scroll_to_bottom()
                else:
                    self._new_msg_hint.show()
            self._refresh_conv_list()
            return

        sender_name = self._find_user_name(sender_id)

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
            self._refresh_conv_list()  # 刷新左侧预览
        else:
            self._unread_counts[key] = self._unread_counts.get(key, 0) + 1
            self._refresh_conv_list()

    def _on_user_list(self, msg):
        """在线列表更新"""
        self.state.online_users = msg.get("online_users", [])
        self._refresh_conv_list()
        # 更新当前聊天头部的在线状态
        if self._current_target:
            if self._current_target["type"] == "p2p":
                self._update_chat_header_for_p2p(self._current_target)
                self._update_info_panel()
            else:
                self._update_chat_header_for_group(self._current_target)

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
            # 系统消息（from=0）
            if sender_id == 0:
                self._append_system_msg(plain)
                continue
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
        """添加消息气泡（对齐设计稿：圆角风格 5px→18px）"""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(13)

        if is_self:
            layout.setDirection(QHBoxLayout.RightToLeft)

        # 圆形头像（42px）
        avatar_text = sender_name[0] if sender_name else "?"
        avatar = self._create_avatar(42, avatar_text, "#6366F1")
        layout.addWidget(avatar)

        # 气泡列
        bubble_col = QVBoxLayout()
        bubble_col.setSpacing(6)

        # 名字 · 时间（对方消息显示发送者，自己消息只显示时间）
        if is_self:
            info_text = ts if ts else ""
        else:
            info_text = f"{sender_name} · {ts}" if ts else sender_name

        if info_text:
            info_label = QLabel(info_text)
            info_label.setStyleSheet("""
                font-size: 24px; color: #94A3B8; background: transparent;
            """)
            # 自己的消息时间右对齐
            if is_self:
                info_label.setAlignment(Qt.AlignRight)
            bubble_col.addWidget(info_label)

        # 气泡内容
        bubble = QLabel(content)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(520)
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        bubble.setContentsMargins(17, 13, 17, 13)

        if is_self:
            bubble.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #4F8DFD, stop:1 #2D6CF6);
                    color: white; border-radius: 18px;
                    font-size: 24px; line-height: 1.6;
                }
            """)

        bubble_col.addWidget(bubble, alignment=Qt.AlignLeft if not is_self else Qt.AlignRight)
        layout.addLayout(bubble_col)
        layout.addStretch()

        self._msg_layout.addWidget(container)

    def _append_system_msg(self, text):
        """添加系统提示"""
        # 设计稿风格：居中灰底圆角标签
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(text)
        label.setStyleSheet("""
            font-size: 24px; color: #94A3B8;
            background: #E2E8F2; padding: 6px 16px;
            border-radius: 12px;
        """)
        layout.addWidget(label)

        self._msg_layout.addWidget(container)

    def _find_user_name(self, user_id):
        """根据用户ID查找显示名称（优先使用备注）"""
        if user_id == self.state.user_id:
            return self.state.username or "我"
        # 1. 查好友列表中的备注
        for f in (self.state.friends or []):
            if f.get("user_id") == user_id:
                return f.get("remark") or f.get("nickname") or f.get("username", f"用户{user_id}")
        # 2. 查在线用户
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
