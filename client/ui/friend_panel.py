"""好友面板（客户端）

支持好友列表展示、添加好友、设置备注功能。
UI 风格对齐设计稿：卡片式好友列表、圆形头像、在线状态标识。

author: 董钧豪
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget, QInputDialog,
    QMessageBox, QDialog,
)
from PyQt5.QtCore import Qt, QTimer
import time
from client.core.base_panel import BasePanel
from client.ui.create_group_dialog import CreateGroupDialog
from common.messages import MT


# 头像颜色池
_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]


class FriendPanel(BasePanel):
    """好友面板"""

    def __init__(self, parent, app):
        self._friends = []  # 好友列表缓存
        self._filter = "all"  # 当前筛选：all/online/offline
        self._pending_requests = []  # 待处理的好友申请
        self._rejected_requests = []  # 被拒绝的好友申请
        super().__init__(parent, app)

    def subscribe(self):
        """订阅好友相关消息"""
        self.net.on(MT.FRIEND_LIST_RESP, self._on_friend_list)
        self.net.on(MT.FRIEND_ADD_RESP, self._on_friend_add)
        self.net.on(MT.FRIEND_REQ_NOTIFY, self._on_friend_req_notify)
        self.net.on(MT.FRIEND_AGREE_RESP, self._on_friend_agree_resp)
        self.net.on(MT.FRIEND_REJECTED, self._on_friend_rejected)
        self.net.on(MT.FRIEND_REQ_LIST_RESP, self._on_friend_req_list)
        self.net.on(MT.GROUP_CREATE_RESP, self._on_group_create_resp)
        self.net.on(MT.GROUP_INVITE, self._on_group_invited)
        self.net.on(MT.USER_LIST, self._on_user_list)
        self._build_ui()

    def showEvent(self, event):
        """面板显示时请求初始数据"""
        super().showEvent(event)
        if self.state.user_id is not None and not self._friends:
            self.net.send({"type": MT.FRIEND_LIST})

    def _build_ui(self):
        """构建好友面板UI"""
        self.setStyleSheet("background-color: #EEF2FA;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ========== 标题栏 ==========
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("background-color: #fff; border-bottom: 1px solid #EEF1F7;")

        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)

        title = QLabel("好友列表")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B;")
        hl.addWidget(title)

        self._count_badge = QLabel("0 位")
        self._count_badge.setStyleSheet("""
            font-size: 15px; font-weight: 700; color: #2D6CF6;
            background: #E7EFFC; padding: 3px 14px; border-radius: 10px;
        """)
        hl.addWidget(self._count_badge)

        hl.addStretch()

        # 发起群聊按钮
        group_btn = QPushButton("＋ 发起群聊")
        group_btn.setFixedHeight(44)
        group_btn.setCursor(Qt.PointingHandCursor)
        group_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; color: #2D6CF6;
                border: none; border-radius: 13px;
                font-size: 16px; font-weight: 700; padding: 0 20px;
            }
            QPushButton:hover { background: #D1E3FA; }
        """)
        group_btn.clicked.connect(self._on_create_group)
        hl.addWidget(group_btn)

        add_btn = QPushButton("＋ 添加好友")
        add_btn.setFixedHeight(44)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 13px;
                font-size: 16px; font-weight: 700; padding: 0 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        add_btn.clicked.connect(self._on_add_friend)
        hl.addWidget(add_btn)

        layout.addWidget(header)

        # ========== 筛选和搜索 ==========
        filter_bar = QFrame()
        filter_bar.setStyleSheet("background-color: #F7F9FD;")
        filter_bar.setFixedHeight(70)

        fl = QHBoxLayout(filter_bar)
        fl.setContentsMargins(26, 14, 26, 14)
        fl.setSpacing(10)

        # 搜索框
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索好友")
        self._search_box.setFixedHeight(50)
        self._search_box.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: none; border-radius: 14px;
                font-size: 15px; color: #1E293B; padding: 0 16px;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        fl.addWidget(self._search_box)

        # 筛选按钮
        self._filter_btns = {}
        for key, label in [("all", "全部"), ("online", "在线"), ("offline", "离线")]:
            btn = QPushButton(label)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            self._filter_btns[key] = btn
            fl.addWidget(btn)

        self._update_filter_style()

        layout.addWidget(filter_bar)

        # ========== 好友列表（滚动） ==========
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #F7F9FD; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        self._friend_content = QWidget()
        self._friend_layout = QVBoxLayout(self._friend_content)
        self._friend_layout.setContentsMargins(26, 12, 26, 12)
        self._friend_layout.setSpacing(6)
        self._friend_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._friend_content)
        layout.addWidget(scroll, 1)

        # 网络连接后加载好友列表（初始化时网络尚未就绪）
        if self.state.user_id is not None:
            self.net.send({"type": MT.FRIEND_LIST})

    # ==================== 筛选按钮样式 ====================

    def _update_filter_style(self):
        """更新筛选按钮样式"""
        for key, btn in self._filter_btns.items():
            if key == self._filter:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #E7EFFC; color: #2D6CF6;
                        border: none; border-radius: 13px;
                        font-size: 15px; font-weight: 700; padding: 0 18px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #fff; color: #94A3B8;
                        border: none; border-radius: 13px;
                        font-size: 15px; padding: 0 18px;
                    }
                    QPushButton:hover { background: #F7F9FD; color: #64748B; }
                """)

    def _set_filter(self, key):
        """设置筛选条件"""
        self._filter = key
        self._update_filter_style()
        self._refresh_friend_list()

    # ==================== 圆形头像 ====================

    def _create_avatar(self, size, text, color):
        """创建圆形头像"""
        avatar = QLabel(text)
        avatar.setFixedSize(size, size)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            font-size: {size // 2 - 2}px;
            font-weight: 600;
            color: white;
            border-radius: {size // 2}px;
            background-color: {color};
        """)
        return avatar

    # ==================== 好友列表渲染 ====================

    def _refresh_friend_list(self):
        """刷新好友列表"""
        while self._friend_layout.count():
            child = self._friend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 1. 待处理的好友申请（置顶显示）
        if self._pending_requests:
            self._add_section_label(f"好友申请 · {len(self._pending_requests)} 条待处理")
            for req in self._pending_requests:
                self._add_request_card(req)

        # 2. 已拒绝的好友申请
        if self._rejected_requests:
            self._add_section_label("已拒绝的申请")
            for req in self._rejected_requests:
                self._add_rejected_card(req)

        # 3. 按筛选条件过滤好友
        online_ids = {u["user_id"] for u in self.state.online_users}
        filtered = self._friends
        if self._filter == "online":
            filtered = [f for f in self._friends if f.get("user_id") in online_ids]
        elif self._filter == "offline":
            filtered = [f for f in self._friends if f.get("user_id") not in online_ids]

        if filtered:
            # 分组：在线 / 离线
            online_friends = [f for f in filtered if f.get("user_id") in online_ids]
            offline_friends = [f for f in filtered if f.get("user_id") not in online_ids]

            if online_friends:
                self._add_section_label(f"在线 · {len(online_friends)} 人")
                for i, f in enumerate(online_friends):
                    self._add_friend_card(f, is_online=True,
                                          color=_AVATAR_COLORS[i % len(_AVATAR_COLORS)])

            if offline_friends:
                self._add_section_label(f"离线 · {len(offline_friends)} 人")
                for i, f in enumerate(offline_friends):
                    self._add_friend_card(f, is_online=False,
                                          color=_AVATAR_COLORS[(i + len(online_friends)) % len(_AVATAR_COLORS)])
        elif not self._pending_requests:
            empty = QLabel("暂无好友")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("font-size: 14px; color: #94A3B8; padding: 60px 0; background: transparent;")
            self._friend_layout.addWidget(empty)

        self._friend_layout.addStretch()

    def _add_section_label(self, text):
        """添加分组标题"""
        container = QFrame()
        container.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 10, 4, 6)

        label = QLabel(text)
        label.setStyleSheet("font-size: 14px; font-weight: 700; color: #94A3B8; letter-spacing: 1px; background: transparent;")
        layout.addWidget(label)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #E5EAF3;")
        layout.addWidget(line, 1)

        self._friend_layout.addWidget(container)

    def _add_rejected_card(self, req):
        """添加已拒绝的申请卡片（只读展示）"""
        container = QFrame()
        container.setFixedHeight(76)
        container.setStyleSheet("""
            QFrame { background-color: #F1F5F9; border-radius: 18px; border: 1px solid #E2E8F0; }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        name = req.get("nickname") or req.get("username", "未知")
        avatar = self._create_avatar(48, name[0] if name else "?", "#94A3B8")
        layout.addWidget(avatar)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #64748B; background: transparent;")
        text_col.addWidget(name_label)

        reason = req.get("reject_reason", "")
        hint_text = f"已拒绝 · {reason}" if reason else "已拒绝"
        hint_label = QLabel(hint_text)
        hint_label.setStyleSheet("font-size: 14px; color: #94A3B8; background: transparent;")
        text_col.addWidget(hint_label)
        layout.addLayout(text_col, 1)

        self._friend_layout.addWidget(container)

    def _add_request_card(self, req):
        """添加好友申请卡片（含同意/拒绝按钮）"""
        container = QFrame()
        container.setFixedHeight(76)
        container.setStyleSheet("""
            QFrame { background-color: #FFF8E7; border-radius: 18px; border: 1px solid #FDE68A; }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        # 申请人信息
        name = req.get("nickname") or req.get("username", "未知")
        avatar = self._create_avatar(48, name[0] if name else "?", "#F59E0B")
        layout.addWidget(avatar)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #1E293B; background: transparent;")
        text_col.addWidget(name_label)
        hint_label = QLabel("想加你为好友")
        hint_label.setStyleSheet("font-size: 14px; color: #92400E; background: transparent;")
        text_col.addWidget(hint_label)
        layout.addLayout(text_col, 1)

        # 同意按钮
        agree_btn = QPushButton("同意")
        agree_btn.setFixedHeight(38)
        agree_btn.setCursor(Qt.PointingHandCursor)
        agree_btn.setStyleSheet("""
            QPushButton {
                background: #34D399; color: white; border: none;
                border-radius: 10px; font-size: 14px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover { background: #10B981; }
        """)
        from_id = req.get("from_id")
        agree_btn.clicked.connect(
            lambda checked, fid=from_id: self.net.send(
                {"type": MT.FRIEND_AGREE, "from_id": fid}
            )
        )
        layout.addWidget(agree_btn)

        # 拒绝按钮
        reject_btn = QPushButton("拒绝")
        reject_btn.setFixedHeight(38)
        reject_btn.setCursor(Qt.PointingHandCursor)
        reject_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #94A3B8; border: none;
                border-radius: 10px; font-size: 14px; padding: 0 18px;
            }
            QPushButton:hover { background: #E2E8F0; color: #64748B; }
        """)
        reject_btn.clicked.connect(
            lambda checked, fid=from_id: self._on_reject_friend(fid)
        )
        layout.addWidget(reject_btn)

        self._friend_layout.addWidget(container)

    def _add_friend_card(self, friend, is_online, color):
        """添加好友卡片"""
        container = QFrame()
        container.setFixedHeight(86)
        container.setStyleSheet("""
            QFrame {
                background-color: #fff; border-radius: 18px;
            }
            QFrame:hover { background-color: #F7F9FD; }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 16, 20, 16)
        layout.setSpacing(16)

        # 圆形头像（带在线状态点）
        avatar_container = QWidget()
        avatar_container.setFixedSize(54, 54)
        avatar_container.setStyleSheet("background: transparent;")

        name = friend.get("remark") or friend.get("username", "?")
        avatar_text = name[0] if name else "?"
        avatar = self._create_avatar(58, avatar_text, color)
        avatar.setParent(avatar_container)

        # 在线状态点
        dot = QLabel(avatar_container)
        dot.setFixedSize(14, 14)
        if is_online:
            dot.setStyleSheet("background-color: #34D399; border-radius: 7px; border: 2.5px solid #fff;")
        else:
            dot.setStyleSheet("background-color: #CBD5E1; border-radius: 7px; border: 2.5px solid #fff;")
        dot.move(40, 40)

        layout.addWidget(avatar_container)

        # 文字信息
        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E293B; background: transparent;")
        text_col.addWidget(name_label)

        status_label = QLabel("在线" if is_online else "离线")
        status_label.setStyleSheet(
            f"font-size: 15px; font-weight: 500; color: {'#34D399' if is_online else '#94A3B8'}; background: transparent;")
        text_col.addWidget(status_label)

        layout.addLayout(text_col, 1)

        # 操作按钮
        msg_btn = QPushButton("💬")
        msg_btn.setFixedSize(40, 40)
        msg_btn.setCursor(Qt.PointingHandCursor)
        msg_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; color: #2D6CF6;
                border: none; border-radius: 13px; font-size: 18px;
            }
            QPushButton:hover { background: #D1E3FA; }
        """)
        friend_id = friend.get("user_id")
        friend_name = friend.get("username", "")
        msg_btn.clicked.connect(
            lambda checked, fid=friend_id, fname=friend_name:
                self._switch_to_chat(fid, fname)
        )
        layout.addWidget(msg_btn)

        # 更多按钮
        more_btn = QPushButton("⋯")
        more_btn.setFixedSize(40, 40)
        more_btn.setCursor(Qt.PointingHandCursor)
        more_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #94A3B8;
                border: none; border-radius: 13px; font-size: 18px;
            }
            QPushButton:hover { background: #E7EFFC; color: #2D6CF6; }
        """)
        more_btn.clicked.connect(
            lambda checked, fid=friend_id, fname=name:
                self._on_remark(fid, fname)
        )
        layout.addWidget(more_btn)

        self._friend_layout.addWidget(container)

    # ==================== 操作处理 ====================

    def _on_add_friend(self):
        """添加好友对话框（输入对方ID + 申请附言）"""
        dialog = _AddFriendDialog(self.state.username or "", self)
        if dialog.exec_() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                self.net.send({
                    "type": MT.FRIEND_ADD,
                    "target_id": result["target_id"],
                    "message": result["message"],
                })

    def _on_friend_add(self, msg):
        """添加好友结果"""
        if msg.get("ok"):
            QMessageBox.information(self, "成功", "好友申请已发送，等待对方同意")
        else:
            QMessageBox.warning(self, "失败", msg.get("reason", "添加失败"))

    def _on_friend_req_notify(self, msg):
        """收到好友申请通知，刷新申请列表"""
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_friend_agree_resp(self, msg):
        """好友申请被同意 — 自动发送问候消息"""
        friend_id = msg.get("friend_id")

        if msg.get("accepted"):
            # 申请方：先发送申请附言，再弹提示（避免 QMessageBox 阻塞导致消息顺序错乱）
            req_msg = msg.get("request_message", "").strip()
            if req_msg:
                encrypted = self.app.crypto.encrypt(req_msg)
                self.net.send({
                    "type": MT.CHAT, "to": friend_id,
                    "content": encrypted, "ts": int(time.time()),
                })
            QMessageBox.information(self, "成功", f"{msg.get('friend_name', '对方')} 已同意你的好友申请！")
        elif msg.get("ok") and friend_id:
            # 同意方：延迟发送问候消息（让申请方的消息先到）
            encrypted = self.app.crypto.encrypt("我们现在是好友啦")
            QTimer.singleShot(500, lambda: self.net.send({
                "type": MT.CHAT, "to": friend_id,
                "content": encrypted, "ts": int(time.time()),
            }))

        self.net.send({"type": MT.FRIEND_LIST})

    def _on_friend_req_list(self, msg):
        """收到申请列表（含待处理和已拒绝）"""
        requests = msg.get("requests", [])
        self._pending_requests = [r for r in requests if r.get("status") == 0]
        self._rejected_requests = [r for r in requests if r.get("status") == 2]
        self._refresh_friend_list()

    def _on_friend_rejected(self, msg):
        """对方拒绝了你的好友申请"""
        from_name = msg.get("from_name", "对方")
        reason = msg.get("reason", "未说明理由")
        QMessageBox.information(self, "好友申请被拒绝",
                                f"{from_name} 拒绝了你的好友申请\n理由：{reason}")
        # 刷新申请列表（服务端已记录拒绝）
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_create_group(self):
        """发起群聊（只有一人时自动进入私聊）"""
        if not self._friends:
            QMessageBox.information(self, "提示", "没有好友可邀请")
            return

        dialog = CreateGroupDialog(self._friends, self)
        if dialog.exec_() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                invitees = result.get("invitees", [])

                # 只选了一个人 → 自动进入私聊
                if len(invitees) == 1:
                    friend_id = invitees[0]
                    friend_name = str(friend_id)
                    for f in self._friends:
                        if f["user_id"] == friend_id:
                            friend_name = f.get("remark") or f.get("username", str(friend_id))
                            break
                    self._switch_to_chat(friend_id, friend_name)
                    return

                # 多人则正常创建群聊
                self.net.send({"type": MT.GROUP_CREATE, **result})

    def _on_group_create_resp(self, msg):
        """创建群聊结果 — 成功后自动跳转到群聊窗口"""
        if msg.get("ok"):
            # 切换到聊天面板并选中新群聊
            self.app.main.switch_panel("chat")
            chat_panel = self.app.panels.get("chat")
            if chat_panel:
                chat_panel._on_contact_selected(
                    {"id": msg["group_id"], "name": msg["group_name"], "type": "room"}
                )
            # 刷新群聊列表使左侧显示新群
            self.net.send({"type": MT.GROUP_LIST})
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "失败", msg.get("message", "创建群聊失败"))

    def _on_group_invited(self, msg):
        """被邀请加入群聊 — 刷新群聊列表使新群聊显示在对话列表中"""
        # 先将群名写入本地缓存，避免服务端响应前显示为"加载中…"
        group_id = msg.get("group_id", "")
        group_name = msg.get("group_name", "")
        if group_id and group_name:
            chat_panel = self.app.panels.get("chat")
            if chat_panel:
                exists = any(g["group_id"] == group_id for g in chat_panel._my_groups)
                if not exists:
                    chat_panel._my_groups.append({
                        "group_id": group_id,
                        "group_name": group_name,
                    })
                chat_panel._refresh_conv_list()
        self.net.send({"type": MT.GROUP_LIST})

    def _on_remark(self, friend_id, current_name):
        """设置备注对话框"""
        remark, ok = QInputDialog.getText(self, "设置备注", f"为 {current_name} 设置备注：")
        if ok:
            self.net.send({"type": MT.FRIEND_REMARK, "friend_id": friend_id, "remark": remark.strip()})

    def _on_reject_friend(self, from_id):
        """拒绝好友申请，弹出对话框输入理由"""
        reason, ok = QInputDialog.getText(self, "拒绝好友申请", "请输入拒绝理由（可选）：")
        if ok:
            self.net.send({
                "type": MT.FRIEND_REJECT,
                "from_id": from_id,
                "reason": reason.strip(),
            })

    def _switch_to_chat(self, friend_id, friend_name):
        """切换到与该好友的聊天"""
        self.app.main.switch_panel("chat")
        # 在聊天面板中选中该好友
        chat_panel = self.app.panels.get("chat")
        if chat_panel:
            chat_panel._on_contact_selected(
                {"id": friend_id, "name": friend_name, "type": "p2p"}
            )

    def _on_friend_list(self, msg):
        """收到好友列表"""
        self._friends = msg.get("friends", [])
        self._count_badge.setText(f"{len(self._friends)} 位")
        self.state.friends = self._friends
        self._refresh_friend_list()
        # 同时也请求待处理申请列表
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_user_list(self, msg):
        """在线列表更新时刷新"""
        self.state.online_users = msg.get("online_users", [])
        self._refresh_friend_list()


class _AddFriendDialog(QDialog):
    """添加好友对话框（输入对方ID + 申请附言）"""

    def __init__(self, my_username, parent=None):
        super().__init__(parent)
        self._result = None
        self.setWindowTitle("添加好友")
        self.setFixedSize(400, 280)
        self.setStyleSheet("""
            QDialog { background-color: #F7F9FD; border-radius: 16px; }
        """)
        self._build_ui(my_username)

    def get_result(self):
        return self._result

    def _build_ui(self, my_username):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("添加好友")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: #1E293B;")
        layout.addWidget(title)

        # 对方ID
        id_label = QLabel("对方用户 ID")
        id_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        layout.addWidget(id_label)

        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("请输入对方用户ID")
        self._id_input.setFixedHeight(48)
        self._id_input.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: 2px solid #E5EAF3;
                border-radius: 12px; font-size: 16px; color: #1E293B;
                padding: 0 16px;
            }
            QLineEdit:focus { border: 2px solid #4F8DFD; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        layout.addWidget(self._id_input)

        # 申请消息
        msg_label = QLabel("申请附言")
        msg_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #475569;")
        layout.addWidget(msg_label)

        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("我是" + (my_username or "XXX"))
        self._msg_input.setText(f"我是{my_username}")
        self._msg_input.selectAll()
        self._msg_input.setFixedHeight(48)
        self._msg_input.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: 2px solid #E5EAF3;
                border-radius: 12px; font-size: 16px; color: #1E293B;
                padding: 0 16px;
            }
            QLineEdit:focus { border: 2px solid #4F8DFD; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        layout.addWidget(self._msg_input)

        # 按钮
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

        send_btn = QPushButton("发送申请")
        send_btn.setFixedHeight(48)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
                font-size: 16px; font-weight: 700;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)
        send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(send_btn)

        layout.addLayout(btn_row)

    def _on_send(self):
        target_id = self._id_input.text().strip()
        if not target_id:
            QMessageBox.warning(self, "提示", "请输入对方用户ID")
            return
        message = self._msg_input.text().strip()
        self._result = {"target_id": target_id, "message": message}
        self.accept()
