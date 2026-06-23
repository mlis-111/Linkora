"""
文件传输面板
Author: gxt

发送流程：选接收人 → 选文件 → FILE_REQ → 收到 FILE_RESP 后 64KB 分块 Base64 发送 → 进度条
接收流程：FILE_REQ 通知 → 接受/拒绝 → 选保存位置 → 收数据块落盘 → FILE_END 完成
"""
import os
import base64
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QFrame, QWidget, QProgressBar,
                             QComboBox, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from common.messages import MT
from client.core.base_panel import BasePanel

CHUNK_SIZE = 64 * 1024  # 64KB


class FilePanel(BasePanel):
    """文件传输面板：选文件、发送、接收、进度展示"""

    def __init__(self, master, app):
        # 发送状态
        self._file_path = None
        self._sending = False
        self._send_seq = 0
        self._send_total = 0
        self._send_file_id = None
        self._send_target_id = None
        self._send_fh = None

        # 接收缓冲区: file_id -> {file_name, file_size, received, fh, save_path}
        self._receiving = {}

        # 传输记录: [{file_name, size_str, file_size, sender, progress, status}]
        self._records = []

        super().__init__(master, app)

    # ── 订阅 ──────────────────────────────────────────────

    def subscribe(self):
        self.net.on(MT.FILE_REQ, self._on_file_req)
        self.net.on(MT.FILE_RESP, self._on_file_resp)
        self.net.on(MT.FILE_DATA, self._on_file_data)
        self.net.on(MT.FILE_END, self._on_file_end)
        self.net.on(MT.USER_LIST, self._on_user_list_update)
        self._build_ui()

    # ── UI 构建 ───────────────────────────────────────────

    def _build_ui(self):
        """构建文件传输界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 头部 ──
        header = QFrame()
        header.setFixedHeight(68)
        header.setStyleSheet("background-color: #F7F9FD;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        title = QLabel("文件传输")
        title.setStyleSheet(
            "font-size: 19px; font-weight: 800; color: #1E293B;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 接收人下拉框
        self.receiver_combo = QComboBox()
        self.receiver_combo.setFixedWidth(160)
        self.receiver_combo.setFixedHeight(36)
        self.receiver_combo.setPlaceholderText("选择接收人")
        self.receiver_combo.setStyleSheet("""
            QComboBox {
                background-color: #fff;
                border: 2px solid #E7EFFC;
                border-radius: 10px;
                font-size: 13px;
                color: #1E293B;
                padding: 4px 12px;
            }
            QComboBox:hover { border: 2px solid #4F8DFD; }
            QComboBox QAbstractItemView {
                background-color: #fff;
                border: 1px solid #E7EFFC;
                border-radius: 8px;
                selection-background-color: #E7EFFC;
                selection-color: #1E293B;
            }
        """)
        self._refresh_receiver_list()
        header_layout.addWidget(self.receiver_combo)

        header_layout.addSpacing(12)

        upload_btn = QPushButton("📤 发送文件")
        upload_btn.setFixedHeight(36)
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        upload_btn.clicked.connect(self._select_and_send)
        header_layout.addWidget(upload_btn)

        layout.addWidget(header)

        # ── 内容区域 ──
        content = QWidget()
        content.setStyleSheet("background-color: #EEF2FA;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        # 统计信息卡片（保留 feature-zjj 原有样式）
        stats_card = QFrame()
        stats_card.setStyleSheet("""
            background-color: #fff;
            border-radius: 16px;
        """)
        stats_layout = QHBoxLayout(stats_card)
        stats_layout.setSpacing(32)

        stats = [
            ("今日传输", "12 个文件", "📊"),
            ("传输速度", "480 KB/s", "⚡"),
            ("总计大小", "156 MB", "💾"),
        ]
        for label, value, icon in stats:
            stat_item = QWidget()
            stat_layout = QVBoxLayout(stat_item)
            stat_layout.setSpacing(6)
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 24px;")
            stat_layout.addWidget(icon_label)
            value_label = QLabel(value)
            value_label.setStyleSheet(
                "font-size: 16px; font-weight: 700; color: #1E293B;")
            stat_layout.addWidget(value_label)
            label_label = QLabel(label)
            label_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
            stat_layout.addWidget(label_label)
            stats_layout.addWidget(stat_item)
        stats_layout.addStretch()
        content_layout.addWidget(stats_card)

        # 传输记录标题
        list_title = QLabel("传输记录")
        list_title.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #1E293B;")
        content_layout.addWidget(list_title)

        # 传输记录列表
        self.records_scroll = QScrollArea()
        self.records_scroll.setWidgetResizable(True)
        self.records_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)
        self.records_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self.records_content = QWidget()
        self.records_layout = QVBoxLayout(self.records_content)
        self.records_layout.setContentsMargins(0, 0, 0, 0)
        self.records_layout.setSpacing(12)
        self.records_layout.setAlignment(Qt.AlignTop)

        self.records_scroll.setWidget(self.records_content)
        content_layout.addWidget(self.records_scroll, 1)

        layout.addWidget(content, 1)

    # ── 接收人列表刷新 ───────────────────────────────────

    def _on_user_list_update(self, msg):
        """在线列表更新时刷新接收人下拉框"""
        self._refresh_receiver_list()

    def _refresh_receiver_list(self):
        """根据在线列表刷新接收人下拉框"""
        current = self.receiver_combo.currentText()
        self.receiver_combo.clear()
        for u in self.app.state.online_users:
            if u.get("user_id") != self.app.state.user_id:
                label = u.get("nickname") or u.get("username", "")
                self.receiver_combo.addItem(label, u["user_id"])
        if current:
            idx = self.receiver_combo.findText(current)
            if idx >= 0:
                self.receiver_combo.setCurrentIndex(idx)

    # ── 发送流程 ─────────────────────────────────────────

    def _select_and_send(self):
        """选择文件并发送"""
        if self._sending:
            QMessageBox.warning(self, "提示", "正在发送文件中，请等待完成")
            return

        idx = self.receiver_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "提示", "请先选择接收人")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要发送的文件", "", "所有文件 (*.*)")
        if not file_path:
            return

        self._file_path = file_path
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        self._send_target_id = self.receiver_combo.currentData()

        self._send_file_id = None
        self._sending = True

        self.net.send({
            "type": MT.FILE_REQ,
            "to": self._send_target_id,
            "file_name": file_name,
            "file_size": file_size,
        })

        self._add_record(file_name, file_size, "我", 0, "waiting")

    def _start_send_chunks(self):
        """收到接受应答后，开始分块发送文件数据"""
        if not self._file_path or not self._send_file_id:
            return
        try:
            self._send_fh = open(self._file_path, "rb")
        except OSError:
            self._update_record_status("读取失败")
            self._sending = False
            return

        file_size = os.path.getsize(self._file_path)
        self._send_seq = 0
        self._send_total = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        self._update_record_progress(0, "sending")
        self._send_next_chunk()

    def _send_next_chunk(self):
        """发送下一批数据块（每次 10 块，通过 QTimer 调度避免阻塞 GUI）"""
        if not self._send_fh:
            return

        # 每次调用发送一批（最多 10 块），然后让出 GUI 线程
        for _ in range(10):
            data = self._send_fh.read(CHUNK_SIZE)
            if not data:
                # 全部发送完毕
                self._send_fh.close()
                self._send_fh = None
                self._sending = False
                self.net.send({
                    "type": MT.FILE_END,
                    "to": self._send_target_id,
                    "file_id": self._send_file_id,
                    "status": 1,
                })
                self._update_record_progress(100, "done")
                return

            encoded = base64.b64encode(data).decode("ascii")
            self.net.send({
                "type": MT.FILE_DATA,
                "to": self._send_target_id,
                "file_id": self._send_file_id,
                "seq": self._send_seq,
                "data": encoded,
            })

            self._send_seq += 1
            progress = min(int(self._send_seq / self._send_total * 100), 99)
            self._update_record_progress(progress, "sending")

        # 还有数据，通过 QTimer 调度下一批
        QTimer.singleShot(10, self._send_next_chunk)

    # ── 接收流程 ─────────────────────────────────────────

    def _prompt_receive(self, msg):
        """收到文件请求，弹窗询问是否接受"""
        file_name = msg.get("file_name", "未知文件")
        file_size = msg.get("file_size", 0)
        size_mb = file_size / (1024 * 1024)
        from_id = msg.get("from")

        from_name = str(from_id)
        for u in self.app.state.online_users:
            if u.get("user_id") == from_id:
                from_name = u.get("nickname") or u.get("username", "")
                break

        reply = QMessageBox.question(
            self, "文件传输请求",
            f"{from_name} 向您发送文件：\n\n"
            f"📄 {file_name}\n📦 {size_mb:.2f} MB\n\n是否接受？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            save_path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", file_name, "所有文件 (*.*)")
            if not save_path:
                self.net.send({
                    "type": MT.FILE_RESP,
                    "to": from_id,
                    "file_id": msg.get("file_id"),
                    "accept": False,
                })
                return

            self._receiving[msg["file_id"]] = {
                "file_name": file_name,
                "file_size": file_size,
                "received": 0,
                "save_path": save_path,
                "fh": open(save_path, "wb"),
            }

            self._add_record(file_name, file_size, from_name, 0, "receiving")

            self.net.send({
                "type": MT.FILE_RESP,
                "to": from_id,
                "file_id": msg.get("file_id"),
                "accept": True,
            })
        else:
            self.net.send({
                "type": MT.FILE_RESP,
                "to": from_id,
                "file_id": msg.get("file_id"),
                "accept": False,
            })

    # ── 消息回调（已在 GUI 线程）─────────────────────────

    def _on_file_req(self, msg):
        """收到文件传输请求"""
        self._prompt_receive(msg)

    def _on_file_resp(self, msg):
        """收到对方对文件请求的应答"""
        if msg.get("accept"):
            self._send_file_id = msg.get("file_id")
            self._start_send_chunks()
        else:
            self._update_record_status("已拒绝")
            self._sending = False

    def _on_file_data(self, msg):
        """收到文件数据块"""
        file_id = msg.get("file_id")
        buf = self._receiving.get(file_id)
        if buf is None:
            return

        try:
            raw = base64.b64decode(msg.get("data", ""))
        except Exception:
            return

        try:
            buf["fh"].write(raw)
        except OSError:
            buf["fh"].close()
            self._receiving.pop(file_id, None)
            self._update_record_status("写入失败")
            return

        buf["received"] += len(raw)
        if buf["file_size"] > 0:
            progress = min(int(buf["received"] / buf["file_size"] * 100), 99)
        else:
            progress = 0
        self._update_record_progress(progress, "receiving")

    def _on_file_end(self, msg):
        """收到文件传输结束"""
        file_id = msg.get("file_id")
        status = msg.get("status", 1)

        # 如果是接收方
        buf = self._receiving.pop(file_id, None)
        if buf is not None:
            buf["fh"].close()
            if status == 1:
                self._update_record_progress(100, "done")
            else:
                self._update_record_status("传输失败")
                try:
                    os.remove(buf["save_path"])
                except OSError:
                    pass
            return

        # 如果是发送方
        if status == 1:
            self._update_record_status("已完成")
        else:
            self._update_record_status("传输失败")

    # ── 传输记录管理 ────────────────────────────────────

    def _add_record(self, file_name, file_size, sender, progress, status):
        """添加一条传输记录"""
        self._records.append({
            "file_name": file_name,
            "size_str": self._format_size(file_size),
            "file_size": file_size,
            "sender": sender,
            "progress": progress,
            "status": status,
        })
        self._render_records()

    def _update_record_progress(self, progress, status):
        """更新最新一条记录的进度"""
        if self._records:
            self._records[-1]["progress"] = progress
            self._records[-1]["status"] = status
        self._render_records()

    def _update_record_status(self, status):
        """更新最新一条记录的状态"""
        if self._records:
            self._records[-1]["status"] = status
        self._render_records()

    def _render_records(self):
        """重新渲染传输记录列表"""
        while self.records_layout.count():
            child = self.records_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for rec in self._records:
            item = self._create_record_item(rec)
            self.records_layout.addWidget(item)

        self.records_layout.addStretch()

    def _create_record_item(self, rec):
        """创建一条传输记录控件"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(item)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 14, 16, 14)

        info_row = QHBoxLayout()
        info_row.setSpacing(14)

        icon_map = {
            ".pdf": "📄", ".doc": "📝", ".docx": "📝",
            ".zip": "📦", ".rar": "📦", ".7z": "📦",
            ".jpg": "🖼", ".png": "🖼", ".gif": "🖼",
            ".py": "💻", ".js": "💻",
            ".mp4": "🎬", ".mp3": "🎵",
        }
        ext = os.path.splitext(rec["file_name"])[1].lower()
        icon = icon_map.get(ext, "📎")

        file_icon = QLabel(icon)
        file_icon.setFixedSize(48, 48)
        file_icon.setAlignment(Qt.AlignCenter)
        file_icon.setStyleSheet("""
            background-color: #E7EFFC;
            border-radius: 14px;
            font-size: 24px;
        """)
        info_row.addWidget(file_icon)

        file_info_layout = QVBoxLayout()
        file_info_layout.setSpacing(4)
        name_label = QLabel(rec["file_name"])
        name_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #1E293B;")
        file_info_layout.addWidget(name_label)

        direction = "发送给" if rec["sender"] == "我" else "来自"
        meta_label = QLabel(f"{rec['size_str']} · {direction} {rec['sender']}")
        meta_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        file_info_layout.addWidget(meta_label)

        info_row.addLayout(file_info_layout)
        info_row.addStretch()

        status_text = {
            "waiting": "等待应答...",
            "sending": "发送中",
            "receiving": "接收中",
            "done": "✅ 完成",
            "已完成": "✅ 完成",
            "已拒绝": "❌ 已拒绝",
            "读取失败": "❌ 读取失败",
            "写入失败": "❌ 写入失败",
            "传输失败": "❌ 传输失败",
        }.get(rec["status"], rec["status"])

        if rec["status"] in ("done", "已完成"):
            color = "#34D399"
        elif "失败" in rec["status"] or "拒绝" in rec["status"]:
            color = "#FB7185"
        else:
            color = "#2D6CF6"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {color};")
        info_row.addWidget(status_label)

        layout.addLayout(info_row)

        if rec["status"] in ("sending", "receiving", "waiting"):
            progress_bar = QProgressBar()
            progress_bar.setFixedHeight(7)
            progress_bar.setValue(rec["progress"])
            progress_bar.setTextVisible(False)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: #EDF1F8;
                    border: none;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4F8DFD, stop:1 #2D6CF6);
                    border-radius: 4px;
                }
            """)
            layout.addWidget(progress_bar)

            progress_text = QLabel(f"{rec['progress']}% · {status_text}")
            progress_text.setStyleSheet(
                "font-size: 11px; color: #2D6CF6; font-weight: 600;")
            layout.addWidget(progress_text)

        return item

    @staticmethod
    def _format_size(size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
