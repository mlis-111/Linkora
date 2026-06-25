"""好友面板（客户端）

支持好友列表展示、添加好友、设置备注功能。
UI 对齐消息面板样式。

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
from common.messages import MT

_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
]

C_DARK    = "#1E293B"
C_SUBTLE  = "#94A3B8"
C_MUTED   = "#6B7A90"
C_WHITE   = "#FFFFFF"
C_BG      = "#EEF2FA"
C_SIDEBAR = "#F0F4FA"
C_BORDER  = "#E5EAF3"
C_PRIMARY = "#2D6CF6"
C_BLUE_BG = "#E7EFFC"
C_BLUE_GRAD = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4F8DFD,stop:1 #2D6CF6)"
C_GREEN   = "#34D399"
C_OFFLINE = "#CBD5E1"
C_RED     = "#FB7185"


class FriendPanel(BasePanel):
    """好友面板"""

    def __init__(self, parent, app):
        self._friends = []
        self._filter = "all"
        self._pending_requests = []
        self._rejected_requests = []
        self._searched_user = None
        self._search_text = ""
        super().__init__(parent, app)

    def subscribe(self):
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
        super().showEvent(event)
        if self.state.user_id and not self._friends:
            self.net.send({"type": MT.FRIEND_LIST})

    # ═══════════════════════════════════════════════════
    #  整体布局
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        self.setStyleSheet(f"background:{C_BG};")
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._build_left(), 1)

        d = QFrame()
        d.setFixedWidth(1)
        d.setStyleSheet(f"background:{C_BORDER};")
        main.addWidget(d)

        self._build_right()
        main.addWidget(self._right_panel)

        from PyQt5.QtCore import QTimer as QtTimer
        QtTimer.singleShot(200, lambda: self.net.send({"type": MT.FRIEND_LIST}))

    # ═══════════════════════════════════════════════════
    #  左侧好友列表
    # ═══════════════════════════════════════════════════

    def _build_left(self):
        left = QFrame()
        left.setStyleSheet(f"background:{C_SIDEBAR};")
        lo = QVBoxLayout(left)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # 标题行
        hdr = QWidget()
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(48, 60, 28, 36)
        hl.setSpacing(14)
        t = QLabel("好友列表")
        t.setStyleSheet(f"font-size:45px;font-weight:900;color:{C_DARK};")
        hl.addWidget(t)

        hl.addStretch()

        add = QPushButton("＋ 添加好友")
        add.setFixedHeight(64)
        add.setCursor(Qt.PointingHandCursor)
        add.setStyleSheet(f"""
            QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:14px;font-size:26px;font-weight:700;padding:0 20px;}}
            QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3B7FED,stop:1 #1D5CE6);}}
        """)
        add.clicked.connect(self._on_add_friend)
        hl.addWidget(add)
        lo.addWidget(hdr)

        # 筛选栏
        bar = QFrame()
        bar.setStyleSheet(f"background:{C_SIDEBAR};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(44, 10, 44, 18)
        bl.setSpacing(12)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索好友")
        self._search_box.setFixedHeight(60)
        self._search_box.setStyleSheet(f"""
            QLineEdit{{background:{C_WHITE};border:none;border-radius:20px;
            font-size:24px;color:{C_DARK};padding:0 20px;}}
            QLineEdit::placeholder{{color:#B0BAC8;}}
        """)
        self._search_box.textChanged.connect(self._on_search_text)
        bl.addWidget(self._search_box)

        self._filter_btns = {}
        for k, label in [("all", "全部"), ("online", "在线"), ("offline", "离线")]:
            b = QPushButton(label)
            b.setFixedHeight(60)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, key=k: self._set_filter(key))
            self._filter_btns[k] = b
            bl.addWidget(b)
        self._update_filter_style()
        lo.addWidget(bar)

        # 好友列表
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setStyleSheet(
            f"QScrollArea{{border:none;background:{C_SIDEBAR};}}"
            "QScrollBar:vertical{width:8px;background:transparent;}"
            "QScrollBar::handle:vertical{background:rgba(100,116,139,0.22);border-radius:6px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}")
        self._fl_w = QWidget()
        self._fl_w.setStyleSheet("background:transparent;")
        self._fl_l = QVBoxLayout(self._fl_w)
        self._fl_l.setContentsMargins(44, 0, 44, 24)
        self._fl_l.setSpacing(16)
        self._fl_l.setAlignment(Qt.AlignTop)
        sc.setWidget(self._fl_w)
        lo.addWidget(sc, 1)
        return left

    def _update_filter_style(self):
        for k, b in self._filter_btns.items():
            if k == self._filter:
                b.setStyleSheet(f"QPushButton{{background:{C_BLUE_BG};color:{C_PRIMARY};border:none;border-radius:14px;font-size:24px;font-weight:700;padding:0 18px;}}")
            else:
                b.setStyleSheet(f"QPushButton{{background:{C_WHITE};color:{C_SUBTLE};border:none;border-radius:14px;font-size:24px;padding:0 18px;}}"
                                f"QPushButton:hover{{background:{C_BLUE_BG};color:{C_PRIMARY};}}")

    def _set_filter(self, key):
        self._filter = key
        self._update_filter_style()
        self._refresh_list()

    def _on_search_text(self, text):
        self._search_text = text.strip().lower()
        self._refresh_list()

    def _matches(self, name):
        return (not self._search_text) or (self._search_text in name.lower())

    # ═══════════════════════════════════════════════════
    #  好友列表渲染
    # ═══════════════════════════════════════════════════

    def _create_avatar(self, size, text, color):
        av = QLabel(text)
        av.setFixedSize(size, size)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"font-size:{size//2}px;font-weight:600;color:white;border-radius:{size//2}px;background:{color};")
        return av

    def _refresh_list(self):
        while self._fl_l.count():
            it = self._fl_l.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            elif it.spacerItem(): self._fl_l.removeItem(it)

        online_ids = {u["user_id"] for u in self.state.online_users}
        filtered = self._friends
        if self._filter == "online":
            filtered = [f for f in self._friends if f.get("user_id") in online_ids]
        elif self._filter == "offline":
            filtered = [f for f in self._friends if f.get("user_id") not in online_ids]
        if self._search_text:
            filtered = [f for f in filtered if self._matches(f.get("remark") or f.get("username", ""))]

        if not filtered:
            e = QLabel("暂无好友")
            e.setAlignment(Qt.AlignCenter)
            e.setStyleSheet(f"font-size:26px;color:{C_SUBTLE};padding:80px 0;")
            self._fl_l.addWidget(e)
        else:
            online = [f for f in filtered if f.get("user_id") in online_ids]
            offline = [f for f in filtered if f.get("user_id") not in online_ids]
            if online:
                self._add_section(f"在线 · {len(online)} 人")
                for i, f in enumerate(online):
                    self._add_card(f, True, _AVATAR_COLORS[i % len(_AVATAR_COLORS)])
            if offline:
                self._add_section(f"离线 · {len(offline)} 人")
                for i, f in enumerate(offline):
                    self._add_card(f, False, _AVATAR_COLORS[(i + len(online)) % len(_AVATAR_COLORS)])
        self._fl_l.addStretch()

    def _add_section(self, text):
        w = QFrame()
        w.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(4, 12, 4, 8)
        l = QLabel(text)
        l.setStyleSheet(f"font-size:20px;font-weight:700;color:{C_SUBTLE};")
        hl.addWidget(l)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{C_BORDER};")
        hl.addWidget(line, 1)
        self._fl_l.addWidget(w)

    def _add_card(self, friend, online, color):
        """好友卡片 — 仿消息面板按钮样式"""
        name = friend.get("remark") or friend.get("username", "?")
        fid = friend.get("user_id")

        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_WHITE};border-radius:18px;}}QFrame:hover{{background:#E2EAF6;}}")

        lo = QHBoxLayout(card)
        lo.setContentsMargins(24, 24, 28, 24)
        lo.setSpacing(16)

        # 头像容器 + 状态点
        av_wrap = QWidget()
        av_wrap.setFixedSize(65, 65)
        av_wrap.setStyleSheet("background:transparent;")

        av = QLabel(name[0], av_wrap)
        av.setFixedSize(65, 65)
        av.setAlignment(Qt.AlignCenter)
        av.setStyleSheet(f"font-size:30px;font-weight:600;color:white;border-radius:32px;background:{color};")

        dot = QLabel(av_wrap)
        dot.setFixedSize(14, 14)
        dot.setStyleSheet(f"background:{C_GREEN if online else C_OFFLINE};border-radius:7px;border:2px solid white;")
        dot.move(49, 49)
        lo.addWidget(av_wrap)

        tx = QVBoxLayout()
        tx.setSpacing(6)
        nm = QLabel(name)
        nm.setStyleSheet(f"font-size:27px;font-weight:700;color:{C_DARK};background:transparent;border:none;")
        tx.addWidget(nm)
        st = QLabel("在线" if online else "离线")
        st.setStyleSheet(f"font-size:20px;color:{C_GREEN if online else C_SUBTLE};background:transparent;border:none;")
        tx.addWidget(st)
        lo.addLayout(tx, 1)

        # 操作按钮
        chat = QPushButton("💬")
        chat.setFixedSize(70, 70)
        chat.setCursor(Qt.PointingHandCursor)
        chat.setStyleSheet(f"QPushButton{{background:{C_BLUE_BG};border:none;border-radius:18px;font-size:32px;}}"
                           f"QPushButton:hover{{background:#D1E3FA;}}")
        chat.clicked.connect(lambda _, fid=fid, nm=name: self._switch_to_chat(fid, nm))
        lo.addWidget(chat)

        more = QPushButton("⋯")
        more.setFixedSize(70, 70)
        more.setCursor(Qt.PointingHandCursor)
        more.setStyleSheet(f"QPushButton{{background:{C_SIDEBAR};border:none;border-radius:18px;font-size:32px;}}"
                           f"QPushButton:hover{{background:{C_BLUE_BG};color:{C_PRIMARY};}}")
        lo.addWidget(more)

        # 内联编辑区：取消 | 备注输入 | 保存备注 ‖ 删除好友
        edit = QFrame()
        edit.hide()
        el = QHBoxLayout(edit)
        el.setContentsMargins(28, 20, 28, 20)
        el.setSpacing(16)

        # 备注输入（先创建，供后续 lambda 引用）
        inp = QLineEdit()
        inp.setPlaceholderText("输入备注")
        inp.setText(friend.get("remark", ""))
        inp.setFixedHeight(56)
        inp.setStyleSheet(f"background:{C_BLUE_BG};border:2px solid {C_PRIMARY};border-radius:14px;font-size:24px;padding:0 16px;color:{C_DARK};")

        # 取消
        cancel = QPushButton("取消")
        cancel.setFixedHeight(56)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"QPushButton{{background:{C_SIDEBAR};color:{C_SUBTLE};border:none;border-radius:14px;font-size:24px;font-weight:600;padding:0 28px;}}"
                              f"QPushButton:hover{{background:#E2E8F0;}}")
        cancel.clicked.connect(lambda _, es=edit, inp=inp, orig=friend.get("remark", ""): (inp.setText(orig), es.hide()))
        el.addWidget(cancel)

        el.addWidget(inp, 1)

        # 保存备注
        save = QPushButton("保存备注")
        save.setFixedHeight(56)
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(f"QPushButton{{background:{C_PRIMARY};color:white;border:none;border-radius:14px;font-size:24px;font-weight:700;padding:0 24px;}}"
                            f"QPushButton:hover{{background:#1D5CE6;}}")
        save.clicked.connect(lambda _, fid=fid, inp=inp, es=edit: (
            self.net.send({"type": MT.FRIEND_REMARK, "friend_id": fid, "remark": inp.text().strip()}),
            self.net.send({"type": MT.FRIEND_LIST}), es.hide()))
        el.addWidget(save)

        # 竖线分隔
        vl = QFrame()
        vl.setFixedWidth(1)
        vl.setStyleSheet(f"background:{C_BORDER};")
        el.addWidget(vl)
        el.addSpacing(16)

        # 删除好友
        del_btn = QPushButton("🗑 删除好友")
        del_btn.setFixedHeight(56)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(f"QPushButton{{background:#FFF1F2;color:{C_RED};border:none;border-radius:14px;font-size:24px;font-weight:600;padding:0 28px;}}"
                               f"QPushButton:hover{{background:#FEE2E2;}}")
        del_btn.clicked.connect(lambda _, fid=fid: (
            self.net.send({"type": MT.FRIEND_REMOVE, "friend_id": fid}), edit.hide()))
        el.addWidget(del_btn)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        w0 = QWidget()
        w0.setLayout(lo)
        outer.addWidget(w0)
        outer.addWidget(edit)
        card.setLayout(outer)

        more.clicked.connect(lambda _, es=edit, inp=inp: (es.show(), inp.setFocus(), inp.selectAll()) if es.isHidden() else es.hide())
        self._fl_l.addWidget(card)

    # ═══════════════════════════════════════════════════
    #  右侧面板
    # ═══════════════════════════════════════════════════

    def _build_right(self):
        self._right_panel = QFrame()
        self._right_panel.setFixedWidth(680)
        self._right_panel.setStyleSheet(f"background:{C_BG};")
        lo = QVBoxLayout(self._right_panel)
        lo.setContentsMargins(32, 40, 32, 28)
        lo.setSpacing(22)

        self._add_card_w = self._build_add_card()
        self._add_card_w.hide()
        lo.addWidget(self._add_card_w)

        self._req_card = self._build_req_card()
        lo.addWidget(self._req_card, 1)

    def _build_add_card(self):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_WHITE};border-radius:20px;}}")
        al = QVBoxLayout(card)
        al.setContentsMargins(28, 28, 28, 28)
        al.setSpacing(0)

        t = QLabel("添加好友")
        t.setStyleSheet(f"font-size:32px;font-weight:800;color:{C_DARK};padding-bottom:10px;")
        al.addWidget(t)
        d = QLabel(" 输入对方用户ID，发送好友申请")
        d.setStyleSheet(f"font-size:20px;color:{C_SUBTLE};")
        al.addSpacing(6)
        al.addWidget(d)
        al.addSpacing(24)

        sr = QFrame()
        sr.setStyleSheet(f"QFrame{{background:{C_BLUE_BG};border:2px solid {C_PRIMARY};border-radius:15px;}}")
        srl = QHBoxLayout(sr)
        srl.setContentsMargins(18, 0, 18, 0)
        srl.setSpacing(12)
        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("输入用户ID搜索")
        self._add_input.setFixedHeight(56)
        self._add_input.setStyleSheet("border:none;background:transparent;font-size:22px;color:#1E293B;")
        srl.addWidget(self._add_input, 1)
        sb = QPushButton("搜索")
        sb.setFixedHeight(40)
        sb.setCursor(Qt.PointingHandCursor)
        sb.setStyleSheet(f"QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:12px;font-size:20px;font-weight:700;padding:0 18px;}}")
        sb.clicked.connect(self._on_search_user)
        srl.addWidget(sb)
        al.addWidget(sr)

        self._result_frame = QFrame()
        self._result_frame.setStyleSheet(f"QFrame{{background:{C_SIDEBAR};border-radius:16px;}}")
        self._result_frame.hide()
        rl = QHBoxLayout(self._result_frame)
        rl.setContentsMargins(18, 16, 18, 16)
        rl.setSpacing(14)
        self._result_av = self._create_avatar(52, "?", "#0EA5E9")
        rl.addWidget(self._result_av)
        rv = QVBoxLayout()
        rv.setSpacing(4)
        self._result_name = QLabel("")
        self._result_name.setStyleSheet(f"font-size:22px;font-weight:700;color:{C_DARK};")
        rv.addWidget(self._result_name)
        self._result_info = QLabel("")
        self._result_info.setStyleSheet(f"font-size:20px;color:{C_SUBTLE};")
        rv.addWidget(self._result_info)
        rl.addLayout(rv, 1)
        self._apply_btn = QPushButton("申请")
        self._apply_btn.setFixedHeight(48)
        self._apply_btn.setCursor(Qt.PointingHandCursor)
        self._apply_btn.setStyleSheet(f"QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:14px;font-size:20px;font-weight:700;padding:0 22px;}}")
        self._apply_btn.clicked.connect(self._on_apply)
        rl.addWidget(self._apply_btn)
        al.addSpacing(24)
        al.addWidget(self._result_frame)

        self._verify_row = QFrame()
        self._verify_row.hide()
        vl = QVBoxLayout(self._verify_row)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(8)
        vl2 = QLabel("验证消息")
        vl2.setStyleSheet(f"font-size:20px;font-weight:600;color:{C_MUTED};")
        vl.addWidget(vl2)
        self._verify_input = QLineEdit()
        self._verify_input.setPlaceholderText(f"我是{self.state.username or 'XXX'}")
        self._verify_input.setText(f"我是{self.state.username or 'XXX'}")
        self._verify_input.setFixedHeight(42)
        self._verify_input.setStyleSheet(f"background:{C_SIDEBAR};border:2px solid {C_BORDER};border-radius:13px;font-size:20px;padding:0 14px;color:{C_DARK};")
        vl.addWidget(self._verify_input)
        al.addSpacing(20)
        al.addWidget(self._verify_row)

        self._add_msg = QLabel("")
        self._add_msg.setAlignment(Qt.AlignCenter)
        self._add_msg.setStyleSheet("font-size:20px;font-weight:600;padding:10px 0;")
        self._add_msg.hide()
        al.addWidget(self._add_msg)

        return card

    def _build_req_card(self):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{C_WHITE};border-radius:20px;}}")
        rl = QVBoxLayout(card)
        rl.setContentsMargins(40, 40, 28, 28)
        rl.setSpacing(0)

        tr = QHBoxLayout()
        t = QLabel("好友申请")
        t.setStyleSheet(f"font-size:32px;font-weight:800;color:{C_DARK};")
        tr.addWidget(t)
        self._req_badge = QLabel("0")
        self._req_badge.setStyleSheet(f"font-size:24px;font-weight:700;color:white;background:{C_RED};padding:4px 14px;border-radius:12px;")
        self._req_badge.hide()
        tr.addWidget(self._req_badge)
        tr.addStretch()
        rl.addLayout(tr)
        rl.addSpacing(35)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea{border:none;background:transparent;}"
                         "QScrollBar:vertical{width:6px;background:transparent;}"
                         "QScrollBar::handle:vertical{background:rgba(100,116,139,0.22);border-radius:6px;}")
        self._req_w = QWidget()
        self._req_w.setStyleSheet("background:transparent;")
        self._req_l = QVBoxLayout(self._req_w)
        self._req_l.setContentsMargins(16, 8, 16, 16)
        self._req_l.setSpacing(30)
        self._req_l.setAlignment(Qt.AlignTop)

        sc.setWidget(self._req_w)
        rl.addWidget(sc, 1)
        return card

    # ═══════════════════════════════════════════════════
    #  交互
    # ═══════════════════════════════════════════════════

    def _on_search_user(self):
        tid = self._add_input.text().strip()
        if not tid:
            self._show_msg("请输入用户ID", False)
            return
        self._searched_user = None
        self._result_frame.hide()
        self._verify_row.hide()
        self._add_msg.hide()
        self.net.send({"type": MT.USER_SEARCH, "target_id": tid})

    def _on_apply(self):
        if not self._searched_user: return
        self.net.send({"type": MT.FRIEND_ADD, "target_id": str(self._searched_user["user_id"]),
                        "message": self._verify_input.text().strip()})

    def _on_user_search_resp(self, msg):
        if not msg.get("ok"):
            self._result_frame.hide(); self._verify_row.hide()
            self._show_msg(f"❌ {msg.get('reason', '搜索失败')}", False); return
        u = msg["user"]
        self._searched_user = u
        name = u.get("nickname") or u.get("username", "")
        self._result_av.setText(name[0])
        c = _AVATAR_COLORS[hash(u["username"]) % len(_AVATAR_COLORS)]
        self._result_av.setStyleSheet(f"font-size:22px;font-weight:600;color:white;border-radius:26px;background:{c};")
        self._result_name.setText(name)
        if u.get("is_friend"):
            self._result_info.setText("已是好友"); self._apply_btn.setEnabled(False); self._apply_btn.setText("已是好友"); self._verify_row.hide()
        else:
            self._result_info.setText(f"用户ID: {u['user_id']}"); self._apply_btn.setEnabled(True); self._apply_btn.setText("申请")
            self._verify_input.setText(f"我是{self.state.username or 'XXX'}"); self._verify_row.show()
        self._result_frame.show()

    def _show_msg(self, text, success):
        self._add_msg.setStyleSheet(f"font-size:20px;font-weight:600;padding:10px 0;color:{'#10B981' if success else '#EF4444'};")
        self._add_msg.setText(text); self._add_msg.show()
        QTimer.singleShot(3000, self._add_msg.hide)

    def _on_add_friend(self):
        if self._add_card_w.isVisible():
            self._add_card_w.hide()
            return
        self._add_card_w.show()
        self._add_input.setFocus(); self._add_input.clear()
        self._result_frame.hide(); self._verify_row.hide(); self._add_msg.hide()
        self._searched_user = None

    def _on_friend_add(self, msg):
        if msg.get("ok"):
            self._show_msg("已发送好友申请", True); self._result_frame.hide(); self._verify_row.hide(); self._add_input.clear(); self._searched_user = None
            self.net.send({"type": MT.FRIEND_REQ_LIST})
        else: self._show_msg(f"❌ {msg.get('reason', '添加失败')}", False)

    def _on_friend_req_notify(self, msg): self.net.send({"type": MT.FRIEND_REQ_LIST})
    def _on_friend_agree_resp(self, msg):
        fid = msg.get("friend_id")
        if msg.get("accepted"):
            req_msg = msg.get("request_message", "").strip()
            if req_msg:
                self.net.send({"type": MT.CHAT, "to": fid, "content": self.app.crypto.encrypt(req_msg), "ts": int(time.time())})
        elif msg.get("ok") and fid:
            QTimer.singleShot(500, lambda: self.net.send({"type": MT.CHAT, "to": fid, "content": self.app.crypto.encrypt("我们现在是好友啦"), "ts": int(time.time())}))
        self.net.send({"type": MT.FRIEND_LIST})
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_friend_req_list(self, msg):
        incoming = msg.get("incoming", [])
        self._pending_requests = [r for r in incoming if r.get("status") == 0]
        self._accepted_requests = [r for r in incoming if r.get("status") == 1]
        self._rejected_requests = [r for r in incoming if r.get("status") == 2]
        self._outgoing_requests = msg.get("outgoing", [])
        self._refresh_requests()

    def _refresh_requests(self):
        while self._req_l.count():
            it = self._req_l.takeAt(0)
            if it.widget() and it.widget() is not getattr(self, '_no_req', None):
                it.widget().deleteLater()
            elif it.spacerItem():
                self._req_l.removeItem(it)
        # 隐藏旧的无申请提示
        if hasattr(self, '_no_req') and self._no_req:
            self._no_req.hide()
        pending_n = len(self._pending_requests)
        total = pending_n + len(self._outgoing_requests) + len(self._accepted_requests) + len(self._rejected_requests)
        if total == 0:
            self._req_badge.hide()
            if not hasattr(self, '_no_req') or not self._no_req:
                self._no_req = QLabel("暂无好友申请")
                self._no_req.setAlignment(Qt.AlignCenter)
                self._no_req.setStyleSheet(f"font-size:24px;color:{C_SUBTLE};background:transparent;")
            try:
                self._no_req.show()
                self._req_l.addStretch()
                self._req_l.addWidget(self._no_req)
                self._req_l.addStretch()
            except RuntimeError:
                self._no_req = QLabel("暂无好友申请")
                self._no_req.setAlignment(Qt.AlignCenter)
                self._no_req.setStyleSheet(f"font-size:24px;color:{C_SUBTLE};background:transparent;")
                self._req_l.addStretch()
                self._req_l.addWidget(self._no_req)
                self._req_l.addStretch()
            return
        self._req_badge.setText(str(pending_n)) if pending_n else self._req_badge.hide()
        self._req_badge.setVisible(pending_n > 0)
        for r in self._pending_requests:
            self._add_pending(r)
        for r in self._accepted_requests:
            self._add_incoming_done(r, True)
        for r in self._rejected_requests:
            self._add_incoming_done(r, False)
        for r in self._outgoing_requests:
            self._add_outgoing(r)

    def _add_pending(self, req):
        from_id = req.get("from_id"); name = req.get("nickname") or req.get("username", "未知")
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:#FFFBE6;border:1px solid #FDE68A;border-radius:24px;}}")
        lo = QVBoxLayout(card)
        lo.setContentsMargins(32, 34, 32, 34); lo.setSpacing(36)
        ir = QHBoxLayout(); ir.setSpacing(24)
        av = self._create_avatar(64, name[0], "#A78BFA"); ir.addWidget(av)
        tv = QVBoxLayout(); tv.setSpacing(12)
        nl = QLabel(name); nl.setStyleSheet(f"font-size:26px;font-weight:700;color:{C_DARK};background:transparent;border:none;"); tv.addWidget(nl)
        tl = QLabel("刚刚"); tl.setStyleSheet(f"font-size:22px;color:{C_SUBTLE};background:transparent;border:none;"); tv.addWidget(tl)
        ir.addLayout(tv, 1); lo.addLayout(ir)
        if req.get("message"):
            ml = QLabel(req["message"]); ml.setWordWrap(True)
            ml.setStyleSheet(f"font-size:24px;color:{C_MUTED};background:white;padding:20px 22px;border:1px solid {C_BORDER};border-radius:12px;")
            lo.addWidget(ml)
        br = QHBoxLayout(); br.setSpacing(0)
        ac = QPushButton("接受"); ac.setFixedHeight(52); ac.setCursor(Qt.PointingHandCursor)
        ac.setStyleSheet(f"QPushButton{{background:{C_BLUE_GRAD};color:white;border:none;border-radius:14px;font-size:22px;font-weight:700;}}")
        ac.clicked.connect(lambda _, fid=from_id: (
            self.net.send({"type": MT.FRIEND_AGREE, "from_id": fid}),
            self.net.send({"type": MT.FRIEND_REQ_LIST})))
        rj = QPushButton("拒绝"); rj.setFixedHeight(52); rj.setCursor(Qt.PointingHandCursor)
        rj.setStyleSheet(f"QPushButton{{background:#FFF1F2;color:{C_RED};border:1px solid #FECACA;border-radius:14px;font-size:22px;font-weight:600;}}"
                          f"QPushButton:hover{{background:#FEE2E2;}}")
        rj.clicked.connect(lambda _, fid=from_id: (self.net.send({"type": MT.FRIEND_REJECT, "from_id": fid, "reason": ""}), self.net.send({"type": MT.FRIEND_REQ_LIST})))
        br.addWidget(ac, 3)
        br.addSpacing(16)
        br.addWidget(rj, 1)
        lo.addLayout(br)
        self._req_l.addWidget(card)

    def _add_incoming_done(self, req, accepted):
        """已处理的收到的申请"""
        name = req.get("nickname") or req.get("username", "未知")
        label = "✓ 已同意" if accepted else "✗ 已拒绝"
        col = "#10B981" if accepted else C_RED
        bg = "#ECFDF5" if accepted else "#FFF1F2"

        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {C_BORDER};border-radius:16px;}}")
        lo = QHBoxLayout(card)
        lo.setContentsMargins(20, 16, 20, 16); lo.setSpacing(16)
        av = self._create_avatar(52, name[0], _AVATAR_COLORS[hash(name) % len(_AVATAR_COLORS)])
        lo.addWidget(av)
        tv = QVBoxLayout(); tv.setSpacing(6)
        nl = QLabel(name); nl.setStyleSheet(f"font-size:24px;font-weight:700;color:{C_DARK};background:transparent;border:none;")
        tv.addWidget(nl)
        sl = QLabel(label); sl.setStyleSheet(f"font-size:20px;color:{col};background:transparent;border:none;")
        tv.addWidget(sl)
        lo.addLayout(tv, 1)
        self._req_l.addWidget(card)

    def _add_outgoing(self, req):
        """发出的申请：已发送/已被拒绝/已同意"""
        name = req.get("nickname") or req.get("username", "目标用户")
        status = req.get("status", 0)
        if status == 1:
            label = "✓ 已同意"
            color = "#10B981"; bg = "#ECFDF5"
        elif status == 2:
            label = "✗ 已拒绝"
            color = C_RED; bg = "#FFF1F2"
        else:
            label = "⏳ 等待同意"
            color = "#F59E0B"; bg = "#FFFBEB"

        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {C_BORDER};border-radius:16px;}}")
        lo = QHBoxLayout(card)
        lo.setContentsMargins(20, 16, 20, 16); lo.setSpacing(16)
        av = self._create_avatar(52, name[0], "#A78BFA"); lo.addWidget(av)
        tv = QVBoxLayout(); tv.setSpacing(6)
        nl = QLabel(name); nl.setStyleSheet(f"font-size:24px;font-weight:700;color:{C_DARK};background:transparent;border:none;")
        tv.addWidget(nl)
        sl = QLabel(label); sl.setStyleSheet(f"font-size:20px;color:{color};background:transparent;border:none;")
        tv.addWidget(sl)
        lo.addLayout(tv, 1)
        self._req_l.addWidget(card)

    def _add_done(self, req):
        name = req.get("nickname") or req.get("username", "未知")
        w = QFrame(); lo = QHBoxLayout(w)
        lo.setContentsMargins(4, 8, 4, 8); lo.setSpacing(14)
        av = self._create_avatar(44, name[0], C_SUBTLE); lo.addWidget(av)
        tv = QVBoxLayout(); tv.setSpacing(3)
        tv.addWidget(QLabel(name)); tv.itemAt(0).widget().setStyleSheet(f"font-size:24px;font-weight:600;color:{C_DARK};")
        tv.addWidget(QLabel("已拒绝")); tv.itemAt(1).widget().setStyleSheet(f"font-size:22px;color:{C_SUBTLE};")
        lo.addLayout(tv, 1); self._req_l.addWidget(w)

    def _on_friend_rejected(self, msg):
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_group_create_resp(self, msg):
        if msg.get("ok"):
            self.app.main.switch_panel("chat")
            cp = self.app.panels.get("chat")
            if cp and hasattr(cp, '_select_target'): cp._select_target({"id": msg["group_id"], "name": msg["group_name"], "type": "room"})
            self.net.send({"type": MT.GROUP_LIST})
        else: QMessageBox.warning(self, "失败", msg.get("message", "创建群聊失败"))

    def _on_group_invited(self, msg):
        gid, gn = msg.get("group_id", ""), msg.get("group_name", "")
        if gid and gn:
            cp = self.app.panels.get("chat")
            if cp and hasattr(cp, '_my_groups') and not any(g["group_id"] == gid for g in cp._my_groups):
                cp._my_groups.append({"group_id": gid, "group_name": gn}); cp._refresh_list()
        self.net.send({"type": MT.GROUP_LIST})

    def _switch_to_chat(self, fid, fname):
        self.app.main.switch_panel("chat")
        cp = self.app.panels.get("chat")
        if cp and hasattr(cp, '_select_target'): cp._select_target({"id": fid, "name": fname, "type": "p2p"})

    def _on_friend_list(self, msg):
        self._friends = msg.get("friends", [])
        self.state.friends = self._friends
        self._refresh_list()
        self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_friend_remove_resp(self, msg):
        if msg.get("ok"): self.net.send({"type": MT.FRIEND_LIST}); self.net.send({"type": MT.FRIEND_REQ_LIST})

    def _on_user_list(self, msg):
        self.state.online_users = msg.get("online_users", [])
        self._refresh_list()
