import os
import base64
import time
import tempfile
import shutil
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QWidget, QProgressBar,
                             QFileDialog, QMessageBox, QLineEdit,
                             QGraphicsDropShadowEffect, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QCursor, QDragEnterEvent, QDropEvent
from common.messages import MT
from client.core.base_panel import BasePanel

# ── 自定义控件 ──────────────────────────────────────

class _NoPropagateScroll(QScrollArea):
    """滚轮事件不向父级冒泡的滚动区域"""
    def wheelEvent(self, event):
        vbar = self.verticalScrollBar()
        if vbar.isVisible():
            vbar.wheelEvent(event)
        event.accept()


class _DropZoneFrame(QFrame):
    """支持拖拽上传的文件拖放区"""

    def __init__(self, on_files, parent=None):
        super().__init__(parent)
        self._on_files = on_files
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "QFrame { border: 2px solid #2D6CF6; border-radius: 24px; "
                "background-color: #E7EFFC; }")

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            "QFrame { border: none; border-radius: 24px; "
            "background-color: #F5F8FF; }"
            "QFrame:hover { background-color: #EEF2FF; }")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            "QFrame { border: none; border-radius: 24px; "
            "background-color: #F5F8FF; }"
            "QFrame:hover { background-color: #EEF2FF; }")
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if os.path.isfile(p):
                paths.append(p)
        if paths:
            self._on_files(paths)


CHUNK_SIZE = 64 * 1024

# --- 严格还原 HTML 的颜色体系 ---
C_PRIMARY = "#2D6CF6"
C_GRAD_START = "#4F8DFD"
C_GRADIENT = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C_GRAD_START}, stop:1 {C_PRIMARY})"
C_SUCCESS = "#10B981"
C_SUCCESS_BG = "#F0FDF6"
C_DANGER = "#EF4444"
C_DANGER_BG = "#FEF2F2"
C_MUTED = "#94A3B8"
C_MUTED_LIGHT = "#CBD5E1"
C_DARK = "#1E293B"
C_TEXT_GRAY = "#475569"
C_TEXT_LIGHT = "#6B7A90"

_AVATAR_COLORS = [
    "#6366F1", "#FB923C", "#F472B6", "#34D399",
    "#A78BFA", "#FB7185", "#38BDF8", "#FBBF24",
    "#4ADE80", "#E879F9",
]

C_BG = "#EEF2FA"
C_LEFT_PANEL = "#F7F9FD"
C_CARD = "#ffffff"
C_BORDER = "#E5EAF3"
C_BLUE_BG = "#E7EFFC"
C_FILE_BG = "#F5F8FF"

_ICON_MAP = {
    ".pdf": ("📄", "#FEE2E2", "#DC2626"),
    ".doc": ("📝", "#DBEAFE", "#2563EB"), 
    ".docx":("📝", "#DBEAFE", "#2563EB"),
    ".xls": ("📊", "#F1F5F9", "#94A3B8"), 
    ".xlsx":("📊", "#F1F5F9", "#94A3B8"),
    ".zip": ("📦", "#FEF3C7", "#D97706"), 
    ".rar": ("📦", "#FEF3C7", "#D97706"),
    ".jpg": ("🖼", "#ECFDF5", "#10B981"), 
    ".png": ("🖼", "#ECFDF5", "#10B981"),
    ".md":  ("📋", "#F3EEFF", "#7C3AED"),
}

def apply_shadow(widget, blur_radius=12, y_offset=3, alpha=15):
    """为组件添加类似 CSS 的柔和阴影"""
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur_radius)
    shadow.setXOffset(0)
    shadow.setYOffset(y_offset)
    shadow.setColor(QColor(45, 108, 246, alpha))
    widget.setGraphicsEffect(shadow)

