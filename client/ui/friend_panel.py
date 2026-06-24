"""好友面板（客户端）

支持好友列表展示、添加好友、设置备注功能。
UI 对齐设计稿：左侧好友列表卡片 + 右侧添加好友/好友申请面板。

author: 董钧豪
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget,
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
        self._accepted_requests = []  # 已接受的申请记录
        self._searched_user = None  # 搜索到的用户信息
        self._search_text = ""  # 搜索框文字
        super().__init__(parent, app)

    def subscribe(self):
        """订阅好友相关消息"""
        self.net.on(MT.FRIEND_LIST_RESP, self._on_friend_list)
        self.net.on(MT.FRIEND_ADD_RESP, self._on_friend_add)
        self.net.on(MT.FRIEND_REQ_NOTIFY, self._on_friend_req_notify)
        self.net.on(MT.FRIEND_AGREE_RESP, self._on_friend_agree_resp)
        self.net.on(MT.FRIEND_REJECTED, self._on_friend_rejected)
        self.net.on(MT.FRIEND_REQ_LIST_RESP, self._on_friend_req_list)
        self.net.on(MT.USER_SEARCH_RESP, self._on_user_search_resp)
        self.net.on(MT.GROUP_CREATE_RESP, self._on_group_create_resp)
        self.net.on(MT.GROUP_INVITE, self._on_group_invited)
        self.net.on(MT.USER_LIST, self._on_user_list)
        self.net.on(MT.FRIEND_REMOVE_RESP, self._on_friend_remove_resp)
        self._build_ui()

    def showEvent(self, event):
        """面板显示时请求初始数据"""
        super().showEvent(event)
        if self.state.user_id is not None and not self._friends:
            self.net.send({"type": MT.FRIEND_LIST})

    # ==================== 整体UI构建 ====================

    def _build_ui(self):
        """构建好友面板UI（左侧列表 + 右侧面板）"""
        self.setStyleSheet("background-color: #EEF2FA;")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 左侧：好友列表 ==========
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #F7F9FD;")

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._build_header()
        left_layout.addWidget(self._header)

        self._build_filter_bar()
        left_layout.addWidget(self._filter_bar)

        # 好友列表（滚动）
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
        left_layout.addWidget(scroll, 1)

        main_layout.addWidget(left_panel, 1)

        # ========== 分割线 ==========
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background-color: #E5EAF3;")
        main_layout.addWidget(divider)

        # ========== 右侧面板（440px） ==========
        self._build_right_panel()
        main_layout.addWidget(self._right_panel)

        # 网络连接后加载好友列表（初始化时网络尚未就绪）
        if self.state.user_id is not None:
            self.net.send({"type": MT.FRIEND_LIST})

    # ==================== 左侧：标题栏 ====================

    def _build_header(self):
        """构建标题栏：好友列表 + 人数角标 + 添加好友/发起群聊按钮"""
        self._header = QFrame()
        self._header.setFixedHeight(60)
        self._header.setStyleSheet("background-color: #fff; border-bottom: 1px solid #EEF1F7;")

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(24, 0, 24, 0)

        title = QLabel("好友列表")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B;")
        hl.addWidget(title)

        self._count_badge = QLabel("0 位")
        self._count_badge.setStyleSheet("""
            font-size: 24px; font-weight: 700; color: #2D6CF6;
            background: #E7EFFC; padding: 3px 11px; border-radius: 10px;
        """)
        hl.addWidget(self._count_badge)

        hl.addStretch()

        # 发起群聊按钮
        group_btn = QPushButton("＋ 发起群聊")
        group_btn.setFixedHeight(40)
        group_btn.setCursor(Qt.PointingHandCursor)
        group_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; color: #2D6CF6;
                border: none; border-radius: 13px;
                font-size: 24px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover {
                background: #D1E3FA; font-size: 24px; padding: 0 22px;
            }
        """)
        group_btn.clicked.connect(self._on_create_group)
        hl.addWidget(group_btn)

        # 添加好友按钮（蓝渐变）
        add_btn = QPushButton("＋ 添加好友")
        add_btn.setFixedHeight(40)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 13px;
                font-size: 24px; font-weight: 700; padding: 0 18px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
                font-size: 24px; padding: 0 22px;
            }
        """)
        add_btn.clicked.connect(self._on_add_friend)
        hl.addWidget(add_btn)

    # ==================== 左侧：筛选栏 ====================

    def _build_filter_bar(self):
        """构建筛选栏：搜索框 + 药丸式筛选按钮"""
        self._filter_bar = QFrame()
        self._filter_bar.setStyleSheet("background-color: #F7F9FD;")
        self._filter_bar.setFixedHeight(70)

        fl = QHBoxLayout(self._filter_bar)
        fl.setContentsMargins(26, 14, 26, 14)
        fl.setSpacing(10)

        # 搜索框
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索好友")
        self._search_box.setFixedHeight(44)
        self._search_box.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: none; border-radius: 14px;
                font-size: 24px; color: #1E293B; padding: 0 16px;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        self._search_box.textChanged.connect(self._on_search_text_changed)
        fl.addWidget(self._search_box)

        # 筛选按钮（药丸式）
        self._filter_btns = {}
        for key, label in [("all", "全部"), ("online", "在线"), ("offline", "离线")]:
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            self._filter_btns[key] = btn
            fl.addWidget(btn)

        # 好友申请按钮（带角标）
        self._req_filter_btn = QPushButton("好友申请")
        self._req_filter_btn.setFixedHeight(40)
        self._req_filter_btn.setCursor(Qt.PointingHandCursor)
        self._req_filter_btn.setStyleSheet("""
            QPushButton {
                background: #fff; color: #94A3B8; border: none;
                border-radius: 13px; font-size: 24px; padding: 0 16px;
            }
            QPushButton:hover { background: #F7F9FD; color: #64748B; font-size: 24px; padding: 0 20px; }
        """)
        self._req_filter_btn.clicked.connect(self._focus_requests)
        fl.addWidget(self._req_filter_btn)

        self._update_filter_style()

    def _update_filter_style(self):
        """更新筛选按钮样式"""
        for key, btn in self._filter_btns.items():
            if key == self._filter:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #E7EFFC; color: #2D6CF6;
                        border: none; border-radius: 13px;
                        font-size: 24px; font-weight: 700; padding: 0 18px;
                    }
                    QPushButton:hover {
                        background: #D1E3FA; font-size: 24px; padding: 0 22px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #fff; color: #94A3B8;
                        border: none; border-radius: 13px;
                        font-size: 24px; padding: 0 18px;
                    }
                    QPushButton:hover {
                        background: #F7F9FD; color: #64748B;
                        font-size: 24px; padding: 0 22px;
                    }
                """)

    def _set_filter(self, key):
        """设置筛选条件"""
        self._filter = key
        self._update_filter_style()
        self._refresh_friend_list()

    def _on_search_text_changed(self, text):
        """搜索文字变化时过滤好友列表"""
        self._search_text = text.strip().lower()
        self._refresh_friend_list()

    def matches_search(self, name):
        """判断名称是否匹配搜索"""
        if not self._search_text:
            return True
        return self._search_text in name.lower()

    def _focus_requests(self):
        """聚焦到右侧好友申请区域"""
        # 刷新申请列表确保数据最新
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_friend_remove_resp(self, msg):
        """删除好友后刷新列表"""
        if msg.get("ok"):
            self.net.send({"type": MT.FRIEND_LIST})
            self.net.send({"type": MT.FRIEND_REQ_LIST})

    # ==================== 左侧：好友列表渲染 ====================

    def _refresh_friend_list(self):
        """刷新好友列表"""
        while self._friend_layout.count():
            child = self._friend_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        online_ids = {u["user_id"] for u in self.state.online_users}

        # 按筛选条件过滤好友
        filtered = self._friends
        if self._filter == "online":
            filtered = [f for f in self._friends if f.get("user_id") in online_ids]
        elif self._filter == "offline":
            filtered = [f for f in self._friends if f.get("user_id") not in online_ids]
        # 搜索过滤
        if self._search_text:
            filtered = [f for f in filtered if self.matches_search(
                f.get("remark") or f.get("username", ""))]
            # 同时搜索也匹配待处理申请
            self._pending_requests = [r for r in self._pending_requests
                                      if self.matches_search(
                r.get("nickname") or r.get("username", ""))]

        if filtered:
            # 分组：在线 / 离线
            online_friends = [f for f in filtered if f.get("user_id") in online_ids]
            offline_friends = [f for f in filtered if f.get("user_id") not in online_ids]

            if online_friends:
                self._add_section_label(f"在线 · {len(online_friends)} 人")
                for i, f in enumerate(online_friends):
                    color = _AVATAR_COLORS[i % len(_AVATAR_COLORS)]
                    self._add_friend_card(f, is_online=True, color=color)

            if offline_friends:
                self._add_section_label(f"离线 · {len(offline_friends)} 人")
                for i, f in enumerate(offline_friends):
                    color = _AVATAR_COLORS[(i + len(online_friends)) % len(_AVATAR_COLORS)]
                    self._add_friend_card(f, is_online=False, color=color)
        else:
            empty = QLabel("暂无好友")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("font-size: 24px; color: #94A3B8; padding: 60px 0; background: transparent;")
            self._friend_layout.addWidget(empty)

        self._friend_layout.addStretch()

    def _add_section_label(self, text):
        """添加分组标题（带分隔线）"""
        container = QFrame()
        container.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 10, 4, 6)

        label = QLabel(text)
        label.setStyleSheet("""
            font-size: 24px; font-weight: 700; color: #94A3B8;
            letter-spacing: 1px; background: transparent;
        """)
        layout.addWidget(label)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #E5EAF3;")
        layout.addWidget(line, 1)

        self._friend_layout.addWidget(container)

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

    def _add_friend_card(self, friend, is_online, color):
        """添加好友卡片，点击 ⋯ 内联展开备注编辑"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #fff; border-radius: 18px;
            }
            QFrame:hover { background-color: #F7F9FD; }
        """)

        # 外层垂直布局：卡片内容 + 可展开编辑区
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ====== 卡片主体 ======
        card_body = QWidget()
        card_body.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(card_body)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # 圆形头像（带在线状态点）
        avatar_container = QWidget()
        avatar_container.setFixedSize(54, 54)
        avatar_container.setStyleSheet("background: transparent;")

        name = friend.get("remark") or friend.get("username", "?")
        avatar_text = name[0] if name else "?"
        avatar = self._create_avatar(54, avatar_text, color)
        avatar.setParent(avatar_container)

        # 在线状态点（右下角）
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

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 24px; font-weight: 700; color: #1E293B; background: transparent;")
        name_row.addWidget(name_label)

        class_name = friend.get("class_name", "")
        if class_name:
            class_label = QLabel(class_name)
            class_label.setStyleSheet("font-size: 24px; color: #94A3B8; background: transparent;")
            name_row.addWidget(class_label)

        name_row.addStretch()
        text_col.addLayout(name_row)

        status_text = "在线" if is_online else "离线"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            f"font-size: 24px; font-weight: 500; color: {'#34D399' if is_online else '#CBD5E1'}; background: transparent;")
        text_col.addWidget(status_label)

        layout.addLayout(text_col, 1)

        # 操作按钮
        if is_online:
            btn_bg = "#E7EFFC"
            btn_color = "#2D6CF6"
        else:
            btn_bg = "#F1F5F9"
            btn_color = "#94A3B8"

        # 发消息按钮
        msg_btn = QPushButton("💬")
        msg_btn.setFixedSize(40, 40)
        msg_btn.setCursor(Qt.PointingHandCursor)
        msg_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_bg}; color: {btn_color};
                border: none; border-radius: 13px; font-size: 24px;
            }}
            QPushButton:hover {{ background: #D1E3FA; color: #2D6CF6; }}
        """)
        friend_id = friend.get("user_id")
        friend_name = friend.get("username", "")
        msg_btn.clicked.connect(
            lambda checked, fid=friend_id, fname=friend_name:
                self._switch_to_chat(fid, fname)
        )

        if not is_online:
            msg_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {btn_bg}; color: {btn_color};
                    border: none; border-radius: 13px; font-size: 24px;
                }}
            """)

        layout.addWidget(msg_btn)

        # 更多按钮
        more_btn = QPushButton("⋯")
        more_btn.setFixedSize(40, 40)
        more_btn.setCursor(Qt.PointingHandCursor)
        more_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #94A3B8;
                border: none; border-radius: 13px; font-size: 24px;
            }
            QPushButton:hover { background: #E7EFFC; color: #2D6CF6; }
        """)
        layout.addWidget(more_btn)

        outer_layout.addWidget(card_body)

        # ====== 内联备注编辑区（默认隐藏）======
        edit_section = QFrame()
        edit_section.setStyleSheet("background: transparent;")
        edit_section.hide()

        edit_layout = QVBoxLayout(edit_section)
        edit_layout.setContentsMargins(20, 8, 20, 16)
        edit_layout.setSpacing(10)

        # 备注输入框
        remark_input = QLineEdit()
        remark_input.setPlaceholderText("输入备注名称")
        remark_input.setText(friend.get("remark", ""))
        remark_input.setFixedHeight(48)
        remark_input.setStyleSheet("""
            QLineEdit {
                background-color: #F5F8FF; border: 1.5px solid #2D6CF6;
                border-radius: 12px; font-size: 24px; color: #1E293B;
                padding: 0 14px;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(42)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #2D6CF6; color: white; border: none;
                border-radius: 10px; font-size: 24px; font-weight: 700;
                padding: 0 22px;
            }
            QPushButton:hover { background: #1D5CE6; }
        """)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(42)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #94A3B8; border: none;
                border-radius: 10px; font-size: 24px; font-weight: 600;
                padding: 0 22px;
            }
            QPushButton:hover { background: #E2E8F0; color: #64748B; }
        """)

        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)

        edit_layout.addWidget(remark_input)
        edit_layout.addLayout(btn_row)

        outer_layout.addWidget(edit_section)

        # ====== 信号连接 ======
        more_btn.clicked.connect(lambda checked, es=edit_section, inp=remark_input: (
            (es.show(), inp.setFocus(), inp.selectAll())
            if es.isHidden()
            else es.hide()
        ))

        # 保存备注
        save_btn.clicked.connect(lambda checked, fid=friend_id, inp=remark_input, es=edit_section: (
            self.net.send({"type": MT.FRIEND_REMARK, "friend_id": fid, "remark": inp.text().strip()}),
            self.net.send({"type": MT.FRIEND_LIST}),
            es.hide(),
        ))

        # 取消 — 恢复原值并收起
        cancel_btn.clicked.connect(
            lambda checked, es=edit_section, inp=remark_input, orig=friend.get("remark", ""): (
                inp.setText(orig),
                es.hide(),
            )
        )

        self._friend_layout.addWidget(container)

    # ==================== 右侧面板 ====================

    def _build_right_panel(self):
        """构建右侧面板：添加好友 + 好友申请"""
        self._right_panel = QFrame()
        self._right_panel.setFixedWidth(520)
        self._right_panel.setStyleSheet("background-color: #EEF2FA;")

        layout = QVBoxLayout(self._right_panel)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # ===== 添加好友卡片 =====
        self._build_add_friend_card()
        layout.addWidget(self._add_friend_widget)

        # ===== 好友申请卡片 =====
        self._build_requests_card()
        layout.addWidget(self._requests_card, 1)

    def _build_add_friend_card(self):
        """构建添加好友卡片"""
        self._add_friend_widget = QFrame()
        self._add_friend_widget.setStyleSheet("""
            QFrame {
                background-color: #fff; border-radius: 20px;
            }
        """)

        layout = QVBoxLayout(self._add_friend_widget)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(0)

        # 标题
        title = QLabel("添加好友")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #1E293B; background: transparent;")
        layout.addWidget(title)

        desc = QLabel("输入对方用户名，发送好友申请")
        desc.setStyleSheet("font-size: 24px; color: #94A3B8; background: transparent;")
        layout.addSpacing(5)
        layout.addWidget(desc)

        # 搜索输入行
        layout.addSpacing(24)
        search_row = QFrame()
        search_row.setStyleSheet("""
            QFrame {
                background-color: #F5F8FF; border: 1.5px solid #2D6CF6;
                border-radius: 15px;
            }
        """)
        sr = QHBoxLayout(search_row)
        sr.setContentsMargins(16, 0, 16, 0)
        sr.setSpacing(11)

        self._add_search_input = QLineEdit()
        self._add_search_input.setPlaceholderText("输入用户ID搜索")
        self._add_search_input.setFixedHeight(56)
        self._add_search_input.setStyleSheet("""
            QLineEdit {
                background: transparent; border: none;
                font-size: 26px; color: #1E293B; font-weight: 500;
            }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        sr.addWidget(self._add_search_input, 1)

        search_btn = QPushButton("搜索")
        search_btn.setFixedHeight(42)
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setStyleSheet("""
            QPushButton {
                background: #E7EFFC; color: #2D6CF6;
                border: none; border-radius: 10px;
                font-size: 24px; font-weight: 600; padding: 0 18px;
            }
            QPushButton:hover {
                background: #D1E3FA; font-size: 24px; padding: 0 18px;
            }
        """)
        search_btn.clicked.connect(self._on_search_user)
        sr.addWidget(search_btn)

        layout.addWidget(search_row)

        # 搜索结果区域（默认隐藏）
        self._search_result = QFrame()
        self._search_result.setStyleSheet("""
            QFrame {
                background-color: #F7F9FD; border-radius: 16px;
            }
        """)
        self._search_result.setFixedHeight(84)
        self._search_result.hide()

        result_layout = QHBoxLayout(self._search_result)
        result_layout.setContentsMargins(18, 16, 18, 16)
        result_layout.setSpacing(14)

        self._result_avatar = self._create_avatar(52, "?", "#0EA5E9")
        result_layout.addWidget(self._result_avatar)

        result_text = QVBoxLayout()
        result_text.setSpacing(3)

        self._result_name = QLabel("")
        self._result_name.setStyleSheet("font-size: 24px; font-weight: 700; color: #1E293B; background: transparent;")
        result_text.addWidget(self._result_name)

        self._result_info = QLabel("")
        self._result_info.setStyleSheet("font-size: 24px; color: #94A3B8; background: transparent;")
        result_text.addWidget(self._result_info)

        result_layout.addLayout(result_text, 1)

        self._apply_btn = QPushButton("申请")
        self._apply_btn.setFixedHeight(48)
        self._apply_btn.setCursor(Qt.PointingHandCursor)
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 13px;
                font-size: 26px; font-weight: 700; padding: 0 24px;
            }
            QPushButton:hover {
                background: #1D5CE6; font-size: 24px; padding: 0 26px;
            }
        """)
        self._apply_btn.clicked.connect(self._on_apply_friend)
        result_layout.addWidget(self._apply_btn)

        layout.addSpacing(24)
        layout.addWidget(self._search_result)

        # 验证消息输入（默认隐藏）
        self._verify_row = QFrame()
        self._verify_row.hide()
        vr = QVBoxLayout(self._verify_row)
        vr.setContentsMargins(0, 0, 0, 0)
        vr.setSpacing(8)

        verify_label = QLabel("验证消息")
        verify_label.setStyleSheet("""
            font-size: 24px; font-weight: 600; color: #475569; background: transparent;
        """)
        vr.addWidget(verify_label)

        self._verify_input = QLineEdit()
        self._verify_input.setPlaceholderText(f"我是{self.state.username or 'XXX'}")
        self._verify_input.setText(f"我是{self.state.username or 'XXX'}")
        self._verify_input.selectAll()
        self._verify_input.setFixedHeight(52)
        self._verify_input.setStyleSheet("""
            QLineEdit {
                background-color: #FAFBFD; border: 1.5px solid #E2E8F2;
                border-radius: 13px; font-size: 26px; color: #64748B;
                padding: 0 16px;
            }
            QLineEdit:focus { border: 1.5px solid #4F8DFD; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)
        vr.addWidget(self._verify_input)

        layout.addSpacing(20)
        layout.addWidget(self._verify_row)

        # 内联结果提示（默认隐藏）
        self._add_result_label = QLabel("")
        self._add_result_label.setAlignment(Qt.AlignCenter)
        self._add_result_label.setStyleSheet("""
            font-size: 24px; font-weight: 600; padding: 10px 0;
            background: transparent;
        """)
        self._add_result_label.hide()
        layout.addWidget(self._add_result_label)

        # 定时器隐藏结果提示
        self._result_timer = QTimer(self)
        self._result_timer.setSingleShot(True)
        self._result_timer.timeout.connect(self._add_result_label.hide)

    def _build_requests_card(self):
        """构建好友申请卡片（带滚动区域，可填满剩余空间）"""
        self._requests_card = QFrame()
        self._requests_card.setStyleSheet("""
            QFrame {
                background-color: #fff; border-radius: 20px;
            }
        """)

        card_layout = QVBoxLayout(self._requests_card)
        card_layout.setContentsMargins(26, 26, 26, 26)
        card_layout.setSpacing(0)

        # 标题 + 角标
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        title = QLabel("好友申请")
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #1E293B; background: transparent;")
        title_row.addWidget(title)

        self._req_count_badge = QLabel("0")
        self._req_count_badge.setStyleSheet("""
            font-size: 24px; font-weight: 700; color: #fff;
            background: #FB7185; padding: 3px 11px; border-radius: 10px;
        """)
        self._req_count_badge.hide()
        title_row.addWidget(self._req_count_badge)

        title_row.addStretch()
        card_layout.addLayout(title_row)

        card_layout.addSpacing(20)

        # 可滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: rgba(100,116,139,0.22); border-radius: 6px; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._requests_layout = QVBoxLayout(scroll_content)
        self._requests_layout.setContentsMargins(0, 0, 0, 0)
        self._requests_layout.setSpacing(12)
        self._requests_layout.setAlignment(Qt.AlignTop)

        self._no_requests_label = QLabel("暂无好友申请")
        self._no_requests_label.setStyleSheet("""
            font-size: 24px; color: #CBD5E1; background: transparent;
            padding: 16px 0;
        """)
        self._no_requests_label.setAlignment(Qt.AlignCenter)
        self._requests_layout.addWidget(self._no_requests_label)

        scroll.setWidget(scroll_content)
        card_layout.addWidget(scroll, 1)

    # ==================== 右侧面板：交互 ====================

    def _on_search_user(self):
        """搜索用户（按ID搜索，结果显示在右侧面板）"""
        target_id = self._add_search_input.text().strip()
        if not target_id:
            self._show_add_result("请输入用户ID", success=False)
            return
        # 重置之前的搜索结果
        self._searched_user = None
        self._search_result.hide()
        self._verify_row.hide()
        self._add_result_label.hide()
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("申请")
        self.net.send({"type": MT.USER_SEARCH, "target_id": target_id})

    def _on_apply_friend(self):
        """从右侧面板直接发送好友申请（不弹窗）"""
        if not self._searched_user:
            return
        self.net.send({
            "type": MT.FRIEND_ADD,
            "target_id": str(self._searched_user["user_id"]),
            "message": self._verify_input.text().strip(),
        })

    def _on_user_search_resp(self, msg):
        """处理用户搜索结果，直接显示在右侧面板"""
        if not msg.get("ok"):
            self._search_result.hide()
            self._verify_row.hide()
            self._show_add_result(f"❌ {msg.get('reason', '搜索失败')}", success=False)
            return

        user = msg["user"]
        self._searched_user = user

        # 更新搜索结果展示
        name = user.get("nickname") or user.get("username", "")
        avatar_text = name[0] if name else "?"
        self._result_avatar.setText(avatar_text)
        # 用搜索到的用户名确定头像颜色
        color_idx = hash(user["username"]) % len(_AVATAR_COLORS)
        self._result_avatar.setStyleSheet(self._result_avatar.styleSheet().replace(
            "background-color: #0EA5E9",
            f"background-color: {_AVATAR_COLORS[color_idx]}"
        ))

        self._result_name.setText(name)

        if user.get("is_friend"):
            self._result_info.setText("已是好友")
            self._apply_btn.setEnabled(False)
            self._apply_btn.setText("已是好友")
            self._verify_row.hide()
        else:
            self._result_info.setText(f"用户ID: {user['user_id']}")
            self._apply_btn.setEnabled(True)
            self._apply_btn.setText("申请")
            # 显示验证消息输入
            self._verify_input.setText(f"我是{self.state.username or 'XXX'}")
            self._verify_input.selectAll()
            self._verify_row.show()

        self._search_result.show()
        self._add_result_label.hide()

    def _switch_to_right_panel(self):
        """切换到右侧面板的指定区域"""
        pass

    def _refresh_requests(self):
        """刷新好友申请列表"""
        # 清空申请列表
        while self._requests_layout.count():
            item = self._requests_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_items = []

        # 待处理申请
        for req in self._pending_requests:
            all_items.append(("pending", req))

        # 已拒绝的申请
        for req in self._rejected_requests:
            all_items.append(("rejected", req))

        # 已接受的申请
        for req in self._accepted_requests:
            all_items.append(("accepted", req))

        if not all_items:
            self._no_requests_label = QLabel("暂无好友申请")
            self._no_requests_label.setStyleSheet("""
                font-size: 24px; color: #CBD5E1; background: transparent;
                padding: 16px 0;
            """)
            self._no_requests_label.setAlignment(Qt.AlignCenter)
            self._requests_layout.addWidget(self._no_requests_label)
            self._req_count_badge.hide()
            return

        # 更新角标
        pending_count = len(self._pending_requests)
        if pending_count > 0:
            self._req_count_badge.setText(str(pending_count))
            self._req_count_badge.show()
        else:
            self._req_count_badge.hide()

        # 也更新筛选栏的好友申请角标
        self._update_req_filter_badge()

        for status, req in all_items:
            if status == "pending":
                self._add_pending_request_card(req)
            elif status == "rejected":
                self._add_accepted_or_rejected_entry(req, is_accepted=False)
            else:
                self._add_accepted_or_rejected_entry(req, is_accepted=True)

    def _update_req_filter_badge(self):
        """更新筛选栏的好友申请按钮角标"""
        pass

    def _add_pending_request_card(self, req):
        """添加待处理的好友申请卡片，支持内联拒绝理由"""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #F7F9FD; border-radius: 16px;
            }
        """)

        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ====== 主内容 ======
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # 申请人信息行
        info_row = QHBoxLayout()
        info_row.setSpacing(14)

        name = req.get("nickname") or req.get("username", "未知")
        from_id = req.get("from_id")

        avatar = self._create_avatar(52, name[0] if name else "?", "#A78BFA")
        info_row.addWidget(avatar)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 24px; font-weight: 700; color: #1E293B; background: transparent;")
        text_col.addWidget(name_label)

        time_label = QLabel("刚刚")
        time_label.setStyleSheet("font-size: 24px; color: #94A3B8; background: transparent;")
        text_col.addWidget(time_label)

        info_row.addLayout(text_col, 1)
        layout.addLayout(info_row)

        # 申请消息
        req_msg = req.get("message", "")
        if req_msg:
            msg_label = QLabel(req_msg)
            msg_label.setWordWrap(True)
            msg_label.setStyleSheet("""
                font-size: 24px; color: #475569;
                background: #fff; padding: 11px 14px;
                border: 1px solid #EEF1F7; border-radius: 11px;
            """)
            layout.addWidget(msg_label)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        accept_btn = QPushButton("接受")
        accept_btn.setFixedHeight(50)
        accept_btn.setCursor(Qt.PointingHandCursor)
        accept_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white; border: none; border-radius: 14px;
                font-size: 26px; font-weight: 700;
            }
            QPushButton:hover {
                background: #1D5CE6; font-size: 26px;
            }
        """)
        accept_btn.clicked.connect(
            lambda checked, fid=from_id: self.net.send(
                {"type": MT.FRIEND_AGREE, "from_id": fid}
            )
        )
        btn_row.addWidget(accept_btn)

        reject_btn = QPushButton("拒绝")
        reject_btn.setFixedHeight(50)
        reject_btn.setCursor(Qt.PointingHandCursor)
        reject_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #94A3B8;
                border: none; border-radius: 14px;
                font-size: 26px; font-weight: 600; padding: 0 30px;
            }
            QPushButton:hover {
                background: #E2E8F0; color: #64748B;
                font-size: 26px; padding: 0 34px;
            }
        """)
        btn_row.addWidget(reject_btn)

        layout.addLayout(btn_row)
        outer_layout.addWidget(body)

        # ====== 内联拒绝理由编辑区（默认隐藏）======
        reject_section = QFrame()
        reject_section.setStyleSheet("background: transparent;")
        reject_section.hide()

        reject_edit_layout = QVBoxLayout(reject_section)
        reject_edit_layout.setContentsMargins(18, 0, 18, 16)
        reject_edit_layout.setSpacing(10)

        # 理由输入框
        reason_input = QLineEdit()
        reason_input.setPlaceholderText("输入回复/拒绝理由（可选）")
        reason_input.setFixedHeight(48)
        reason_input.setStyleSheet("""
            QLineEdit {
                background-color: #fff; border: 1.5px solid #E2E8F2;
                border-radius: 12px; font-size: 24px; color: #1E293B;
                padding: 0 14px;
            }
            QLineEdit:focus { border: 1.5px solid #FB7185; }
            QLineEdit::placeholder { color: #B0BAC8; }
        """)

        # 按钮行
        reject_btn_row = QHBoxLayout()
        reject_btn_row.setSpacing(10)

        confirm_reject_btn = QPushButton("确认拒绝")
        confirm_reject_btn.setFixedHeight(42)
        confirm_reject_btn.setCursor(Qt.PointingHandCursor)
        confirm_reject_btn.setStyleSheet("""
            QPushButton {
                background: #FB7185; color: white; border: none;
                border-radius: 10px; font-size: 24px; font-weight: 700;
                padding: 0 20px;
            }
            QPushButton:hover { background: #F43F5E; }
        """)

        cancel_reject_btn = QPushButton("取消")
        cancel_reject_btn.setFixedHeight(42)
        cancel_reject_btn.setCursor(Qt.PointingHandCursor)
        cancel_reject_btn.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #94A3B8; border: none;
                border-radius: 10px; font-size: 24px; font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover { background: #E2E8F0; color: #64748B; }
        """)

        reject_btn_row.addStretch()
        reject_btn_row.addWidget(confirm_reject_btn)
        reject_btn_row.addWidget(cancel_reject_btn)

        reject_edit_layout.addWidget(reason_input)
        reject_edit_layout.addLayout(reject_btn_row)

        outer_layout.addWidget(reject_section)

        # ====== 信号连接 ======
        # 拒绝按钮 → 展开理由输入
        reject_btn.clicked.connect(
            lambda checked, rs=reject_section, inp=reason_input: (
                (rs.show(), inp.setFocus())
                if rs.isHidden()
                else rs.hide()
            )
        )

        # 确认拒绝 → 发送请求并刷新列表
        confirm_reject_btn.clicked.connect(
            lambda checked, fid=from_id, inp=reason_input, rs=reject_section: (
                self.net.send({
                    "type": MT.FRIEND_REJECT,
                    "from_id": fid,
                    "reason": inp.text().strip(),
                }),
                self.net.send({"type": MT.FRIEND_REQ_LIST}),
                rs.hide(),
            )
        )

        # 取消 → 收起
        cancel_reject_btn.clicked.connect(
            lambda checked, rs=reject_section, inp=reason_input: (
                inp.clear(),
                rs.hide(),
            )
        )

        self._requests_layout.addWidget(container)

    def _add_accepted_or_rejected_entry(self, req, is_accepted):
        """添加已处理的好友申请条目"""
        container = QFrame()
        container.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(14)

        name = req.get("nickname") or req.get("username", "未知")
        avatar = self._create_avatar(48, name[0] if name else "?", "#34D399" if is_accepted else "#94A3B8")
        layout.addWidget(avatar)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #1E293B; background: transparent;")
        text_col.addWidget(name_label)

        time_label = QLabel("昨天" if is_accepted else "已拒绝")
        time_label.setStyleSheet(
            f"font-size: 24px; color: #94A3B8; background: transparent;")
        text_col.addWidget(time_label)

        layout.addLayout(text_col, 1)

        if is_accepted:
            badge = QLabel("已接受")
            badge.setStyleSheet("""
                font-size: 24px; font-weight: 600; color: #10B981;
                background: #F0FDF6; padding: 6px 14px; border-radius: 11px;
            """)
            layout.addWidget(badge)

        self._requests_layout.addWidget(container)

    # ==================== 操作处理 ====================

    def _on_add_friend(self):
        """点击添加好友按钮，聚焦右侧搜索框（不弹窗）"""
        self._add_search_input.setFocus()
        self._add_search_input.clear()
        self._search_result.hide()
        self._verify_row.hide()
        self._add_result_label.hide()
        self._searched_user = None

    def _show_add_result(self, text, success=True):
        """在右侧面板内联显示添加结果"""
        if success:
            self._add_result_label.setStyleSheet("""
                font-size: 24px; font-weight: 600; padding: 10px 0;
                color: #10B981; background: transparent;
            """)
        else:
            self._add_result_label.setStyleSheet("""
                font-size: 24px; font-weight: 600; padding: 10px 0;
                color: #EF4444; background: transparent;
            """)
        self._add_result_label.setText(text)
        self._add_result_label.show()
        # 3秒后自动隐藏
        self._result_timer.start(3000)

    def _on_friend_add(self, msg):
        """添加好友结果（内联显示，不弹窗）"""
        if msg.get("ok"):
            self._show_add_result("✅ 好友申请已发送，等待对方同意", success=True)
            self._search_result.hide()
            self._verify_row.hide()
            self._add_search_input.clear()
            self._searched_user = None
        else:
            self._show_add_result(f"❌ {msg.get('reason', '添加失败')}", success=False)

    def _on_friend_req_notify(self, msg):
        """收到好友申请通知，刷新申请列表"""
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_friend_agree_resp(self, msg):
        """好友申请被同意 — 自动发送问候消息"""
        friend_id = msg.get("friend_id")

        if msg.get("accepted"):
            # 申请方：先发送申请附言，再弹提示
            req_msg = msg.get("request_message", "").strip()
            if req_msg:
                encrypted = self.app.crypto.encrypt(req_msg)
                self.net.send({
                    "type": MT.CHAT, "to": friend_id,
                    "content": encrypted, "ts": int(time.time()),
                })
            QMessageBox.information(self, "成功", f"{msg.get('friend_name', '对方')} 已同意你的好友申请！")
        elif msg.get("ok") and friend_id:
            # 同意方：延迟发送问候消息
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
        self._refresh_requests()

    def _on_friend_rejected(self, msg):
        """对方拒绝了你的好友申请"""
        from_name = msg.get("from_name", "对方")
        reason = msg.get("reason", "未说明理由")
        QMessageBox.information(self, "好友申请被拒绝",
                                f"{from_name} 拒绝了你的好友申请\n理由：{reason}")
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
            self.app.main.switch_panel("chat")
            chat_panel = self.app.panels.get("chat")
            if chat_panel:
                chat_panel._on_contact_selected(
                    {"id": msg["group_id"], "name": msg["group_name"], "type": "room"}
                )
            self.net.send({"type": MT.GROUP_LIST})
        else:
            QMessageBox.warning(self, "失败", msg.get("message", "创建群聊失败"))

    def _on_group_invited(self, msg):
        """被邀请加入群聊 — 刷新群聊列表"""
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

    def _switch_to_chat(self, friend_id, friend_name):
        """切换到与该好友的聊天"""
        self.app.main.switch_panel("chat")
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


