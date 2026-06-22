from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame, QWidget, QProgressBar
from PyQt5.QtCore import Qt
from client.core.base_panel import BasePanel


class FilePanel(BasePanel):
    """文件传输面板 - 方案B样式"""

    def subscribe(self):
        self._build_ui()

    def _build_ui(self):
        """构建文件传输界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QFrame()
        header.setFixedHeight(68)
        header.setStyleSheet("background-color: #F7F9FD;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        title = QLabel("文件传输")
        title.setStyleSheet("font-size: 19px; font-weight: 800; color: #1E293B;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        upload_btn = QPushButton("📤 发送文件")
        upload_btn.setFixedHeight(36)
        upload_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 600;
                
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3B7FED, stop:1 #1D5CE6);
            }
        """)
        header_layout.addWidget(upload_btn)

        layout.addWidget(header)

        # 内容区域
        content = QWidget()
        content.setStyleSheet("background-color: #EEF2FA;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(16)

        # 统计信息卡片
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
            value_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #1E293B;")
            stat_layout.addWidget(value_label)

            label_label = QLabel(label)
            label_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
            stat_layout.addWidget(label_label)

            stats_layout.addWidget(stat_item)

        stats_layout.addStretch()
        content_layout.addWidget(stats_card)

        # 文件列表标题
        list_title = QLabel("传输记录")
        list_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1E293B;  ")
        content_layout.addWidget(list_title)

        # 文件列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)
        scroll_layout.setAlignment(Qt.AlignTop)

        # 示例文件
        files = [
            ("AES加密方案.pdf", "2.4 MB", "董钧豪", 72, True, "📄", "#FEE2E2"),
            ("客户端框架.zip", "8.6 MB", "郭玄同", 100, False, "📦", "#DBEAFE"),
            ("UI设计稿.fig", "12.3 MB", "朱俊基", 100, False, "🎨", "#E0E7FF"),
            ("数据库文档.docx", "1.2 MB", "武家辉", 100, False, "📝", "#D1FAE5"),
        ]

        for filename, size, sender, progress, is_active, icon, icon_bg in files:
            item = self._create_file_item(filename, size, sender, progress, is_active, icon, icon_bg)
            scroll_layout.addWidget(item)

        scroll.setWidget(scroll_content)
        content_layout.addWidget(scroll)

        layout.addWidget(content)

    def _create_file_item(self, filename, size, sender, progress, is_active, icon, icon_bg):
        """创建文件传输项"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border-radius: 16px;
                
                
            }
        """)

        layout = QVBoxLayout(item)
        layout.setSpacing(12)

        # 文件信息行
        info_row = QHBoxLayout()
        info_row.setSpacing(14)

        # 文件图标
        file_icon = QLabel(icon)
        file_icon.setFixedSize(48, 48)
        file_icon.setAlignment(Qt.AlignCenter)
        file_icon.setStyleSheet(f"""
            background-color: {icon_bg};
            border-radius: 14px;
            font-size: 24px;
        """)
        info_row.addWidget(file_icon)

        # 文件名和信息
        file_info_layout = QVBoxLayout()
        file_info_layout.setSpacing(4)

        name_label = QLabel(filename)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1E293B;")
        file_info_layout.addWidget(name_label)

        meta_label = QLabel(f"{size} · 来自 {sender}")
        meta_label.setStyleSheet("font-size: 12px; color: #94A3B8;")
        file_info_layout.addWidget(meta_label)

        info_row.addLayout(file_info_layout)
        info_row.addStretch()

        # 操作按钮
        if progress < 100:
            action_btn = QPushButton("⏸")
            action_btn.setToolTip("暂停")
        else:
            action_btn = QPushButton("⬇")
            action_btn.setToolTip("打开")

        action_btn.setFixedSize(36, 36)
        action_btn.setStyleSheet("""
            QPushButton {
                background-color: #E7EFFC;
                color: #2D6CF6;
                border: none;
                border-radius: 12px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #D1E3FA;
            }
        """)
        info_row.addWidget(action_btn)

        layout.addLayout(info_row)

        # 进度条
        if progress < 100:
            progress_frame = QFrame()
            progress_frame.setFixedHeight(7)
            progress_frame.setStyleSheet("background-color: #EDF1F8; border-radius: 4px;")

            progress_bar = QFrame(progress_frame)
            progress_bar.setGeometry(0, 0, int(progress_frame.width() * progress / 100), 7)
            progress_bar.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4F8DFD, stop:1 #2D6CF6);
                border-radius: 4px;
            """)
            layout.addWidget(progress_frame)

            # 进度文字
            progress_text = QLabel(f"{progress}% · 传输中...")
            progress_text.setStyleSheet("font-size: 11px; color: #2D6CF6; font-weight: 600;")
            layout.addWidget(progress_text)

        return item
