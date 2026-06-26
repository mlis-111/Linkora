"""聊天面板（客户端）

支持私聊和群聊，提供消息收发、历史记录查询功能。
消息发送前自动加密，接收后自动解密显示。
UI 对齐文件面板：大字号、舒朗间距、蓝调阴影。

author: 董钧豪
"""

import time
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QWidget,
    QGraphicsDropShadowEffect, QMenu, QDialog,
    QListWidget, QListWidgetItem, QMessageBox, QTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QBrush, QPixmap
from client.core.base_panel import BasePanel
from common.messages import MT, PUBLIC_ROOM_ID

# ── 颜色 ─────────────────────────────────────────────
C_DARK      = "#1E293B"
C_SUBTLE    = "#94A3B8"
C_MUTED     = "#6B7A90"
C_WHITE     = "#FFFFFF"
C_CARD      = "#FFFFFF"
C_BG        = "#EEF2FA"
C_SIDEBAR   = "#F7F9FD"
C_BORDER    = "#E5EAF3"
C_PRIMARY   = "#2D6CF6"
C_BLUE_BG   = "#DBEAFE"
C_BLUE_GRAD = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4F8DFD,stop:1 #2D6CF6)"
C_RED       = "#FB7185"
C_GREEN     = "#34D399"
C_OFFLINE   = "#CBD5E1"

_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]


def _apply_shadow(widget, blur=12, y=3, alpha=15):
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    s.setXOffset(0)
    s.setYOffset(y)
    s.setColor(QColor(45, 108, 246, alpha))
    widget.setGraphicsEffect(s)