class FilePanel(BasePanel):

    def __init__(self, master, app):
        self._file_paths = []      # 待发送文件队列
        self._sending = False
        self._send_seq = 0
        self._send_total = 0
        self._send_file_id = None
        self._send_target_id = None
        self._send_target_name = None
        self._send_fh = None
        self._receiving = {}
        self._records = []
        self._filter = "全部"  # 全部 / 已完成 / 已失败
        super().__init__(master, app)

    def subscribe(self):
        self.net.on(MT.FILE_REQ, self._on_file_req)
        self.net.on(MT.FILE_RESP, self._on_file_resp)
        self.net.on(MT.FILE_DATA, self._on_file_data)
        self.net.on(MT.FILE_END, self._on_file_end)
        self.net.on("file_req_ack", self._on_file_req_ack)
        self.net.on("file_status", self._on_file_status)
        self.net.on(MT.USER_LIST, self._on_user_list_update)
        self._build_ui()

    # ══════════════════════════════════════════════════
    #  UI 布局 - 左右双栏结构
    # ══════════════════════════════════════════════════

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # 字体全局设置
        font = QFont("Noto Sans SC", 10)
        font.setStyleHint(QFont.SansSerif)
        self.setFont(font)

        # --- 左栏 (4) ---
        left_wrapper = QWidget()
        left_wrapper.setStyleSheet(
            f"background-color: {C_LEFT_PANEL}; border-right: 1px solid {C_BORDER};")
        left_layout = QVBoxLayout(left_wrapper)
        left_layout.setContentsMargins(8, 40, 8, 10)
        left_layout.setSpacing(0)

        left_layout.addWidget(self._build_left_header())

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        left_content = QWidget()
        left_content_ly = QVBoxLayout(left_content)
        left_content_ly.setContentsMargins(0, 0, 0, 24)
        left_content_ly.setSpacing(20)
        left_content_ly.addWidget(self._build_send_card())
        left_content_ly.addWidget(self._build_receive_section())
        left_content_ly.addWidget(self._build_active_section())
        left_content_ly.addStretch()
        left_scroll.setWidget(left_content)
        left_layout.addWidget(left_scroll)

        # --- 右栏 (6) ---
        right_wrapper = QWidget()
        right_wrapper.setStyleSheet(f"background-color: {C_BG}; border: none;")
        right_layout = QVBoxLayout(right_wrapper)
        right_layout.setContentsMargins(0, 40, 0, 0)
        right_layout.setSpacing(0)

        right_layout.addWidget(self._build_history_header())
        right_layout.addWidget(self._build_table_header())
        right_layout.addWidget(self._build_history_list(), 1)
        right_layout.addWidget(self._build_stats_bar())

        main.addWidget(left_wrapper, 3)
        main.addWidget(right_wrapper, 7)

        self._refresh_history()
        self._refresh_stats()

    # ══════════════════════════════════════════════════
    #  
    # ══════════════════════════════════════════════════

    def _build_left_header(self):
        w = QWidget()
        w.setFixedHeight(96)
        ly = QHBoxLayout(w)
        ly.setContentsMargins(54, 28, 22, 18)
        ly.addWidget(QLabel(
            "<span style='font-size:45px; font-weight:900; color:#1E293B;'>"
            "文件传输</span>"))
        ly.addStretch()
        return w

    def _build_send_card(self):
        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        ly = QVBoxLayout(wrapper)
        ly.setContentsMargins(22, 32, 26, 12)

        card = QFrame()
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        card.setStyleSheet(
            f"QFrame {{ background-color: {C_CARD}; border-radius: 20px; }}")
        apply_shadow(card, 18, 4, 22)

        c_ly = QVBoxLayout(card)
        c_ly.setContentsMargins(26, 30, 26, 30)
        c_ly.setSpacing(26)

        # "发送给" 标题 —— 固定高度
        send_to = QLabel(
            f"<span style='font-size:30px; font-weight:700; color:{C_TEXT_GRAY};'>"
            f"📤  发送给</span>")
        send_to.setFixedHeight(38)
        c_ly.addWidget(send_to)

        # 接收人选择框
        self._recip_btn = QPushButton("  👤  点击选择接收人")
        self._recip_btn.setFixedHeight(64)
        self._recip_btn.setCursor(Qt.PointingHandCursor)
        self._recip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #FAFBFD; border: 2px solid #E2E8F2;
                border-radius: 18px; font-size: 28px; color: {C_DARK};
                text-align: left; padding: 0 22px; font-weight: 500;
            }}
            QPushButton:hover {{ border: 2px solid {C_PRIMARY}; }}
        """)
        self._recip_btn.clicked.connect(self._toggle_recip_dropdown)
        c_ly.addWidget(self._recip_btn)

        # 接收人下拉列表（展开式）
        self._recip_dropdown = self._build_recip_dropdown()
        self._recip_dropdown.hide()
        c_ly.addWidget(self._recip_dropdown)

        # 拖拽区 —— 最小220px，最大380px
        self._drop_zone = _DropZoneFrame(self._on_files_dropped)
        self._drop_zone.setCursor(Qt.PointingHandCursor)
        self._drop_zone.setMinimumHeight(260)
        self._drop_zone.setMaximumHeight(420)
        self._drop_zone.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._drop_zone.setStyleSheet(
            f"QFrame {{ border: none; border-radius: 24px; "
            f"background-color: {C_FILE_BG}; }}"
            f"QFrame:hover {{ background-color: #EEF2FF; }}")
        dz_ly = QVBoxLayout(self._drop_zone)
        dz_ly.setContentsMargins(0, 0, 0, 0)
        dz_ly.setAlignment(Qt.AlignCenter)
        dz_ly.setSpacing(12)

        dz_ly.addWidget(QLabel(
            "<div style='font-size:64px; color:#2D6CF6; text-align:center;'>📁</div>"))
        dz_ly.addWidget(QLabel(
            "<div style='font-size:28px; font-weight:600; color:#475569; "
            "text-align:center;'>拖拽文件到此处</div>"))
        dz_ly.addWidget(QLabel(
            "<div style='font-size:22px; color:#94A3B8; text-align:center;'>"
            "或 <span style='color:#2D6CF6; font-weight:600;'>点击选择多个文件</span></div>"))
        self._drop_zone.mousePressEvent = lambda e: self._pick_file()
        c_ly.addWidget(self._drop_zone)

        # 文件列表 —— 直接撑开高度，由外层 left_scroll 统一滚动
        self._file_list_widget = QWidget()
        self._file_list_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._file_list_layout = QVBoxLayout(self._file_list_widget)
        self._file_list_layout.setContentsMargins(0, 0, 0, 0)
        self._file_list_layout.setSpacing(6)
        self._file_list_layout.setAlignment(Qt.AlignTop)

        self._file_list_widget.hide()
        c_ly.addWidget(self._file_list_widget)

        # 发送按钮
        self._send_btn = QPushButton("📤  发送文件")
        self._send_btn.setFixedHeight(68)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_GRADIENT}; color: white; border: none;
                border-radius: 20px; font-size: 24px; font-weight: 700;
            }}
            QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6098FD, stop:1 #3B7FED); }}
            QPushButton:disabled {{ background: #CBD5E1; color: #94A3B8; }}
        """)
        apply_shadow(self._send_btn, 28, 12, 90)
        self._send_btn.clicked.connect(self._select_and_send)
        c_ly.addWidget(self._send_btn)

        ly.addWidget(card)
        return wrapper

    def _build_active_section(self):
        self._active_section = QWidget()
        ly = QVBoxLayout(self._active_section)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(10)

        title_w = QWidget()
        title_ly = QHBoxLayout(title_w)
        title_ly.setContentsMargins(16, 4, 16, 0)
        title_ly.addWidget(QLabel(
            f"<span style='font-size:30px; font-weight:700; color:{C_TEXT_GRAY};'>"
            f"📥  传输中</span>"))

        self._active_badge = QLabel("0")
        self._active_badge.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {C_PRIMARY}; "
            f"background-color: {C_BLUE_BG}; padding: 4px 14px; border-radius: 13px;")
        title_ly.addWidget(self._active_badge)
        title_ly.addStretch()
        ly.addWidget(title_w)

        self._active_list = QVBoxLayout()
        self._active_list.setContentsMargins(16, 0, 16, 0)
        self._active_list.setSpacing(10)
        ly.addLayout(self._active_list)
        
        self._active_section.hide()
        return self._active_section

    # ══════════════════════════════════════════════════
    #  右栏组件
    # ══════════════════════════════════════════════════

    def _build_receive_section(self):
        """接收区 —— 等待确认的文件"""
        self._receive_section = QWidget()
        ly = QVBoxLayout(self._receive_section)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(10)

        title_w = QWidget()
        title_ly = QHBoxLayout(title_w)
        title_ly.setContentsMargins(16, 4, 16, 0)
        title_ly.addWidget(QLabel(
            f"<span style='font-size:22px; font-weight:700; color:{C_TEXT_GRAY};'>"
            f"📥  待接收</span>"))
        self._receive_badge = QLabel("0")
        self._receive_badge.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {C_SUCCESS}; "
            f"background-color: {C_SUCCESS_BG}; padding: 2px 12px; "
            f"border-radius: 11px;")
        title_ly.addWidget(self._receive_badge)
        title_ly.addStretch()
        ly.addWidget(title_w)

        self._receive_list = QVBoxLayout()
        self._receive_list.setContentsMargins(16, 0, 16, 0)
        self._receive_list.setSpacing(8)
        ly.addLayout(self._receive_list)

        self._receive_section.hide()
        return self._receive_section

    def _build_history_header(self):
        w = QFrame()
        w.setFixedHeight(96)
        w.setStyleSheet(f"QFrame {{ background-color: transparent; border: none; }}")
        lo = QHBoxLayout(w)
        lo.setContentsMargins(56, 28, 56, 18)
        lo.setSpacing(24)
        lo.setAlignment(Qt.AlignVCenter)

        lo.addWidget(QLabel(
            f"<span style='font-size:38px; font-weight:800; color:{C_DARK};'>"
            f"传输记录</span>"))

        lo.addStretch()

        # 筛选标签 —— 位于搜索框左侧
        self._filter_tags = {}
        for label in ("全部", "已完成", "已失败"):
            tag = QLabel(label)
            tag.setContentsMargins(24, 10, 24, 10)
            tag.setCursor(Qt.PointingHandCursor)
            tag.mousePressEvent = lambda e, l=label: self._set_filter(l)
            self._filter_tags[label] = tag
            lo.addWidget(tag)

        lo.addSpacing(20)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍  搜索文件名")
        self._search_box.setFixedHeight(56)
        self._search_box.setFixedWidth(280)
        self._search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C_CARD}; border: none; border-radius: 20px;
                font-size: 24px; color: {C_DARK}; padding: 0 22px;
            }}
            QLineEdit::placeholder {{ color: #B0BAC8; }}
        """)
        apply_shadow(self._search_box, 8, 2, 18)
        self._search_box.textChanged.connect(self._on_search)
        lo.addWidget(self._search_box)

        self._update_filter_tags()
        return w

    def _build_table_header(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lo = QHBoxLayout(w)
        lo.setContentsMargins(66, 18, 66, 14)
        lo.setSpacing(0)

        style = f"font-size: 22px; font-weight: 700; color: {C_MUTED};"

        l1 = QLabel("文件"); l1.setFixedWidth(620); l1.setStyleSheet(style); lo.addWidget(l1)
        l2 = QLabel("方向"); l2.setFixedWidth(240); l2.setStyleSheet(style); lo.addWidget(l2)
        l3 = QLabel("大小"); l3.setFixedWidth(165); l3.setStyleSheet(style); lo.addWidget(l3)
        l4 = QLabel("时间"); l4.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); l4.setStyleSheet(style); lo.addWidget(l4)
        l5 = QLabel("状态"); l5.setFixedWidth(160); l5.setStyleSheet(style); l5.setAlignment(Qt.AlignRight | Qt.AlignVCenter); lo.addWidget(l5)
        return w

    def _build_history_list(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: rgba(100,116,139,.22); border-radius: 3px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        self._history_content = QWidget()
        self._history_content.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(40, 4, 40, 16)
        self._history_layout.setSpacing(10)
        self._history_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(self._history_content)
        return scroll

    def _build_stats_bar(self):
        bar = QFrame()
        bar.setFixedHeight(72)
        bar.setStyleSheet(
            f"QFrame {{ background-color: {C_LEFT_PANEL}; "
            f"border-top: 1px solid {C_BORDER}; "
            f"border-bottom: none; border-left: none; border-right: none; }}")
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(54, 0, 54, 0)
        lo.setSpacing(36)

        self._stat_active = self._stat("传输中", "0 项")
        self._stat_done = self._stat("已完成", "0 项")
        self._stat_fail = self._stat("失败", "0 项")
        
        lo.addWidget(self._stat_active)
        lo.addWidget(self._stat_done)
        lo.addWidget(self._stat_fail)
        lo.addStretch()
        return bar

    def _stat(self, label, value):
        w = QWidget()
        lo = QHBoxLayout(w)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)
        lo.addWidget(QLabel(
            f"<span style='font-size:22px; color:{C_TEXT_LIGHT};'>"
            f"{label} <strong style='color:{C_DARK};'>{value}</strong></span>"))
        return w

    # ══════════════════════════════════════════════════
    #  逻辑与 UI 更新
    # ══════════════════════════════════════════════════

    def _set_filter(self, label):
        self._filter = label
        self._update_filter_tags()
        self._refresh_history()

    def _update_filter_tags(self):
        for label, tag in self._filter_tags.items():
            if label == self._filter:
                tag.setStyleSheet(
                    f"font-size: 24px; color: #fff; font-weight: 700; "
                    f"background-color: {C_PRIMARY}; border-radius: 16px;")
            else:
                tag.setStyleSheet(
                    f"font-size: 24px; color: {C_TEXT_LIGHT}; "
                    f"background-color: #E2E8F0; border-radius: 16px;")

    def _on_search(self, text):
        self._refresh_history()

    def _on_user_list_update(self, _):
        pass

    def _build_recip_dropdown(self):
        """构建接收人展开式下拉列表"""
        w = QFrame()
        w.setMinimumHeight(240)
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        w.setStyleSheet(f"""
            QFrame {{ background-color: {C_CARD}; border: 1px solid {C_BORDER};
                     border-radius: 16px; }}
        """)

        ly = QVBoxLayout(w)
        ly.setContentsMargins(10, 10, 10, 10)
        ly.setSpacing(6)

        # 搜索
        self._recip_search = QLineEdit()
        self._recip_search.setPlaceholderText("🔍  搜索联系人…")
        self._recip_search.setFixedHeight(50)
        self._recip_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C_FILE_BG}; border: none;
                border-radius: 14px; font-size: 21px;
                color: {C_DARK}; padding: 0 22px;
            }}
        """)
        self._recip_search.textChanged.connect(self._refresh_recip_items)
        ly.addWidget(self._recip_search)

        # 列表 —— 拦截滚轮事件防止冒泡到外层 left_scroll
        scroll = _NoPropagateScroll()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; }
            QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self._recip_list_content = QWidget()
        self._recip_list_layout = QVBoxLayout(self._recip_list_content)
        self._recip_list_layout.setContentsMargins(14, 10, 14, 14)
        self._recip_list_layout.setSpacing(8)
        self._recip_list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._recip_list_content)
        ly.addWidget(scroll, 1)

        return w

    def _toggle_recip_dropdown(self):
        if self._recip_dropdown.isVisible():
            self._recip_dropdown.hide()
        else:
            self._recip_search.clear()
            self._refresh_recip_items()
            self._recip_dropdown.show()

    def _refresh_recip_items(self, _=None):
        """刷新下拉用户列表"""
        while self._recip_list_layout.count():
            c = self._recip_list_layout.takeAt(0)
            if c.widget(): c.widget().deleteLater()

        keyword = self._recip_search.text().strip().lower()
        users = [u for u in self.app.state.online_users
                 if u.get("user_id") != self.app.state.user_id]
        if keyword:
            users = [u for u in users if keyword in (
                u.get("nickname") or u.get("username", "")).lower()]

        if not users:
            empty = QLabel("暂无匹配用户")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"font-size: 22px; color: {C_MUTED}; padding: 32px;")
            self._recip_list_layout.addWidget(empty)
            self._recip_list_layout.addStretch()
            return

        for u in users:
            uid = u["user_id"]
            nm = u.get("nickname") or u.get("username", "")
            uname = u.get("username", "")
            avatar_char = nm[0] if nm else "?"
            color = _AVATAR_COLORS[hash(uid) % len(_AVATAR_COLORS)]

            row = QPushButton()
            row.setFixedHeight(60)
            row.setCursor(Qt.PointingHandCursor)
            row.setStyleSheet(f"""
                QPushButton {{ background: transparent; border: none;
                               border-radius: 14px; text-align: left; }}
                QPushButton:hover {{ background-color: {C_FILE_BG}; }}
            """)
            row.clicked.connect(lambda checked, n=nm, i=uid: (
                self._on_recip(n, i), self._recip_dropdown.hide()))

            r_ly = QHBoxLayout(row)
            r_ly.setContentsMargins(14, 0, 14, 0)
            r_ly.setSpacing(16)

            av = QLabel(avatar_char)
            av.setFixedSize(42, 42)
            av.setAlignment(Qt.AlignCenter)
            av.setStyleSheet(f"""
                background-color: {color}; color: white;
                border-radius: 16px; font-size: 22px; font-weight: 700;
            """)
            r_ly.addWidget(av)

            name_lbl = QLabel(nm)
            name_lbl.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {C_DARK};")
            r_ly.addWidget(name_lbl, 1)

            status = QLabel("● 在线")
            status.setStyleSheet(f"font-size: 16px; color: {C_SUCCESS};")
            r_ly.addWidget(status)

            self._recip_list_layout.addWidget(row)
        self._recip_list_layout.addStretch()

    def _on_recip(self, name, uid):
        self._send_target_id = uid
        self._send_target_name = name
        self._recip_btn.setText(f"  👤  {name}")
        self._recip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_CARD}; border: 2px solid {C_PRIMARY};
                border-radius: 18px; font-size: 28px; color: {C_DARK};
                text-align: left; padding: 0 22px; font-weight: 600;
            }}
        """)
        self._update_send_btn()

    def _update_send_btn(self):
        n = len(self._file_paths)
        if self._send_target_name and n:
            total = sum(os.path.getsize(p) for p in self._file_paths)
            label = f"📤  发送给 {self._send_target_name}"
            if n > 1:
                label += f"（{n} 个文件，{self._fmt(total)}）"
            else:
                label += f"（{self._fmt(total)}）"
            self._send_btn.setText(label)
            self._send_btn.setEnabled(True)
        else:
            self._send_btn.setText("📤  发送文件")

    def _on_files_dropped(self, paths):
        """拖拽文件——批量追加"""
        self._add_files(paths)

    def _pick_file(self, event=None):
        """点击选择文件——Windows 原生多选"""
        if self._sending:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文件（可多选）", "", "所有文件 (*.*)")
        if paths:
            self._add_files(paths)

    def _add_files(self, paths):
        """追加文件到列表（去重）"""
        added = False
        for p in paths:
            if p not in self._file_paths:
                self._file_paths.append(p)
                added = True
        if added:
            self._refresh_file_list()
            self._update_send_btn()

    def _remove_file(self, path):
        """从列表移除单个文件"""
        if path in self._file_paths:
            self._file_paths.remove(path)
        self._refresh_file_list()
        self._update_send_btn()

    def _clear_file(self):
        self._file_paths.clear()
        self._refresh_file_list()
        self._update_send_btn()

    def _refresh_file_list(self):
        """刷新文件列表 UI — 内容直接撑开，外层 left_scroll 统一滚动"""
        while self._file_list_layout.count():
            c = self._file_list_layout.takeAt(0)
            if c.widget():
                c.widget().deleteLater()

        if not self._file_paths:
            self._file_list_widget.hide()
            return

        self._file_list_widget.show()
        for path in self._file_paths:
            self._file_list_layout.addWidget(self._create_file_item(path))

    def _create_file_item(self, path):
        """单行文件条目"""
        item = QFrame()
        item.setFixedHeight(60)
        item.setStyleSheet(
            f"QFrame {{ background-color: {C_FILE_BG}; border-radius: 18px; }}")

        lo = QHBoxLayout(item)
        lo.setContentsMargins(14, 10, 14, 10)
        lo.setSpacing(12)

        n = os.path.basename(path)
        ext = os.path.splitext(n)[1].lower()
        icon, bg, _ = _ICON_MAP.get(ext, ("📎", "#DBEAFE", C_MUTED))

        ic = QLabel(icon)
        ic.setFixedSize(38, 38)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(
            f"background-color: {bg}; border-radius: 12px; font-size: 20px;")
        lo.addWidget(ic)

        name_lbl = QLabel(n)
        name_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 600; color: {C_DARK};")
        lo.addWidget(name_lbl, 1)

        sz_lbl = QLabel(self._fmt(os.path.getsize(path)))
        sz_lbl.setStyleSheet(f"font-size: 18px; color: {C_MUTED};")
        lo.addWidget(sz_lbl)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(32, 32)
        rm_btn.setCursor(Qt.PointingHandCursor)
        rm_btn.setStyleSheet(
            "QPushButton { background-color: #FEE2E2; color: #EF4444; "
            "border: none; border-radius: 10px; font-weight: 800; font-size: 15px; }"
            "QPushButton:hover { background-color: #FECACA; }")
        rm_btn.clicked.connect(lambda: self._remove_file(path))
        lo.addWidget(rm_btn)

        return item

    def _select_and_send(self):
        if self._sending:
            return
        if not self._send_target_id:
            QMessageBox.warning(self, "提示", "请先选择接收人")
            return
        if not self._file_paths:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return

        self._sending = True
        self._send_btn.setEnabled(False)
        self._send_btn.setText("📤  发送中...")
        self._send_next_file()

    def _send_next_file(self):
        """从队列取出下一个文件发送"""
        if not self._file_paths:
            self._sending = False
            self._send_btn.setEnabled(True)
            self._send_btn.setText("📤  发送文件")
            return

        path = self._file_paths.pop(0)
        n = os.path.basename(path)
        s = os.path.getsize(path)
        self._send_file_id = None
        self._current_file_path = path
        self.net.send({"type": MT.FILE_REQ, "to": self._send_target_id,
                       "file_name": n, "file_size": s})
        self._add_record(n, s, self._send_target_name, "发送给", 0,
                         "sending", time.strftime("%m-%d %H:%M"),
                         fid=None)
        # 等服务端 ACK → _on_file_req_ack → _start_send_chunks

    def _start_send_chunks(self):
        path = getattr(self, '_current_file_path', None)
        if not path:
            return
        try:
            self._send_fh = open(path, "rb")
        except OSError:
            self._update_status("读取失败")
            self._send_next_file()
            return
        self._send_seq = 0
        self._send_total = (os.path.getsize(path) + CHUNK_SIZE - 1) // CHUNK_SIZE
        self._update_progress(0, "sending")
        self._send_next_chunk()

    def _send_next_chunk(self):
        """逐块发送，每 20 块让出 GUI 事件循环"""
        if not self._send_fh:
            return
        for _ in range(20):
            d = self._send_fh.read(CHUNK_SIZE)
            if not d:
                self._send_fh.close()
                self._send_fh = None
                self._update_progress(100, "done")
                self.net.send({"type": MT.FILE_END, "to": self._send_target_id,
                               "file_id": self._send_file_id, "status": 1})
                QTimer.singleShot(0, self._send_next_file)
                return
            self.net.send({"type": MT.FILE_DATA, "to": self._send_target_id,
                           "file_id": self._send_file_id, "seq": self._send_seq,
                           "data": base64.b64encode(d).decode("ascii")})
            self._send_seq += 1
            pct = min(int(self._send_seq / self._send_total * 100), 99)
            self._update_progress(pct, "sending")
        # 让出 GUI 再继续
        QTimer.singleShot(0, self._send_next_chunk)

    def _reset_send(self):
        self._sending = False
        self._send_btn.setEnabled(True)
        self._update_send_btn()

    def _receive_to_temp(self, msg):
        """收到文件通知 → 仅记录，不创建文件。
        数据由服务端缓冲，用户确认后才从服务端拉取。"""
        nm = msg.get("file_name", "未知")
        sz = msg.get("file_size", 0)
        fid = msg.get("from")
        fn = str(fid)
        for u in self.app.state.online_users:
            if u.get("user_id") == fid:
                fn = u.get("nickname") or u.get("username", "")
                break

        # 仅记录，等用户确认后再接收数据
        self._add_record(nm, sz, fn, "接收自", 0, "received",
                         time.strftime("%m-%d %H:%M"),
                         fid=msg["file_id"])

    def _accept_received(self, file_id):
        """用户确认接受 → 选路径 → 准备接收 → 通知服务端开始发送"""
        # 获取记录信息
        rec = None
        for r in self._records:
            if r.get("_file_id") == file_id and r["status"] == "received":
                rec = r
                break
        if not rec:
            return

        sp, _ = QFileDialog.getSaveFileName(
            self, "保存文件", rec["file_name"], "所有 (*.*)")
        if not sp:
            return

        # 准备接收缓冲区
        try:
            fh = open(sp, "wb")
        except OSError:
            QMessageBox.warning(self, "错误", "无法创建文件")
            return

        self._receiving[file_id] = {
            "file_name": rec["file_name"], "file_size": rec["file_size"],
            "received": 0, "save_path": sp, "fh": fh,
        }
        self._update_status_for(file_id, "receiving")

        self.net.send({"type": "file_accept", "file_id": file_id,
                       "accept": True})

    def _reject_received(self, file_id):
        """拒绝接收 → 通知服务端清理"""
        self.net.send({"type": "file_accept", "file_id": file_id,
                       "accept": False})
        self._update_status_for(file_id, "已拒绝")

    def _update_status_for(self, file_id, status):
        """按 file_id 更新记录状态"""
        for r in self._records:
            if r.get("_file_id") == file_id:
                r["progress"] = 100
                r["status"] = status
                break
        self._refresh()

    def _on_file_req_ack(self, m):
        """服务端回传 file_id → 关联记录 + 开始发送"""
        self._send_file_id = m["file_id"]
        # 把 file_id 关联到发送方的记录上
        for r in self._records:
            if r.get("direction") == "发送给" and r["status"] == "sending" \
                    and r.get("_file_id") is None:
                r["_file_id"] = m["file_id"]
                break
        self._start_send_chunks()

    def _on_file_status(self, m):
        """对方接受/拒绝 → 同步发送方状态"""
        fid = m.get("file_id")
        st = m.get("status")
        for r in self._records:
            if r.get("_file_id") == fid and r.get("direction") == "发送给":
                r["status"] = "已接受" if st == "accepted" else "已拒绝"
                self._refresh()
                break

    def _on_file_req(self, m):
        self._receive_to_temp(m)

    def _on_file_resp(self, m):
        pass  # 不再需要握手确认

    def _on_file_data(self, m):
        fid = m.get("file_id")
        b = self._receiving.get(fid)
        if not b:
            return
        try: raw = base64.b64decode(m.get("data", ""))
        except Exception: return
        try: b["fh"].write(raw)
        except OSError:
            b["fh"].close()
            self._receiving.pop(fid, None)
            self._update_status_for(fid, "写入失败")
            return
        b["received"] += len(raw)
        
        # 精确更新对应的接收记录
        for r in self._records:
            if r.get("_file_id") == fid:
                r["progress"] = min(int(b["received"] / b["file_size"] * 100), 99) if b["file_size"] else 0
                break
        self._refresh()

    def _on_file_end(self, m):
        fid = m.get("file_id")
        st = m.get("status", 1)
        
        # BUG FIX: 这里原本使用了 pop()，导致数据直接从内存丢失。现改为 get()。
        b = self._receiving.get(fid)
        if b:
            b["fh"].close()
            if st == 1:
                # 接收完成
                self._update_status_for(fid, "done")
            else:
                self._receiving.pop(fid, None) # 传输明确失败了才清理掉
                self._update_status_for(fid, "传输失败")
                try:
                    os.remove(b["save_path"])
                except OSError:
                    pass
            return
            
        self._update_status("已完成" if st == 1 else "传输失败")

    def _add_record(self, nm, sz, sender, direction, progress, status, tm,
                    fid=None):
        self._records.append({"file_name": nm, "size_str": self._fmt(sz),
                              "file_size": sz, "sender": sender,
                              "direction": direction, "progress": progress,
                              "status": status, "time": tm, "_file_id": fid})
        self._refresh()

    def _update_progress(self, p, s):
        if self._records:
            self._records[-1]["progress"] = p
            self._records[-1]["status"] = s
        self._refresh()

    def _update_status(self, s):
        if self._records: self._records[-1]["status"] = s
        self._refresh()

    def _refresh(self):
        self._refresh_active()
        self._refresh_receive()
        self._refresh_history()
        self._refresh_stats()

    # ── 左侧传输中卡片 ──
    def _refresh_active(self):
        while self._active_list.count():
            c = self._active_list.takeAt(0)
            if c.widget(): c.widget().deleteLater()
            
        active = [r for r in self._records if r["status"] in ("sending", "receiving", "waiting")]
        self._active_badge.setText(str(len(active)))
        if active:
            self._active_section.show()
            for r in active: self._active_list.addWidget(self._create_active_item(r))
        else:
            self._active_section.hide()

    def _create_active_item(self, r):
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {C_CARD}; border-radius: 18px; }}")
        apply_shadow(card, 12, 3, 18)
        ly = QVBoxLayout(card)
        ly.setContentsMargins(18, 16, 18, 16)
        ly.setSpacing(10)

        row = QHBoxLayout()
        ext = os.path.splitext(r["file_name"])[1].lower()
        icon, bg, _ = _ICON_MAP.get(ext, ("📎", "#F1F5F9", C_MUTED))
        ic = QLabel(icon)
        ic.setFixedSize(60, 60)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(
            f"background-color: {bg}; border-radius: 18px; font-size: 32px;")
        row.addWidget(ic)

        tc = QVBoxLayout()
        tc.setSpacing(6)

        name_lbl = QLabel(r['file_name'])
        name_lbl.setStyleSheet(
            f"font-size: 30px; font-weight: 600; color: {C_DARK};")
        tc.addWidget(name_lbl)

        dir_lbl = QLabel(f"{r['direction']} {r['sender']} · {r['size_str']}")
        dir_lbl.setStyleSheet(f"font-size: 22px; color: {C_MUTED};")
        tc.addWidget(dir_lbl)
        row.addLayout(tc, 1)

        pa = QPushButton("✕")
        pa.setFixedSize(44, 44)
        pa.setStyleSheet(
            f"QPushButton {{ background-color: {C_DANGER_BG}; color: {C_DANGER}; "
            "border: none; border-radius: 15px; font-weight: 800; font-size: 20px; }}"
            "QPushButton:hover { background-color: #FECACA; }")
        row.addWidget(pa)
        ly.addLayout(row)

        pb = QProgressBar()
        pb.setFixedHeight(14)
        pb.setValue(r["progress"])
        pb.setTextVisible(False)
        pb.setStyleSheet(
            "QProgressBar { background-color: #EDF1F8; border: none; "
            "border-radius: 7px; } "
            "QProgressBar::chunk { "
            f"background: {C_GRADIENT}; border-radius: 7px; }}")
        ly.addWidget(pb)

        dr = QHBoxLayout()
        dr.setContentsMargins(0, 0, 0, 0)
        dr.addWidget(QLabel(
            f"<span style='font-size:24px; font-weight:700; color:{C_PRIMARY};'>"
            f"{r['progress']}%</span>"))
        dr.addStretch()
        done = int(r["file_size"] * r["progress"] / 100) if r["file_size"] else 0
        dr.addWidget(QLabel(
            f"<span style='font-size:22px; color:{C_MUTED};'>"
            f"{self._fmt(done)} / {r['size_str']}</span>"))
        ly.addLayout(dr)
        return card

    # ── 右侧历史记录条目 ──
    # ── 接收区 ──

    def _refresh_receive(self):
        while self._receive_list.count():
            c = self._receive_list.takeAt(0)
            if c.widget():
                c.widget().deleteLater()

        waiting = [r for r in self._records if r["status"] == "received"]
        self._receive_badge.setText(str(len(waiting)))
        if waiting:
            self._receive_section.show()
            for r in waiting:
                self._receive_list.addWidget(self._create_receive_item(r))
        else:
            self._receive_section.hide()

    def _create_receive_item(self, r):
        """接收区条目 —— 显示文件信息 + 接受/拒绝按钮"""
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #fff; border-radius: 18px; }")
        apply_shadow(card, 10, 2, 15)
        ly = QVBoxLayout(card)
        ly.setContentsMargins(18, 14, 18, 14)
        ly.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(14)
        ext = os.path.splitext(r["file_name"])[1].lower()
        icon, bg, _ = _ICON_MAP.get(ext, ("📎", "#F1F5F9", C_MUTED))
        ic = QLabel(icon)
        ic.setFixedSize(44, 44)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(
            f"background-color: {bg}; border-radius: 14px; font-size: 22px;")
        row.addWidget(ic)

        tc = QVBoxLayout()
        tc.setSpacing(3)
        tc.addWidget(QLabel(
            f"<span style='font-size:20px; font-weight:600; color:#1E293B;'>"
            f"{r['file_name']}</span>"))
        tc.addWidget(QLabel(
            f"<span style='font-size:16px; color:#94A3B8;'>"
            f"来自 {r['sender']} · {r['size_str']}</span>"))
        row.addLayout(tc, 1)
        ly.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        fid = r.get("_file_id")

        accept = QPushButton("✓  接受")
        accept.setFixedHeight(38)
        accept.setCursor(Qt.PointingHandCursor)
        accept.setStyleSheet(
            "QPushButton { background-color: #F0FDF6; color: #10B981; "
            "border: none; border-radius: 12px; font-size: 17px; "
            "font-weight: 700; }"
            "QPushButton:hover { background-color: #D1FAE5; }")
        accept.clicked.connect(
            lambda checked, f=fid: self._accept_received(f))
        btn_row.addWidget(accept, 1)

        reject = QPushButton("✕  拒绝")
        reject.setFixedHeight(38)
        reject.setCursor(Qt.PointingHandCursor)
        reject.setStyleSheet(
            "QPushButton { background-color: #FEF2F2; color: #EF4444; "
            "border: none; border-radius: 12px; font-size: 17px; "
            "font-weight: 700; }"
            "QPushButton:hover { background-color: #FEE2E2; }")
        reject.clicked.connect(
            lambda checked, f=fid: self._reject_received(f))
        btn_row.addWidget(reject, 1)
        ly.addLayout(btn_row)

        return card

    def _refresh_history(self):
        while self._history_layout.count():
            c = self._history_layout.takeAt(0)
            if c.widget(): c.widget().deleteLater()

        filtered = [r for r in self._records
                    if r["status"] not in ("sending", "receiving", "waiting")]
        if self._filter == "已完成":
            filtered = [r for r in filtered
                        if r["status"] in ("done", "已完成", "已接受")]
        elif self._filter == "已失败":
            filtered = [r for r in filtered
                        if "失败" in r["status"] or "拒绝" in r["status"]]

        search_text = self._search_box.text().strip()
        if search_text: filtered = [r for r in filtered if search_text.lower() in r["file_name"].lower()]

        if filtered:
            # 倒序显示，最新的在最上
            for r in reversed(filtered): self._history_layout.addWidget(self._create_history_item(r))
        else:
            empty = QLabel("暂无记录")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"font-size: 28px; color: {C_MUTED}; font-weight: 500; "
                f"padding: 80px; background-color: {C_CARD}; border-radius: 22px;")
            self._history_layout.addWidget(empty)
        self._history_layout.addStretch()

    def _create_history_item(self, r):
        row = QFrame()
        row.setFixedHeight(110)

        opacity_style = "opacity: 0.7;" if "失败" in r["status"] or "拒绝" in r["status"] else ""
        row.setStyleSheet(
            f"QFrame {{ background-color: {C_CARD}; border-radius: 18px; "
            f"{opacity_style} }}")
        apply_shadow(row, 8, 2, 12)

        lo = QHBoxLayout(row)
        lo.setContentsMargins(36, 0, 36, 0)
        lo.setAlignment(Qt.AlignVCenter)
        lo.setSpacing(0)

        # 列1: 文件 (280px)
        col1 = QWidget(); col1.setFixedWidth(620)
        ly1 = QHBoxLayout(col1); ly1.setContentsMargins(0,0,10,0); ly1.setSpacing(12)
        ext = os.path.splitext(r["file_name"])[1].lower()
        icon, bg, _ = _ICON_MAP.get(ext, ("📎", "#F1F5F9", C_MUTED))
        ic = QLabel(icon)
        ic.setFixedSize(52, 52)
        ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(
            f"background-color: {bg}; border-radius: 16px; font-size: 26px;")
        ly1.addWidget(ic)

        info = QVBoxLayout(); info.setSpacing(4); info.setAlignment(Qt.AlignVCenter)
        nm_lbl = QLabel(r['file_name'])
        nm_lbl.setStyleSheet(
            f"font-size: 26px; font-weight: 600; color: {C_DARK};")
        nm_lbl.setWordWrap(False)
        info.addWidget(nm_lbl)
        type_lbl = QLabel(f"{ext[1:].upper()} 文件" if ext else "未知文件")
        type_lbl.setStyleSheet(f"font-size: 18px; color: {C_MUTED};")
        info.addWidget(type_lbl)
        ly1.addLayout(info, 1)
        lo.addWidget(col1)

        # 列2: 方向 (160px)
        col2 = QWidget(); col2.setFixedWidth(240)
        ly2 = QHBoxLayout(col2); ly2.setContentsMargins(0,0,0,0); ly2.setSpacing(8)
        dir_bg = C_SUCCESS_BG if r["direction"] == "接收自" else C_BLUE_BG
        dir_color = C_SUCCESS if r["direction"] == "接收自" else C_PRIMARY
        dir_ic = QLabel("↓" if r["direction"] == "接收自" else "↑")
        dir_ic.setFixedSize(36, 36)
        dir_ic.setAlignment(Qt.AlignCenter)
        dir_ic.setStyleSheet(
            f"background-color: {dir_bg}; color: {dir_color}; "
            "border-radius: 18px; font-weight: 900; font-size: 18px;")
        ly2.addWidget(dir_ic)

        d_info = QVBoxLayout(); d_info.setSpacing(3); d_info.setAlignment(Qt.AlignVCenter)
        d_info.addWidget(QLabel(
            f"<span style='font-size:18px; color:{C_TEXT_LIGHT};'>{r['direction']}</span>"))
        d_info.addWidget(QLabel(
            f"<span style='font-size:20px; font-weight:600; color:{C_DARK};'>{r['sender']}</span>"))
        ly2.addLayout(d_info, 1)
        lo.addWidget(col2)

        # 列3: 大小 (110px)
        sz_lbl = QLabel(r['size_str'])
        sz_lbl.setFixedWidth(165)
        sz_lbl.setStyleSheet(f"font-size: 20px; color: {C_TEXT_LIGHT};")
        lo.addWidget(sz_lbl)

        # 列4: 时间 (Flex)
        tm_lbl = QLabel(r['time'])
        tm_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tm_lbl.setStyleSheet(f"font-size: 18px; color: {C_MUTED};")
        lo.addWidget(tm_lbl)

        # 列5: 状态
        st_w = QWidget(); st_w.setFixedWidth(160)
        st_ly = QHBoxLayout(st_w); st_ly.setContentsMargins(0, 0, 0, 0)
        st_ly.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        if r["status"] in ("done", "已完成"):
            if r.get("direction") == "发送给":
                bg, clr, txt = C_BLUE_BG, C_PRIMARY, "📤 已发送"
            else:
                bg, clr, txt = C_SUCCESS_BG, C_SUCCESS, "✅ 已接受"
        elif r["status"] == "已接受":
            bg, clr, txt = C_SUCCESS_BG, C_SUCCESS, "✅ 已接受"
        elif r["status"] == "已拒绝":
            bg, clr, txt = C_DANGER_BG, C_DANGER, "❌ 已拒绝"
        elif r["status"] == "received":
            bg, clr, txt = C_BLUE_BG, C_PRIMARY, "📥 待接收"
        elif "失败" in r["status"] or "拒绝" in r["status"]:
            bg, clr, txt = C_DANGER_BG, C_DANGER, "❌ 失败"
        else:
            bg, clr, txt = C_BLUE_BG, C_PRIMARY, r["status"]

        badge = QLabel(txt)
        badge.setContentsMargins(16, 7, 16, 7)
        badge.setStyleSheet(
            f"font-size: 18px; font-weight: 600; color: {clr}; "
            f"background-color: {bg}; border-radius: 14px;")
        st_ly.addWidget(badge)
        lo.addWidget(st_w)

        return row

    def _refresh_stats(self):
        def cnt(*ss): return str(sum(1 for r in self._records if r["status"] in ss))
        for w, label, *ss in [
            (self._stat_active,  "传输中", "sending", "receiving", "waiting"),
            (self._stat_done,    "已完成", "done", "已完成", "已接受"),
            (self._stat_fail,    "失败",   "写入失败", "读取失败", "传输失败", "已拒绝"),
        ]:
            w.findChildren(QLabel)[-1].setText(
                f"<span style='font-size:22px; color:{C_TEXT_LIGHT};'>"
                f"{label} <b style='color:{C_DARK};'>{cnt(*ss)} 项</b></span>")

    @staticmethod
    def _fmt(s):
        if s < 1024: return f"{s} B"
        elif s < 1024 * 1024: return f"{s / 1024:.1f} KB"
        elif s < 1024 ** 3: return f"{s / (1024 * 1024):.1f} MB"
        return f"{s / (1024 ** 3):.2f} GB"