from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLineEdit,
    QSizePolicy,
)

from .backend import DataRepository


class DashboardCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str, accent: str = "#2F8CFF"):
        super().__init__()
        self.setObjectName("dashboardCard")
        self.setMinimumHeight(120)
        self.setStyleSheet(
            f"QFrame#dashboardCard {{ background: #1f2f3d; border: 1px solid #2d3d4d; border-radius: 14px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #b9c3d1; font-size: 12px; font-weight: 600;")

        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {accent}; font-size: 28px; font-weight: 700;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #8a99ad; font-size: 11px;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)


class CompactTile(QFrame):
    def __init__(self, title: str, subtitle: str, color: str = "#F5F7FA"):
        super().__init__()
        self.setObjectName("compactTile")
        self.setFixedHeight(120)
        self.setStyleSheet(
            "QFrame#compactTile { background: #e9edf1; border-radius: 12px; border: 1px solid #dfe7ef; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        icon = QLabel("◉")
        icon.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #1a2c3c; font-size: 11px; font-weight: 700;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #405269; font-size: 10px;")
        subtitle_label.setWordWrap(True)

        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


class AvatarCard(QFrame):
    def __init__(self, resident):
        super().__init__()
        self.setObjectName("avatarCard")
        self.setStyleSheet(
            "QFrame#avatarCard { background: #f7f9fb; border-radius: 12px; border: 1px solid #dfe6ee; }"
        )
        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        pix = self._make_avatar(resident.initials, resident.color)
        avatar_label = QLabel()
        avatar_label.setPixmap(pix)
        avatar_label.setFixedSize(90, 90)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel(resident.name)
        name.setStyleSheet("color: #1b2b3a; font-size: 14px; font-weight: 700;")

        role = QLabel(resident.role)
        role.setStyleSheet("color: #5d6d7e; font-size: 11px;")
        role.setWordWrap(True)

        layout.addWidget(avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(role)

    @staticmethod
    def _make_avatar(initials: str, color: str) -> QPixmap:
        pixmap = QPixmap(90, 90)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 90, 90)
        painter.setPen(QColor("#1d2a39"))
        painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, initials)
        painter.end()
        return pixmap


class WeRhereMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.repo = DataRepository()
        self.setWindowTitle("WeRhere")
        self.resize(1500, 900)
        self.setStyleSheet(open("app/styles.qss", encoding="utf-8").read())
        self._build_ui()

    @staticmethod
    def _load_brand_logo() -> QPixmap | None:
        logo_path = Path(__file__).resolve().parent / "assets" / "brand-logo2.png"
        if not logo_path.exists():
            return None
        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            return None
        return pixmap.scaled(220, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def _build_ui(self):
        main_widget = QWidget(self)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        content = self._build_content()

        main_layout.addWidget(sidebar, 0)
        main_layout.addWidget(content, 1)

        self.setCentralWidget(main_widget)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)

        logo_container = QWidget()
        logo_container.setObjectName("brandShell")
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pixmap = self._load_brand_logo()
        if logo_pixmap is not None:
            logo_label.setPixmap(logo_pixmap)
        else:
            logo_label.setText("WeRhere")
            logo_label.setStyleSheet("color: white; font-size: 30px; font-weight: 700;")
        logo_layout.addWidget(logo_label)
        layout.addWidget(logo_container)

        nav_items = [
            ("Dashboard", "active"),
            ("Applications", ""),
            ("Meetings", ""),
            ("Reports", ""),
            ("Settings", ""),
        ]

        for label, state in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navButton" if state != "active" else "navButtonActive")
            btn.setStyleSheet(
                "QPushButton#navButton { background: transparent; color: #dfeaf5; border: none; text-align: left; padding: 10px 12px; border-radius: 10px; }"
                "QPushButton#navButton:hover { background: rgba(255,255,255,0.06); }"
                "QPushButton#navButtonActive { background: #d8e4ee; color: #17314e; border: none; text-align: left; padding: 10px 12px; border-radius: 10px; font-weight: 700; }"
            )
            layout.addWidget(btn)

        layout.addStretch()
        footer = QLabel("WeRhere CRM")
        footer.setStyleSheet("color: #bdc8d3; font-size: 11px; padding-top: 8px;")
        layout.addWidget(footer)

        return sidebar

    def _build_content(self) -> QWidget:
        container = QWidget()
        container.setObjectName("mainArea")
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(22, 18, 22, 18)
        content_layout.setSpacing(18)

        header_row = QHBoxLayout()
        heading = QLabel("Operations dashboard")
        heading.setStyleSheet("font-size: 34px; font-weight: 800; color: #edf3fb;")
        header_row.addWidget(heading)
        header_row.addStretch()

        status_badge = QLabel("Live overview")
        status_badge.setStyleSheet(
            "background: rgba(95, 214, 167, 0.12); color: #90f0be; border: 1px solid rgba(144, 240, 190, 0.4); border-radius: 999px; padding: 8px 14px; font-weight: 700;"
        )
        header_row.addWidget(status_badge)
        action_button = QPushButton("+ New record")
        action_button.setObjectName("primaryButton")
        header_row.addWidget(action_button)
        content_layout.addLayout(header_row)

        topbar = QHBoxLayout()
        search = QLineEdit()
        search.setPlaceholderText("Search applications, meetings, residents")
        search.setObjectName("searchBox")
        topbar.addWidget(search)

        filter_button = QPushButton("Filter")
        filter_button.setObjectName("ghostButton")
        topbar.addWidget(filter_button)
        content_layout.addLayout(topbar)

        stats_row = QHBoxLayout()
        stats_row.addWidget(DashboardCard("Applications", "124", "+14% vs last month", "#6ec0ff"))
        stats_row.addWidget(DashboardCard("Needs review", "12", "3 urgent", "#ffc870"))
        stats_row.addWidget(DashboardCard("Meetings", "27", "This week", "#54d3a7"))
        stats_row.addWidget(DashboardCard("Residents", "96", "Active", "#ff8aaa"))
        content_layout.addLayout(stats_row)

        middle = QHBoxLayout()
        middle.setSpacing(16)

        left_panel = self._build_applications_panel()
        right_panel = self._build_side_panel()

        middle.addWidget(left_panel, 2)
        middle.addWidget(right_panel, 1)
        content_layout.addLayout(middle)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(18)
        bottom_row.addWidget(self._build_profile_panel(), 2)
        bottom_row.addWidget(self._build_messaging_panel(), 1)
        content_layout.addLayout(bottom_row)

        return container

    def _build_applications_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QLabel("Applications")
        header.setStyleSheet("color: #f0f5fa; font-size: 20px; font-weight: 700;")
        layout.addWidget(header)

        table = QTableWidget(0, 5)
        table.setObjectName("appTable")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Name", "Type", "Location", "Status", "Last update"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet(
            "QTableWidget#appTable { background: #1f2f3d; color: #edf3fb; border: 1px solid #2d3d4d; border-radius: 12px; }"
            "QHeaderView::section { background: #24384c; color: #edf3fb; padding: 8px; border: none; }"
            "QTableWidget::item { padding: 8px; border-bottom: 1px solid #2d3d4d; color: #edf3fb; }"
        )

        for app in self.repo.get_applications():
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(app.applicant_name))
            table.setItem(row, 1, QTableWidgetItem(app.type_name))
            table.setItem(row, 2, QTableWidgetItem(app.location))
            table.setItem(row, 3, QTableWidgetItem(app.status))
            table.setItem(row, 4, QTableWidgetItem(app.last_update))

        layout.addWidget(table)
        return panel

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QLabel("Meeting")
        header.setStyleSheet("color: #f0f5fa; font-size: 20px; font-weight: 700;")
        layout.addWidget(header)

        for item in self.repo.get_meetings():
            row = QFrame()
            row.setObjectName("meetingRow")
            row.setStyleSheet(
                "QFrame#meetingRow { background: #1d2d3d; border: 1px solid #344a61; border-radius: 12px; }"
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 12, 12, 12)

            left = QLabel(item.title)
            left.setStyleSheet("color: #edf3fb; font-weight: 600;")
            time = QLabel(item.time)
            time.setStyleSheet("color: #a2b7cb; font-size: 11px;")
            status = QLabel(item.status)
            status.setStyleSheet("color: #9be4c0; font-size: 10px; font-weight: 700;")

            row_layout.addWidget(left)
            row_layout.addStretch()
            row_layout.addWidget(time)
            row_layout.addWidget(status)
            layout.addWidget(row)

        return panel

    def _build_profile_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        header = QLabel("Character References")
        header.setStyleSheet("color: #f0f5fa; font-size: 20px; font-weight: 700;")
        layout.addWidget(header)

        cards = QHBoxLayout()
        for resident in self.repo.get_residents():
            cards.addWidget(AvatarCard(resident))
        layout.addLayout(cards)

        return panel

    def _build_messaging_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QLabel("Our CRM Application")
        header.setStyleSheet("color: #f0f5fa; font-size: 18px; font-weight: 700;")
        layout.addWidget(header)

        tiles = QHBoxLayout()
        for title, subtitle, color in [
            ("Better", "Application Management", "#3b6ea7"),
            ("Stronger", "Mentor Support", "#4d8d6d"),
            ("More", "Career Opportunities", "#d4b360"),
        ]:
            tiles.addWidget(CompactTile(title, subtitle, color))
        layout.addLayout(tiles)

        badge = QLabel("Every application represents a person.")
        badge.setWordWrap(True)
        badge.setStyleSheet("color: #dfeaf5; font-size: 16px; font-weight: 600; background: #1d2d3d; border-radius: 12px; padding: 18px;")
        layout.addWidget(badge)

        return panel


def main():
    import sys

    app = QApplication(sys.argv)
    window = WeRhereMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