class ChatPanel(BasePanel):
    """聊天面板"""

    def __init__(self, parent, app):
        self._current_target = None
        self._conv_items = {}
        self._unread = {}
        self._last_times = {}
        self._last_previews = {}
        self._my_groups = []
        self._search_text = ""
        self._history_token = 0
        self._group_members_cache = {}
        super().__init__(parent, app)

    def subscribe(self):
        self.net.on(MT.CHAT, self._on_chat)
        self.net.on(MT.ROOM_CHAT, self._on_room_chat)
        self.net.on(MT.HISTORY_RESP, self._on_history)
        self.net.on(MT.USER_LIST, self._on_user_list)
        self.net.on(MT.FRIEND_LIST_RESP, self._on_friend_list)
        self.net.on(MT.GROUP_LIST_RESP, self._on_group_list)
        self.net.on(MT.GROUP_CREATE_RESP, self._on_group_create_resp)
        self.net.on(MT.GROUP_JOIN_RESP, self._on_group_join)
        self.net.on(MT.GROUP_NAME_UPDATED, self._on_group_name_update)
        self.net.on(MT.GROUP_MEMBERS_RESP, self._on_group_members)
        self.net.on(MT.GROUP_INVITE, self._on_group_invite)
        self.net.on(MT.FRIEND_REMOVE_RESP, self._on_friend_remove_resp)
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        # 已有数据则跳过，避免每次切面板都请求+重绘导致闪烁
        if not self.state.friends and not self._my_groups:
            self._request_lists()

    def _request_lists(self):
        if self.state.user_id:
            self.net.send({"type": MT.FRIEND_LIST})
            self.net.send({"type": MT.GROUP_LIST})

    # ═══════════════════════════════════════════════════
    #  整体布局
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        self.setStyleSheet(f"background:{C_BG};")
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_left())

        d = QFrame()
        d.setFixedWidth(1)
        d.setStyleSheet(f"background:{C_BORDER};")
        main.addWidget(d)

        main.addWidget(self._build_right(), 1)

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(200, self._request_lists)

    # ═══════════════════════════════════════════════════
    #  左侧对话列表
    # ═══════════════════════════════════════════════════

    def _build_left(self):
        self._left = QFrame()
        self._left.setFixedWidth(520)
        self._left.setStyleSheet(f"background:{C_SIDEBAR};")

        lo = QVBoxLayout(self._left)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # 标题 "消息" + 创建群聊按钮
        hdr = QWidget()
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(48, 60, 28, 36)
        hl.setSpacing(16)
        t = QLabel("消息")
        t.setStyleSheet(f"font-size:45px; font-weight:900; color:{C_DARK};")
        hl.addWidget(t)
        hl.addStretch()

        create = QPushButton("＋ 创建群聊")
        create.setFixedHeight(52)
        create.setCursor(Qt.PointingHandCursor)
        create.setStyleSheet(f"""
            QPushButton {{ background:{C_BLUE_BG}; color:{C_PRIMARY};
            border:none; border-radius:14px; font-size:23px; font-weight:700;
            padding:0 18px; }}
            QPushButton:hover {{ background:#D1E3FA; }}
        """)
        create.clicked.connect(self._show_create_group_dialog)
        hl.addWidget(create)
        lo.addWidget(hdr)

        # 搜索
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索用户或消息")
        self._search.setFixedHeight(100)
        self._search.setStyleSheet(f"""
            QLineEdit {{ background:{C_WHITE}; border:none; border-radius:20px;
            font-size:24px; color:{C_DARK}; padding:0 22px;
            margin:8px 28px 24px 28px; }}
            QLineEdit::placeholder {{ color:#B0BAC8; }}
        """)
        self._search.textChanged.connect(lambda t: setattr(self, '_search_text', t.strip().lower()) or self._refresh_list())
        lo.addWidget(self._search)

        # 滚动列表
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea{border:none;background:transparent;}"
                         "QScrollBar:vertical{width:8px;background:transparent;}"
                         "QScrollBar::handle:vertical{background:rgba(100,116,139,0.22);border-radius:6px;}"
                         "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}")
        self._conv_w = QWidget()
        self._conv_l = QVBoxLayout(self._conv_w)
        self._conv_l.setContentsMargins(28, 15, 28, 24)
        self._conv_l.setSpacing(5)
        self._conv_l.setAlignment(Qt.AlignTop)
        sc.setWidget(self._conv_w)
        lo.addWidget(sc, 1)
        return self._left

    # ═══════════════════════════════════════════════════
    #  右侧聊天区
    # ═══════════════════════════════════════════════════

    def _build_right(self):
        self._right = QWidget()
        rl = QVBoxLayout(self._right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        self._chat_hdr = QWidget()
        self._chat_hdr.setFixedHeight(140)
        rl.addWidget(self._chat_hdr)
        self._chat_hdr.hide()

        self._msg_scroll = QScrollArea()
        self._msg_scroll.setWidgetResizable(True)
        self._msg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._msg_scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{C_WHITE};}}"
            "QScrollBar:vertical{width:8px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#CBD5E1;border-radius:4px;min-height:24px;}")
        self._msg_w = QWidget()
        self._msg_l = QVBoxLayout(self._msg_w)
        self._msg_l.setContentsMargins(48, 32, 48, 32)
        self._msg_l.setSpacing(24)
        self._msg_l.setAlignment(Qt.AlignTop)
        self._msg_scroll.setWidget(self._msg_w)

        # 初始欢迎界面
        self._welcome = QWidget()
        self._welcome.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(self._welcome)
        wl.setAlignment(Qt.AlignCenter)
        wl.setSpacing(32)
        # Logo
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(300, 300)
        pixmap = QPixmap("icon/logo.png").scaled(
            300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)
        p = QPainter(rounded)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(pixmap))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(pixmap.rect(), 70, 70)
        p.end()
        logo.setPixmap(rounded)
        wl.addWidget(logo, alignment=Qt.AlignCenter)
        # 欢迎文字
        title = QLabel("欢迎使用 Linkora")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size:38px; font-weight:700; color:#64748B;"
            "line-height:1.5;"
            "background:transparent; border:none;")
        wl.addWidget(title)
        subtitle = QLabel("选择一个联系人开始聊天")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            "font-size:26px; color:#94A3B8;"
            "line-height:1.5;"
            "background:transparent; border:none;")
        wl.addWidget(subtitle)
        self._msg_l.addStretch()
        self._msg_l.addWidget(self._welcome)
        self._msg_l.addStretch()

        rl.addWidget(self._msg_scroll, 1)

        rl.addWidget(self._build_composer())
        return self._right

    def _set_chat_header(self, name, sub, is_online=None):
        """持久化布局：首次构建，后续仅更新文本和显隐"""
        w = self._chat_hdr
        if not hasattr(self, '_hdr_built'):
            self._hdr_built = True
            hl = QHBoxLayout(w)
            hl.setContentsMargins(44, 28, 36, 26)
            hl.setSpacing(32)

            self._hdr_av = QLabel()
            self._hdr_av.setFixedSize(80, 80)
            self._hdr_av.setAlignment(Qt.AlignCenter)
            self._hdr_av.setStyleSheet(f"font-size:36px;font-weight:600;color:white;border-radius:40px;background:{C_BLUE_GRAD};")
            hl.addWidget(self._hdr_av)

            vi = QVBoxLayout()
            vi.setSpacing(6)
            self._hdr_name = QLabel()
            self._hdr_name.setStyleSheet(f"font-size:34px;font-weight:800;color:{C_DARK};background:transparent;")
            vi.addWidget(self._hdr_name)

            self._hdr_status = QLabel()
            self._hdr_status.setStyleSheet("font-size:24px;background:transparent;")
            vi.addWidget(self._hdr_status)

            self._hdr_sub = QLabel()
            self._hdr_sub.setStyleSheet(f"font-size:22px;color:{C_SUBTLE};background:transparent;")
            vi.addWidget(self._hdr_sub)

            hl.addLayout(vi)
            hl.addStretch()

            # 群聊设置按钮（⋯ → 展开设置面板）
            self._hdr_mb = QPushButton("⋯")
            self._hdr_mb.setFixedSize(64, 64)
            self._hdr_mb.setCursor(Qt.PointingHandCursor)
            self._hdr_mb.setStyleSheet(f"QPushButton{{background:{C_BLUE_BG};border:none;border-radius:18px;font-size:32px;}}"
                                       f"QPushButton:hover{{background:#D1E3FA;}}")
            self._hdr_mb.clicked.connect(self._show_group_settings)
            self._hdr_mb.hide()
            hl.addWidget(self._hdr_mb)

            self._hdr_more = QPushButton("⋯")
            self._hdr_more.setFixedSize(64, 64)
            self._hdr_more.setCursor(Qt.PointingHandCursor)
            self._hdr_more.setStyleSheet(f"QPushButton{{background:{C_BLUE_BG};border:none;border-radius:18px;font-size:32px;}}"
                                         f"QPushButton:hover{{background:#D1E3FA;}}")
            self._hdr_more.clicked.connect(self._show_more_menu)
            self._hdr_more.hide()
            hl.addWidget(self._hdr_more)

        # 更新文本
        self._hdr_av.setText(name[0] if name else "💬")
        self._hdr_name.setText(name if name else "")
        if is_online is True:
            self._hdr_status.setText("● 在线")
            self._hdr_status.setStyleSheet(f"font-size:24px;color:{C_GREEN};background:transparent;")
            self._hdr_status.show()
        elif is_online is False:
            self._hdr_status.setText("○ 离线")
            self._hdr_status.setStyleSheet(f"font-size:24px;color:{C_SUBTLE};background:transparent;")
            self._hdr_status.show()
        else:
            self._hdr_status.hide()
        self._hdr_sub.setText(sub if sub else "")
        self._hdr_sub.setVisible(bool(sub))

        # 按钮显隐
        is_room = bool(self._current_target and self._current_target.get("type") == "room")
        self._hdr_mb.setVisible(is_room)
        self._hdr_more.hide()

    def _build_composer(self):
        outer = QFrame()
        outer.setStyleSheet(f"background:{C_BG};")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(36, 28, 36, 32)

        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_CARD};border-radius:20px;}}")
        _apply_shadow(card, 18, 4, 22)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(26, 24, 26, 24)
        cl.setSpacing(0)

        ir = QHBoxLayout()
        ir.setSpacing(16)

        self._input = QTextEdit()
        self._input.setPlaceholderText("输入消息，Enter 发送…")
        self._input.setFixedHeight(56)
        self._input.setAcceptRichText(False)
        self._input.setStyleSheet(f"border:none;background:transparent;font-size:24px;color:{C_DARK};padding:4px 8px;")
        self._input.textChanged.connect(self._on_input_resize)
        self._input.installEventFilter(self)
        ir.addWidget(self._input, 1)

        self._send_btn = QPushButton("➤")
        self._send_btn.setFixedSize(64, 64)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:20px;font-size:28px;}}
            QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3B7FED,stop:1 #1D5CE6);}}
        """)
        _apply_shadow(self._send_btn, 28, 12, 90)
        self._send_btn.clicked.connect(self._on_send)
        ir.addWidget(self._send_btn)
        cl.addLayout(ir)

        ol.addWidget(card)
        return outer

    def _on_input_resize(self):
        doc = self._input.document()
        h = int(doc.size().height()) + 12
        h = max(56, min(h, 224))
        self._input.setFixedHeight(h)

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj == self._input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    # ═══════════════════════════════════════════════════
    #  对话列表项
    # ═══════════════════════════════════════════════════

    def _add_conv_item(self, key, av_text, av_color, name, sub, time_text, target, gradient=False, is_online=None):
        active = self._current_target and self._conv_key(self._current_target) == key

        if key in self._conv_items:
            it = self._conv_items[key]
            it.findChild(QLabel, "c_text").setText(
                f"<span style='font-size:27px;font-weight:700;color:{C_DARK};'>{name}</span>"
                f"<br><span style='font-size:20px;color:{C_MUTED};'>{sub}</span>")
            it.findChild(QLabel, "c_time").setText(time_text)
            # 更新激活态
            if active:
                it.setStyleSheet(
                    "QPushButton#ConvItem{background:#E0E7F5;border-radius:18px;padding:44px 28px 44px 60px;border:none;text-align:left;}")
            else:
                it.setStyleSheet(
                    "QPushButton#ConvItem{background:transparent;border-radius:18px;padding:44px 28px 44px 60px;border:none;text-align:left;}"
                    "QPushButton#ConvItem:hover{background:#E8EDF5;}")
            return

        btn = QPushButton()
        btn.setObjectName("ConvItem")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _, t=target: self._select_target(t))
        if active:
            btn.setStyleSheet(
                "QPushButton#ConvItem{background:#E0E7F5;border-radius:18px;padding:44px 28px 44px 60px;border:none;text-align:left;}")
        else:
            btn.setStyleSheet(
                "QPushButton#ConvItem{background:transparent;border-radius:18px;padding:44px 28px 44px 60px;border:none;text-align:left;}"
                "QPushButton#ConvItem:hover{background:#E8EDF5;}")

        # ── 按钮内部布局：头像 + 文字列 ──
        row = QHBoxLayout(btn)
        row.setContentsMargins(18, 0, 0, 0)
        row.setSpacing(16)

        # 头像容器 + 状态点覆盖在右下角
        av_wrap = QWidget()
        av_wrap.setFixedSize(65, 65)
        av_wrap.setStyleSheet("background:transparent;")
        av_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        av = QLabel(av_text, av_wrap)
        av.setFixedSize(65, 65)
        av.setAlignment(Qt.AlignCenter)
        if gradient:
            av.setStyleSheet(f"font-size:30px;font-weight:600;color:white;border-radius:32px;background:{C_BLUE_GRAD};")
        else:
            av.setStyleSheet(f"font-size:30px;font-weight:600;color:white;border-radius:32px;background:{av_color};")
        av.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        if is_online is not None:
            dot = QLabel(av_wrap)
            dot.setFixedSize(14, 14)
            if is_online:
                dot.setStyleSheet(f"background:{C_GREEN};border-radius:7px;border:2px solid white;")
            else:
                dot.setStyleSheet(f"background:{C_OFFLINE};border-radius:7px;border:2px solid white;")
            dot.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            dot.move(49, 49)

        row.addWidget(av_wrap)

        # 文字：名称+预览合并，时间放最右
        tx = QVBoxLayout()
        tx.setContentsMargins(10, 0, 0, 0)
        tx.setSpacing(0)

        combined = QLabel()
        combined.setObjectName("c_text")
        combined.setTextFormat(Qt.RichText)
        combined.setText(
            f"<span style='font-size:27px;font-weight:700;color:{C_DARK};'>{name}</span>"
            f"<br><span style='font-size:20px;color:{C_MUTED};'>{sub}</span>")
        combined.setStyleSheet("background:transparent;")
        combined.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        tx.addWidget(combined)

        row.addLayout(tx, 1)

        # 时间（右侧）
        ti = QLabel(time_text)
        ti.setObjectName("c_time")
        ti.setStyleSheet(f"font-size:22px;color:{C_SUBTLE};background:transparent; padding-right:25px;")
        ti.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(ti)

        self._conv_items[key] = btn
        self._conv_l.addWidget(btn)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER};margin:0 20px;")
        sep.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._conv_l.addWidget(sep)

    def _matches_search(self, name):
        if not self._search_text:
            return True
        return self._search_text in name.lower()

    def _is_online(self, uid):
        for u in (self.state.online_users or []):
            if u.get("user_id") == uid:
                return True
        return False

    def _refresh_list(self):
        # 清空
        for k in list(self._conv_items.keys()):
            w = self._conv_items.pop(k)
            w.deleteLater()
        while self._conv_l.count():
            it = self._conv_l.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.spacerItem():
                self._conv_l.removeItem(it)

        # 顶部横线
        top_sep = QFrame()
        top_sep.setFixedHeight(1)
        top_sep.setStyleSheet(f"background:{C_BORDER};margin:0 20px;")
        self._conv_l.addWidget(top_sep)

        # 公共聊天室
        if self._matches_search("公共聊天室"):
            self._add_conv_item(
                f"room_{PUBLIC_ROOM_ID}",
                "👥", "", "公共聊天室",
                self._last_previews.get("room_0", ""),
                self._last_times.get("room_0", ""),
                {"id": PUBLIC_ROOM_ID, "name": "公共聊天室", "type": "room"},
                gradient=True)

        # 群聊
        for g in self._my_groups:
            gid = g["group_id"]
            key = f"room_{gid}"
            if not self._matches_search(g.get("remark") or g.get("group_name", "")):
                continue
            self._add_conv_item(
                key,
                (g.get("remark") or g.get("group_name", ""))[0], _AVATAR_COLORS[hash(str(gid)) % len(_AVATAR_COLORS)],
                g.get("remark") or g.get("group_name", ""),
                self._last_previews.get(key, ""),
                self._last_times.get(key, ""),
                {"id": gid, "name": g.get("remark") or g.get("group_name", ""), "type": "room"})

        # 好友（全部显示，区分在线/离线）
        for f in (self.state.friends or []):
            uid = f["user_id"]
            key = f"p2p_{uid}"
            if not self._matches_search(f.get("remark") or f["username"]):
                continue
            online = self._is_online(uid)
            self._add_conv_item(
                key,
                (f.get("remark") or f["username"])[0], _AVATAR_COLORS[uid % len(_AVATAR_COLORS)],
                f.get("remark") or f["username"],
                self._last_previews.get(key, ""),
                self._last_times.get(key, ""),
                {"id": uid, "name": f.get("remark") or f["username"], "type": "p2p"},
                is_online=online)

        self._conv_l.addStretch()

    def _select_target(self, target):
        if self._current_target and self._current_target.get("id") == target.get("id") and self._current_target.get("type") == target.get("type"):
            return
        self._current_target = target
        self._unread.pop(self._conv_key(target), None)
        self._clear_messages()
        name = target["name"]
        sub = ""
        online = None
        if target.get("type") == "p2p":
            online = self._is_online(target["id"])
        self._chat_hdr.show()
        self._set_chat_header(name, sub, online)
        self._history_token += 1
        self._load_history(target)
        self._refresh_list()

    def _conv_key(self, target):
        if not target:
            return ""
        return f"{target['type']}_{target['id']}"

    def _load_history(self, target):
        if target["type"] == "p2p":
            self.net.send({"type": MT.HISTORY_REQ, "scope": "p2p", "target": target["id"], "token": self._history_token})
        else:
            self.net.send({"type": MT.HISTORY_REQ, "scope": "room", "room_id": target["id"], "token": self._history_token})

    # ═══════════════════════════════════════════════════
    #  发送
    # ═══════════════════════════════════════════════════

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text or not self._current_target:
            return
        self._input.clear()
        self._input.setFixedHeight(56)
        t = self._current_target
        ts = int(time.time())
        try:
            encrypted = self.app.crypto.encrypt(text)
        except Exception:
            encrypted = text
        if t["type"] == "p2p":
            self.net.send({"type": MT.CHAT, "to": t["id"], "content": encrypted, "ts": ts})
        else:
            self.net.send({"type": MT.ROOM_CHAT, "room_id": t["id"], "content": encrypted, "ts": ts})
        self._append_msg(text, ts, True)
        key = self._conv_key(t)
        self._last_previews[key] = text[:28]
        self._last_times[key] = self._fmt_time(ts)
        self._refresh_list()

    # ═══════════════════════════════════════════════════
    #  接收
    # ═══════════════════════════════════════════════════

    def _on_chat(self, msg):
        sender = msg.get("from", 0)
        if int(sender) == int(self.state.user_id or -1):
            return
        try:
            plain = self.app.crypto.decrypt(msg["content"])
        except Exception:
            plain = msg.get("content", "")
        key = f"p2p_{sender}"
        self._last_previews[key] = plain[:28]
        self._last_times[key] = self._fmt_time(int(time.time()))
        if self._current_target and self._conv_key(self._current_target) == key:
            self._unread.pop(key, None)
            name = self._find_name(sender)
            self._append_msg(plain, int(time.time()), False, sender_name=name)
        else:
            self._unread[key] = self._unread.get(key, 0) + 1
        self._refresh_list()

    def _on_room_chat(self, msg):
        sender = msg.get("from", 0)
        room_id = msg.get("room_id", 0)
        if int(sender) == int(self.state.user_id or -1):
            return
        if int(sender) == 0:
            try:
                sys_plain = self.app.crypto.decrypt(msg.get("content", ""))
            except Exception:
                sys_plain = msg.get("content", "")
            self._append_sys_msg(sys_plain)
            return
        # 陌生群聊 → 自动拉取群列表
        if room_id != PUBLIC_ROOM_ID and not any(g.get("group_id") == room_id for g in self._my_groups):
            self.net.send({"type": MT.GROUP_LIST})
        try:
            plain = self.app.crypto.decrypt(msg["content"])
        except Exception:
            plain = msg.get("content", "")
        key = f"room_{room_id}"
        name = self._find_name(sender)
        self._last_previews[key] = f"{name}: {plain[:20]}"
        self._last_times[key] = self._fmt_time(int(time.time()))
        if self._current_target and self._conv_key(self._current_target) == key:
            self._unread.pop(key, None)
            self._append_msg(plain, int(time.time()), False, sender_name=name)
        else:
            self._unread[key] = self._unread.get(key, 0) + 1
        self._refresh_list()

    # ═══════════════════════════════════════════════════
    #  历史
    # ═══════════════════════════════════════════════════

    def _on_history(self, msg):
        token = msg.get("token", 0)
        # token=0 是预览请求，更新预览文字后刷新列表
        if token == 0:
            records = msg.get("records", [])
            if records:
                last = records[-1]
                try:
                    content = self.app.crypto.decrypt(last.get("content", ""))
                except Exception:
                    content = last.get("content", "")
                preview = content[:28]
                ts_str = last.get("sent_at", "")
                try:
                    from datetime import datetime as dt
                    ts_dt = dt.strptime(str(ts_str)[:19], "%Y-%m-%d %H:%M:%S")
                    ts_val = int(ts_dt.timestamp())
                except Exception:
                    ts_val = 0
                scope = msg.get("scope", "")
                if scope == "p2p":
                    key = f"p2p_{msg.get('target', 0)}"
                    self._last_previews[key] = preview
                    self._last_times[key] = self._fmt_time(ts_val) if ts_val else ""
                elif scope == "room":
                    key = f"room_{msg.get('room_id', 0)}"
                    self._last_previews[key] = preview
                    self._last_times[key] = self._fmt_time(ts_val) if ts_val else ""
            self._refresh_list()
            return

        if token != self._history_token:
            return
        self._clear_messages()
        records = msg.get("records", [])
        if not records:
            self._append_sys_msg("暂无聊天记录")
            return
        # 同步最新预览
        last = records[-1]
        try:
            lp = self.app.crypto.decrypt(last.get("content", ""))
        except Exception:
            lp = last.get("content", "")
        scope = msg.get("scope", "")
        if scope == "p2p":
            pk = f"p2p_{msg.get('target', 0)}"
        else:
            pk = f"room_{msg.get('room_id', 0)}"
        self._last_previews[pk] = lp[:28]
        self._last_times[pk] = self._fmt_time(int(time.time()))
        for r in records:
            is_self = int(r.get("sender_id", 0)) == int(self.state.user_id or -1)
            try:
                content = self.app.crypto.decrypt(r.get("content", ""))
            except Exception:
                content = r.get("content", "")
            ts_str = r.get("sent_at", 0)
            try:
                ts = int(ts_str) if ts_str else int(time.time())
            except (ValueError, TypeError):
                ts = int(time.time())
            name = ""
            if not is_self:
                name = self._find_name(r.get("sender_id", 0))
            self._append_msg(content, ts, is_self, sender_name=name)
        self._scroll_bottom()

    # ═══════════════════════════════════════════════════
    #  创建群聊
    # ═══════════════════════════════════════════════════

    def _show_create_group_dialog(self):
        friends = self.state.friends or []
        if not friends:
            QMessageBox.information(self, "提示", "请先添加好友")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("创建群聊")
        dlg.setFixedSize(560, 640)
        dlg.setStyleSheet(f"background:{C_WHITE};border-radius:24px;")

        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(36, 36, 36, 32)
        lo.setSpacing(24)

        # 标题
        title = QLabel("创建群聊")
        title.setStyleSheet(f"font-size:32px;font-weight:800;color:{C_DARK};")
        lo.addWidget(title)

        desc = QLabel("选择至少 2 位好友，发起群聊")
        desc.setStyleSheet(f"font-size:20px;color:{C_SUBTLE};")
        lo.addWidget(desc)

        # 群名称
        name_input = QLineEdit()
        name_input.setPlaceholderText("输入群聊名称")
        name_input.setFixedHeight(56)
        name_input.setStyleSheet(
            f"background:{C_BG};border:2px solid {C_BORDER};border-radius:14px;font-size:24px;padding:0 18px;color:{C_DARK};")
        lo.addWidget(name_input)

        # 成员选择框（仿文件页接收人下拉样式）
        picker = QFrame()
        picker.setStyleSheet(f"QFrame{{background:{C_CARD};border:2px solid {C_BORDER};border-radius:16px;}}")
        pl = QVBoxLayout(picker)
        pl.setContentsMargins(14, 14, 14, 14)
        pl.setSpacing(10)

        # 搜索 + 全选按钮行
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        group_search = QLineEdit()
        group_search.setPlaceholderText("🔍 搜索好友…")
        group_search.setFixedHeight(50)
        group_search.setStyleSheet(f"background:{C_BG};border:none;border-radius:14px;font-size:22px;color:{C_DARK};padding:0 18px;")
        group_search.textChanged.connect(lambda t: [
            lst.item(i).setHidden(t.strip().lower() not in lst.item(i).text().lower())
            for i in range(lst.count())
        ])
        top_row.addWidget(group_search, 1)

        sel_all = QPushButton("全选")
        sel_all.setFixedHeight(50)
        sel_all.setCursor(Qt.PointingHandCursor)
        sel_all.setStyleSheet(f"QPushButton{{background:{C_BG};border:none;border-radius:14px;font-size:20px;font-weight:600;color:{C_PRIMARY};padding:0 14px;}}"
                               f"QPushButton:hover{{background:{C_BLUE_BG};}}")
        sel_all.clicked.connect(lambda: [lst.item(i).setCheckState(Qt.Checked) for i in range(lst.count())])
        top_row.addWidget(sel_all)
        desel = QPushButton("取消")
        desel.setFixedHeight(50)
        desel.setCursor(Qt.PointingHandCursor)
        desel.setStyleSheet(f"QPushButton{{background:{C_BG};border:none;border-radius:14px;font-size:20px;color:{C_SUBTLE};padding:0 14px;}}"
                             f"QPushButton:hover{{background:{C_BLUE_BG};}}")
        desel.clicked.connect(lambda: [lst.item(i).setCheckState(Qt.Unchecked) for i in range(lst.count())])
        top_row.addWidget(desel)
        pl.addLayout(top_row)

        # 滚动列表
        lsc = QScrollArea()
        lsc.setWidgetResizable(True)
        lsc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lsc.setFrameShape(QFrame.NoFrame)
        lsc.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                          "QScrollBar:vertical{width:6px;background:transparent;}"
                          "QScrollBar::handle:vertical{background:#CBD5E1;border-radius:3px;}")
        lst = QListWidget()
        lst.setSelectionMode(QListWidget.NoSelection)
        lst.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;font-size:22px;}}"
            "QListWidget::item{padding:14px 12px;border-bottom:1px solid #F0F2F5;}"
            "QListWidget::indicator{{width:22px;height:22px;}}")
        for f in friends:
            name = f.get("remark") or f["username"]
            item = QListWidgetItem("  " + name)
            item.setData(Qt.UserRole, f["user_id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            lst.addItem(item)
        lsc.setWidget(lst)
        # 点击整行切换勾选
        lst.itemClicked.connect(lambda item: item.setCheckState(
            Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked))
        pl.addWidget(lsc, 1)
        lo.addWidget(picker, 1)

        # 按钮行
        br = QHBoxLayout()
        br.setSpacing(20)
        cancel = QPushButton("取消")
        cancel.setFixedHeight(56)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"QPushButton{{background:{C_BG};color:{C_MUTED};border:none;border-radius:14px;font-size:24px;padding:0 28px;}}"
                             f"QPushButton:hover{{background:#E2E8F0;}}")
        cancel.clicked.connect(dlg.reject)
        br.addWidget(cancel)
        br.addStretch()

        confirm = QPushButton("创建群聊")
        confirm.setFixedHeight(56)
        confirm.setCursor(Qt.PointingHandCursor)
        confirm.setStyleSheet(f"QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:14px;font-size:24px;font-weight:700;padding:0 32px;}}"
                              f"QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3B7FED,stop:1 #1D5CE6);}}")
        confirm.clicked.connect(lambda: self._do_create_group(dlg, lst, name_input.text().strip()))
        br.addWidget(confirm)
        lo.addLayout(br)

        dlg.exec_()

    def _do_create_group(self, dlg, lst, group_name):
        selected = []
        for i in range(lst.count()):
            item = lst.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        if len(selected) < 2:
            QMessageBox.warning(self, "提示", "请至少选择 2 位好友")
            return
        self.net.send({"type": MT.GROUP_CREATE, "group_name": group_name or "新建群聊", "invitees": selected})
        dlg.accept()

    def _on_group_create_resp(self, msg):
        if msg.get("ok"):
            self.net.send({"type": MT.GROUP_LIST})
        else:
            QMessageBox.warning(self, "创建失败", msg.get("reason", "未知错误"))

    # ═══════════════════════════════════════════════════
    #  群聊其他
    # ═══════════════════════════════════════════════════

    def _on_group_list(self, msg):
        self._my_groups = msg.get("my_groups", [])
        self._refresh_list()
        # 加载公共聊天室和每个群的最新消息作为预览
        self.net.send({"type": MT.HISTORY_REQ, "scope": "room", "room_id": PUBLIC_ROOM_ID, "limit": 1, "token": 0})
        for g in self._my_groups:
            self.net.send({"type": MT.HISTORY_REQ, "scope": "room", "room_id": g["group_id"], "limit": 1, "token": 0})

    def _on_group_join(self, msg):
        if msg.get("ok"):
            self.net.send({"type": MT.GROUP_LIST})

    def _on_group_name_update(self, msg):
        gid = msg.get("group_id")
        for g in self._my_groups:
            if g["group_id"] == gid:
                g["group_name"] = msg.get("group_name", g.get("group_name", ""))
        if self._current_target and self._current_target.get("id") == gid:
            self._set_chat_header(msg.get("group_name", msg.get("name", "")), "")
        self._refresh_list()

    def _on_group_members(self, msg):
        members = msg.get("members", [])
        gid = msg.get("group_id", 0)
        self._group_members_cache[gid] = members

    def _on_group_invite(self, msg):
        self.net.send({"type": MT.GROUP_LIST})

    def _show_group_settings(self):
        if not self._current_target or self._current_target.get("type") != "room":
            return
        gid = self._current_target["id"]
        gname = self._current_target.get("name", "")
        is_public = gid == PUBLIC_ROOM_ID

        dlg = QDialog(self)
        dlg.setWindowTitle("群聊设置")
        dlg.setFixedSize(520, 640)
        # 先请求最新成员列表，等响应到达后再填充
        self._group_members_cache.pop(gid, None)
        self.net.send({"type": MT.GROUP_MEMBERS, "group_id": gid})
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(32, 32, 32, 28)
        lo.setSpacing(28)

        # 标题
        t = QLabel("群聊设置")
        t.setStyleSheet(f"font-size:28px;font-weight:800;color:{C_DARK};")
        lo.addWidget(t)

        # ── 修改群名称 ──
        nl = QLabel("修改群名称")
        nl.setStyleSheet(f"font-size:22px;font-weight:600;color:{C_MUTED};")
        lo.addWidget(nl)
        name_row = QHBoxLayout()
        name_row.setSpacing(16)
        name_input = QLineEdit()
        name_input.setPlaceholderText("新群聊名称")
        name_input.setText(gname)
        name_input.setFixedHeight(52)
        name_input.setStyleSheet(f"background:{C_BG};border:2px solid {C_BORDER};border-radius:14px;font-size:22px;padding:0 16px;color:{C_DARK};")
        name_row.addWidget(name_input, 1)
        rename_btn = QPushButton("修改")
        rename_btn.setFixedHeight(52)
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_btn.setStyleSheet(f"QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:14px;font-size:22px;font-weight:700;padding:0 24px;}}"
                                  f"QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3B7FED,stop:1 #1D5CE6);}}")
        rename_btn.clicked.connect(lambda: (
            self.net.send({"type": MT.GROUP_UPDATE_NAME, "group_id": gid, "group_name": name_input.text().strip()}),
            dlg.accept()))
        name_row.addWidget(rename_btn)
        lo.addLayout(name_row)

        # ── 成员列表 ──
        ml = QLabel("群成员")
        ml.setStyleSheet(f"font-size:24px;font-weight:700;color:{C_DARK};")
        lo.addWidget(ml)

        members_scroll = QScrollArea()
        members_scroll.setWidgetResizable(True)
        members_scroll.setFrameShape(QFrame.NoFrame)
        members_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                                     "QScrollBar:vertical{width:6px;background:transparent;}"
                                     "QScrollBar::handle:vertical{background:#CBD5E1;border-radius:3px;}")
        members_w = QWidget()
        members_l = QVBoxLayout(members_w)
        members_l.setContentsMargins(0, 0, 0, 0)
        members_l.setSpacing(10)
        members_l.setAlignment(Qt.AlignTop)

        # 延迟填充成员（等服务器响应）
        def fill_members():
            members = self._group_members_cache.get(gid, [])
            if not members:
                empty = QLabel("暂无成员信息")
                empty.setStyleSheet(f"font-size:20px;color:{C_SUBTLE};background:transparent;padding:20px 0;")
                empty.setAlignment(Qt.AlignCenter)
                members_l.addWidget(empty)
                return
            for m in members:
                row = QWidget()
                row.setStyleSheet(f"background:{C_BG};border-radius:14px;")
                rl2 = QHBoxLayout(row)
                rl2.setContentsMargins(16, 14, 16, 14)
                rl2.setSpacing(14)
                av = QLabel((m.get("nickname") or m.get("username", "?"))[0])
                av.setFixedSize(40, 40)
                av.setAlignment(Qt.AlignCenter)
                av.setStyleSheet(f"font-size:18px;font-weight:600;color:white;border-radius:20px;background:{_AVATAR_COLORS[hash(str(m.get('user_id',0))) % len(_AVATAR_COLORS)]};")
                rl2.addWidget(av)
                nm = QLabel(m.get("nickname") or m.get("username", ""))
                nm.setStyleSheet(f"font-size:22px;color:{C_DARK};background:transparent;")
                rl2.addWidget(nm, 1)
                members_l.addWidget(row)
        def try_fill():
            if self._group_members_cache.get(gid):
                fill_members()
            else:
                from PyQt5.QtCore import QTimer as QtTimer2
                QtTimer2.singleShot(200, try_fill)
        from PyQt5.QtCore import QTimer as QtTimer2
        QtTimer2.singleShot(200, try_fill)
        members_l.addStretch()
        members_scroll.setWidget(members_w)
        lo.addWidget(members_scroll, 1)

        # ── 退出/删除群聊 ──
        if not is_public:
            leave_btn = QPushButton("退出群聊")
            leave_btn.setFixedHeight(52)
            leave_btn.setCursor(Qt.PointingHandCursor)
            leave_btn.setStyleSheet(f"QPushButton{{background:#FFF1F2;color:{C_RED};border:1px solid #FECACA;border-radius:14px;font-size:22px;font-weight:600;}}"
                                     f"QPushButton:hover{{background:#FEE2E2;}}")
            leave_btn.clicked.connect(lambda: (
                self.net.send({"type": MT.GROUP_REMOVE_MEMBER, "group_id": gid, "target_id": self.state.user_id}),
                self.net.send({"type": MT.GROUP_LIST}),
                dlg.accept(),
                setattr(self, '_current_target', None) or self._set_chat_header("", "", None) or self._chat_hdr.hide() or self._clear_messages()))
            lo.addWidget(leave_btn)

        dlg.exec_()

    def _show_members(self):
        if self._current_target and self._current_target.get("type") == "room":
            self.net.send({"type": MT.GROUP_MEMBERS, "group_id": self._current_target["id"]})

    def _show_more_menu(self):
        if not self._current_target or self._current_target.get("type") != "p2p":
            return
        menu = QMenu(self)
        act = menu.addAction("删除好友")
        act.triggered.connect(self._remove_friend)
        menu.exec_(self.cursor().pos())

    def _remove_friend(self):
        if not self._current_target:
            return
        self.net.send({"type": MT.FRIEND_REMOVE, "friend_id": self._current_target["id"]})

    # ═══════════════════════════════════════════════════
    #  好友列表 & 在线状态
    # ═══════════════════════════════════════════════════

    def _on_friend_list(self, msg):
        self.state.friends = msg.get("friends", [])
        self._refresh_list()
        # 加载每个好友的最新一条消息作为预览
        for f in self.state.friends:
            self.net.send({"type": MT.HISTORY_REQ, "scope": "p2p", "target": f["user_id"], "limit": 1, "token": 0})
        # 如果当前正处在私聊界面，同步更新头部显示（备注变更后及时刷新）
        if self._current_target and self._current_target.get("type") == "p2p":
            fid = self._current_target["id"]
            for f in self.state.friends:
                if f["user_id"] == fid:
                    new_name = f.get("remark") or f["username"]
                    self._current_target["name"] = new_name
                    online = self._is_online(fid)
                    self._set_chat_header(new_name, "", online)
                    break

    def _on_friend_remove_resp(self, msg):
        if msg.get("ok"):
            self._current_target = None
            self._clear_messages()
            self._set_chat_header("Linkora", "")
            self.net.send({"type": MT.FRIEND_LIST})

    def _on_user_list(self, msg):
        had_friends = bool(self.state.friends)
        self.state.online_users = msg.get("online_users", [])
        self.state.all_users = msg.get("all_users", [])
        # 首次收到在线列表时拉取好友和群聊
        if not had_friends and self.state.user_id:
            self._request_lists()
        self._refresh_list()

    # ═══════════════════════════════════════════════════
    #  消息显示
    # ═══════════════════════════════════════════════════

    def _append_msg(self, text, ts, is_self, sender_name=""):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(20)

        if is_self:
            lo.addStretch()

        if not is_self:
            av_text = sender_name[0] if sender_name else "?"
            av = QLabel(av_text)
            av.setFixedSize(64, 64)
            av.setAlignment(Qt.AlignCenter)
            c = _AVATAR_COLORS[hash(sender_name) % len(_AVATAR_COLORS)] if sender_name else C_PRIMARY
            av.setStyleSheet(f"font-size:30px;font-weight:600;color:white;border-radius:32px;background:{c};")
            lo.addWidget(av)

        # 气泡列
        col_w = QWidget()
        col_w.setStyleSheet("background:transparent;")
        col = QVBoxLayout(col_w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)

        info = QLabel()
        if is_self:
            info.setText(self._fmt_time(ts))
            info.setAlignment(Qt.AlignRight)
        else:
            info.setText(f"{sender_name} · {self._fmt_time(ts)}" if sender_name else self._fmt_time(ts))
        info.setStyleSheet(f"font-size:23px;color:{C_SUBTLE};")
        col.addWidget(info)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(1280 if is_self else 1360)
        bubble.setTextFormat(Qt.PlainText)
        if is_self:
            bubble.setStyleSheet(f"""
                QLabel{{background:{C_BLUE_GRAD};color:white;border-radius:22px;
                border-top-right-radius:6px;font-size:24px;padding:20px 27px;}}
            """)
        else:
            bubble.setStyleSheet(f"""
                QLabel{{background:{C_WHITE};color:{C_DARK};border:1px solid {C_BLUE_BG};
                border-radius:22px;border-top-left-radius:6px;font-size:24px;padding:20px 27px;}}
            """)
        # 用水平 layout + stretch 约束气泡宽度，与 AI 面板一致
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_self:
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()
        col.addLayout(row)

        lo.addWidget(col_w)

        if not is_self:
            lo.addStretch()

        self._msg_l.addWidget(w)
        self._scroll_bottom()

    def _append_sys_msg(self, text):
        l = QLabel(text)
        l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet(f"font-size:22px;color:{C_SUBTLE};padding:8px 20px;")
        self._msg_l.addWidget(l)
        self._scroll_bottom()

    def _clear_messages(self):
        if hasattr(self, '_welcome') and self._welcome:
            self._welcome.hide()
        while self._msg_l.count():
            it = self._msg_l.takeAt(0)
            if it.widget() and it.widget() is not getattr(self, '_welcome', None):
                it.widget().deleteLater()
            elif it.spacerItem():
                self._msg_l.removeItem(it)

    def _scroll_bottom(self):
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(30, lambda: self._msg_scroll.verticalScrollBar().setValue(
            self._msg_scroll.verticalScrollBar().maximum()))

    # ═══════════════════════════════════════════════════
    #  辅助
    # ═══════════════════════════════════════════════════

    def _fmt_time(self, ts):
        from datetime import datetime
        return datetime.fromtimestamp(ts).strftime("%H:%M")

    def _find_name(self, uid):
        uid = int(uid)
        for g in self._my_groups:
            for m in g.get("members", []):
                if m.get("user_id") == uid:
                    return m.get("nickname") or m.get("username", f"用户{uid}")
        for f in self.state.friends or []:
            if f["user_id"] == uid:
                return f.get("remark") or f["username"]
        for u in self.state.all_users or []:
            if u.get("user_id") == uid:
                return u.get("nickname") or u.get("username", f"用户{uid}")
        return f"用户{uid}"
