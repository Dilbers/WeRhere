from __future__ import annotations

from collections import Counter
from datetime import datetime
import os
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .backend import initialize_database


_UI_FONT_FAMILY: str | None = None


def _register_windows_font() -> None:
    global _UI_FONT_FAMILY
    application = QApplication.instance()
    if application is None:
        return
    if _UI_FONT_FAMILY is not None:
        application.setFont(QFont(_UI_FONT_FAMILY))
        return
    font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
    if not font_path.is_file():
        return
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        raise RuntimeError(f"Could not load the Windows UI font: {font_path}")
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError(f"No font family was registered from: {font_path}")
    _UI_FONT_FAMILY = families[0]
    application.setFont(QFont(_UI_FONT_FAMILY))


class BrandLogoWidget(QLabel):
    def __init__(self, width: int = 240, height: int = 72):
        super().__init__()
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_logo(width, height)

    def _load_logo(self, width: int, height: int):
        logo_path = Path(__file__).resolve().parent / "assets" / "brand-logo.svg"
        if not logo_path.exists():
            self.setText("WeRhere")
            self.setStyleSheet("font-size: 30px; font-weight: 800; color: #34434b;")
            return

        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            self.setText("WeRhere")
            self.setStyleSheet("font-size: 30px; font-weight: 800; color: #34434b;")
            return
        self.setPixmap(pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        _register_windows_font()
        self.setWindowTitle("WeRhere | Sign in")
        self.setFixedSize(480, 480)
        style_path = Path(__file__).with_name("styles.qss")
        self.setStyleSheet(style_path.read_text(encoding="utf-8"))
        self.db = initialize_database()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 34, 42, 30)
        layout.setSpacing(14)

        logo = BrandLogoWidget(270, 78)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Welcome back")
        title.setObjectName("loginTitle")
        layout.addWidget(title)
        introduction = QLabel("Sign in to continue to your workspace.")
        introduction.setObjectName("pageSubtitle")
        layout.addWidget(introduction)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(0)
        self.username_edit = QLineEdit()
        self.username_edit.setMinimumHeight(42)
        self.username_edit.setPlaceholderText("Username")
        self.password_edit = QLineEdit()
        self.password_edit.setMinimumHeight(42)
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username_edit)
        form.addRow("Password", self.password_edit)
        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Sign in")
        button_box.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryButton")
        button_box.button(QDialogButtonBox.StandardButton.Ok).setMinimumHeight(44)
        button_box.accepted.connect(self._attempt_login)
        layout.addWidget(button_box)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorMessage")
        layout.addWidget(self.error_label)
        self.password_edit.returnPressed.connect(self._attempt_login)
        layout.addStretch()

    def _attempt_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        self.authenticated_user = self.db.get_authenticated_user(username, password)
        if self.authenticated_user is not None:
            self.accept()
        else:
            self.error_label.setText("Invalid username or password.")
            self.password_edit.clear()


class DashboardCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str, accent: str = "#2F8CFF"):
        super().__init__()
        self.setObjectName("dashboardCard")
        self.setMinimumHeight(126)
        self.setStyleSheet(f"""
            QFrame#dashboardCard {{
                background: #ffffff;
                border: 1px solid #e6ebf2;
                border-left: 4px solid {accent};
                border-radius: 14px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #748197; font-size: 12px; font-weight: 600;")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("color: #24354a; font-size: 27px; font-weight: 750;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #8b97a8; font-size: 11px;")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(subtitle_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class ApplicationDialog(QDialog):
    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application" if record is None else "Edit Application")
        self.resize(520, 420)

        self.applicant_name = QLineEdit(record["applicant_name"] if record else "")
        self.type_name = QLineEdit(record["type_name"] if record else "")
        self.location = QLineEdit(record["location"] if record else "")

        self.status = QComboBox()
        self.status.addItems(["Pending", "In review", "Approved", "Needs follow-up"])
        self.status.setCurrentText(record["status"] if record else "Pending")

        self.priority = QComboBox()
        self.priority.addItems(["High", "Medium", "Low"])
        self.priority.setCurrentText(record["priority"] if record else "Medium")

        self.last_update = QLineEdit(record["last_update"] if record else "Today")
        self.notes = QTextEdit(record["notes"] if record else "")

        form = QFormLayout(self)
        form.addRow("Applicant Name", self.applicant_name)
        form.addRow("Type", self.type_name)
        form.addRow("Location", self.location)
        form.addRow("Status", self.status)
        form.addRow("Priority", self.priority)
        form.addRow("Last Update", self.last_update)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def data(self):
        return {
            "applicant_name": self.applicant_name.text().strip(),
            "type_name": self.type_name.text().strip(),
            "location": self.location.text().strip(),
            "status": self.status.currentText(),
            "priority": self.priority.currentText(),
            "last_update": self.last_update.text().strip() or "Today",
            "notes": self.notes.toPlainText().strip(),
        }


class MeetingDialog(QDialog):
    def __init__(self, record=None, parent=None, residents=None):
        super().__init__(parent)
        self.setWindowTitle("Meeting" if record is None else "Edit Meeting")
        self.resize(450, 250)

        self.title = QLineEdit(record["title"] if record else "")
        self.meeting_time = QLineEdit(record["meeting_time"] if record else "")
        self.meeting_time.setPlaceholderText("YYYY-MM-DD HH:MM")
        self.mentor_name = QLineEdit(
            record.get("mentor_name", "Community team") if record else ""
        )
        self.mentor_name.setPlaceholderText("Mentor or team")
        self.resident_name = QComboBox()
        self.resident_name.addItem("Not assigned", "")
        for resident in (residents or []):
            self.resident_name.addItem(resident["name"], resident["name"])
        if record:
            match = self.resident_name.findData(record.get("resident_name", ""))
            self.resident_name.setCurrentIndex(max(match, 0))
        self.status = QComboBox()
        self.status.addItems(["Scheduled", "Pending", "Approved", "Cancelled"])
        self.status.setCurrentText(record["status"] if record else "Scheduled")

        form = QFormLayout(self)
        form.addRow("Title", self.title)
        form.addRow("Time", self.meeting_time)
        form.addRow("Mentor", self.mentor_name)
        form.addRow("Resident", self.resident_name)
        form.addRow("Status", self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def data(self):
        return {
            "title": self.title.text().strip(),
            "meeting_time": self.meeting_time.text().strip(),
            "mentor_name": self.mentor_name.text().strip() or "Community team",
            "resident_name": self.resident_name.currentData() or "",
            "status": self.status.currentText(),
        }


class MessageDialog(QDialog):
    def __init__(self, recipients, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New message")
        self.setMinimumSize(500, 390)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Write a message")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QFormLayout()
        self.recipient = QComboBox()
        for username, display_name in recipients:
            self.recipient.addItem(f"{display_name}  ·  {username}", username)
        self.subject = QLineEdit()
        self.subject.setPlaceholderText("A short, clear subject")
        self.body = QTextEdit()
        self.body.setPlaceholderText("Write your message...")
        self.body.setMinimumHeight(150)
        form.addRow("To", self.recipient)
        form.addRow("Subject", self.subject)
        form.addRow("Message", self.body)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Send")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorMessage")
        layout.addWidget(self.error_label)

    def _accept_if_valid(self):
        if not self.recipient.currentData():
            self.error_label.setText("Choose a recipient.")
        elif not self.subject.text().strip() or not self.body.toPlainText().strip():
            self.error_label.setText("Add a subject and message before sending.")
        else:
            self.accept()

    def data(self):
        return {
            "recipient": self.recipient.currentData(),
            "subject": self.subject.text().strip(),
            "body": self.body.toPlainText().strip(),
        }


class ResidentDialog(QDialog):
    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resident" if record is None else "Edit Resident")
        self.resize(450, 340)

        self.name = QLineEdit(record["name"] if record else "")
        self.role = QLineEdit(record["role"] if record else "")
        self.description = QTextEdit(record["description"] if record else "")
        self.initials = QLineEdit(record["initials"] if record else "")
        self.color = QLineEdit(record["color"] if record else "#DCE7F5")

        form = QFormLayout(self)
        form.addRow("Name", self.name)
        form.addRow("Accommodation type", self.role)
        form.addRow("Description", self.description)
        form.addRow("Initials", self.initials)
        form.addRow("Avatar background (hex)", self.color)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def data(self):
        return {
            "name": self.name.text().strip(),
            "role": self.role.text().strip(),
            "description": self.description.toPlainText().strip(),
            "initials": self.initials.text().strip(),
            "color": self.color.text().strip() or "#DCE7F5",
        }


class AvatarCard(QFrame):
    def __init__(self, name: str, initials: str, color: str, role: str):
        super().__init__()
        self.setObjectName("avatarCard")
        self.setStyleSheet(
            "QFrame#avatarCard { background: #f7f9fb; border-radius: 12px; border: 1px solid #dfe6ee; }"
        )
        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        pix = self._make_avatar(initials, color)
        avatar_label = QLabel()
        avatar_label.setPixmap(pix)
        avatar_label.setFixedSize(90, 90)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(name)
        name_label.setStyleSheet("color: #1b2b3a; font-size: 14px; font-weight: 700;")

        role_label = QLabel(role)
        role_label.setStyleSheet("color: #5d6d7e; font-size: 11px;")
        role_label.setWordWrap(True)

        layout.addWidget(avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(role_label)

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
    def __init__(self, user):
        super().__init__()
        _register_windows_font()
        self.username = user["username"]
        self.display_name = user["display_name"] or self.username
        self.role = user["role"]
        self.is_admin = self.role == "admin"
        self.db = initialize_database()
        self.setWindowTitle(
            "WeRhere | Community workspace"
        )
        self.resize(1440, 920)
        self.setMinimumSize(1120, 720)
        style_path = Path(__file__).with_name("styles.qss")
        self.setStyleSheet(style_path.read_text(encoding="utf-8"))
        self._build_ui()

    def _build_ui(self):
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        logo = BrandLogoWidget(184, 54)
        sidebar_layout.addWidget(logo)

        self.nav_buttons = {}
        if self.is_admin:
            self.page_builders = [
                ("Dashboard", self._build_dashboard_page),
                ("Applications", self._build_applications_page),
                ("Mentor sessions", self._build_meetings_page),
                ("Residents", self._build_residents_page),
                ("Messages", self._build_messages_page),
                ("Settings", self._build_settings_page),
            ]
        else:
            self.page_builders = [
                ("My overview", self._build_resident_dashboard_page),
                ("My application", self._build_resident_application_page),
                ("Shared schedule", self._build_resident_meetings_page),
                ("Messages", self._build_messages_page),
                ("Support", self._build_resident_support_page),
                ("Settings", self._build_settings_page),
            ]

        for index, (name, _) in enumerate(self.page_builders):
            btn = QPushButton(name)
            btn.setObjectName("navButton")
            btn.clicked.connect(lambda checked, current=index: self._switch_page(current))
            self.nav_buttons[name] = btn
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()
        role_label = QLabel("ADMINISTRATOR" if self.is_admin else "RESIDENT")
        role_label.setObjectName("roleBadge")
        user_label = QLabel(self.display_name)
        user_label.setObjectName("sidebarUser")
        sidebar_layout.addWidget(user_label)
        sidebar_layout.addWidget(role_label)

        self.stack = QStackedWidget()
        for _, page_builder in self.page_builders:
            self.stack.addWidget(page_builder())

        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.sidebar)
        central_layout.addWidget(self.stack)
        self.setCentralWidget(central)
        self._switch_page(0)

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for btn in self.nav_buttons.values():
            btn.setObjectName("navButton")
            btn.setStyleSheet("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        active_name = list(self.nav_buttons.keys())[index]
        active_button = self.nav_buttons[active_name]
        active_button.setObjectName("navButtonActive")
        active_button.style().unpolish(active_button)
        active_button.style().polish(active_button)

    @staticmethod
    def _colored_item(text: str, category: str = "status") -> QTableWidgetItem:
        status_colors = {
            "approved": ("#e4f5ec", "#287a54"),
            "in review": ("#f0ebfb", "#6b50a4"),
            "pending": ("#fff4d8", "#976b15"),
            "needs follow-up": ("#ffebe9", "#b44440"),
            "rejected": ("#ffebe9", "#b44440"),
            "scheduled": ("#e7f2fc", "#2f6e9f"),
            "cancelled": ("#edf0f4", "#687588"),
            "completed": ("#e4f5ec", "#287a54"),
        }
        priority_colors = {
            "high": ("#ffebe9", "#b44440"),
            "medium": ("#fff4d8", "#976b15"),
            "low": ("#e4f5ec", "#287a54"),
        }
        color_map = priority_colors if category == "priority" else status_colors
        background, foreground = color_map.get(
            text.strip().lower(), ("#edf0f4", "#687588")
        )
        item = QTableWidgetItem(text)
        item.setBackground(QColor(background))
        item.setForeground(QColor(foreground))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        font = item.font()
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(font)
        return item

    @staticmethod
    def _status_badge(text: str) -> QLabel:
        item = WeRhereMainWindow._colored_item(text)
        badge = QLabel(text)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {item.background().color().name()}; "
            f"color: {item.foreground().color().name()}; "
            "border-radius: 10px; padding: 7px 12px; font-weight: 700;"
        )
        return badge

    def _build_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(20)

        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        header = QLabel(f"Good to see you, {self.display_name}")
        header.setObjectName("pageTitle")
        subtitle = QLabel("Here’s what’s happening across your community today.")
        subtitle.setObjectName("pageSubtitle")
        header_text.addWidget(header)
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text)
        header_row.addStretch()
        new_application = QPushButton("+  New application")
        new_application.setObjectName("primaryButton")
        new_application.clicked.connect(self._add_application)
        header_row.addWidget(new_application)
        layout.addLayout(header_row)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(14)
        stats = self.db.dashboard_stats()
        self.application_metric = DashboardCard(
            "Applications", str(stats["applications_total"]), "Across all programmes", "#cf4f4b"
        )
        self.attention_metric = DashboardCard(
            "Needs attention", str(stats["needs_attention"]), "Awaiting a next step", "#dc9a37"
        )
        self.meeting_metric = DashboardCard(
            "Mentor sessions", str(stats["meetings_total"]), "On the shared schedule", "#4f9c9b"
        )
        self.resident_metric = DashboardCard(
            "Residents", str(stats["residents_total"]), "People in your community", "#7084bb"
        )
        for card in (
            self.application_metric,
            self.attention_metric,
            self.meeting_metric,
            self.resident_metric,
        ):
            stats_layout.addWidget(card)
        layout.addLayout(stats_layout)

        middle = QHBoxLayout()
        middle.setSpacing(16)

        recent_panel = QWidget(); recent_panel.setObjectName("panel"); recent_layout = QVBoxLayout(recent_panel)
        panel_header = QHBoxLayout()
        recent_title = QLabel("Recent applications")
        recent_title.setObjectName("panelTitle")
        panel_header.addWidget(recent_title)
        panel_header.addStretch()
        view_all = QPushButton("View all")
        view_all.setObjectName("textButton")
        view_all.clicked.connect(lambda: self._switch_page(1))
        panel_header.addWidget(view_all)
        recent_layout.addLayout(panel_header)
        self.dashboard_table = QTableWidget(0, 4)
        self.dashboard_table.setHorizontalHeaderLabels(["Applicant", "Accommodation", "Status", "Priority"])
        self.dashboard_table.setAlternatingRowColors(True)
        self.dashboard_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.dashboard_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dashboard_table.verticalHeader().setVisible(False)
        self.dashboard_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.dashboard_table.horizontalHeader().setStretchLastSection(True)
        self.dashboard_table.setMaximumHeight(260)
        recent_layout.addWidget(self.dashboard_table)

        info_panel = QWidget(); info_panel.setObjectName("panel"); info_layout = QVBoxLayout(info_panel)
        info_title = QLabel("Coming up")
        info_title.setObjectName("panelTitle")
        info_layout.addWidget(info_title)
        self.upcoming_list = QVBoxLayout()
        self.upcoming_list.setSpacing(10)
        info_layout.addLayout(self.upcoming_list)
        info_layout.addStretch()
        sessions_button = QPushButton("Open mentor sessions")
        sessions_button.clicked.connect(lambda: self._switch_page(2))
        info_layout.addWidget(sessions_button)

        middle.addWidget(recent_panel, 2)
        middle.addWidget(info_panel, 1)
        layout.addLayout(middle)

        attention_panel = QWidget()
        attention_panel.setObjectName("panel")
        attention_layout = QVBoxLayout(attention_panel)
        attention_header = QHBoxLayout()
        attention_title = QLabel("Needs a next step")
        attention_title.setObjectName("panelTitle")
        attention_header.addWidget(attention_title)
        attention_header.addStretch()
        attention_view_all = QPushButton("Review applications")
        attention_view_all.setObjectName("textButton")
        attention_view_all.clicked.connect(lambda: self._switch_page(1))
        attention_header.addWidget(attention_view_all)
        attention_layout.addLayout(attention_header)
        self.attention_list = QHBoxLayout()
        self.attention_list.setSpacing(10)
        attention_layout.addLayout(self.attention_list)
        layout.addWidget(attention_panel)
        self._refresh_dashboard()
        return page

    def _build_resident_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        welcome = QLabel(f"Welcome, {self.display_name}")
        welcome.setObjectName("pageTitle")
        layout.addWidget(welcome)

        application = self.db.get_resident_application(self.display_name)
        meetings = [
            meeting
            for meeting in self.db.list_meetings()
            if not meeting.get("resident_name")
            or meeting["resident_name"] == self.display_name
        ]
        status = application["status"] if application else "Not started"
        next_step = {
            "Approved": "Review your move-in details",
            "In review": "Our team is reviewing your application",
            "Pending": "Your application is in the review queue",
            "Needs follow-up": "Contact your coordinator about the requested information",
        }.get(status, "Contact your coordinator to get started")

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(
            DashboardCard("My application", status, "Current status", "#65D6AD")
        )
        stats_layout.addWidget(
            DashboardCard("Shared schedule", str(len(meetings)), "Community events", "#7DC6FF")
        )
        stats_layout.addWidget(
            DashboardCard("Next step", "1 action", "See your guidance below", "#FFC870")
        )
        layout.addLayout(stats_layout)

        content = QHBoxLayout()
        content.setSpacing(18)

        progress_panel = QWidget()
        progress_panel.setObjectName("panel")
        progress_layout = QVBoxLayout(progress_panel)
        title = QLabel("Your next step")
        title.setObjectName("panelTitle")
        progress_layout.addWidget(title)
        next_step_label = QLabel(next_step)
        next_step_label.setObjectName("nextStep")
        next_step_label.setWordWrap(True)
        progress_layout.addWidget(next_step_label)
        if application:
            progress_layout.addWidget(self._status_badge(status))
            if application.get("notes"):
                note = QLabel(f"Update from your team: {application['notes']}")
                note.setObjectName("supportNote")
                note.setWordWrap(True)
                progress_layout.addWidget(note)
        else:
            no_application = QLabel(
                "There is no application linked to your account yet. "
                "Please contact your coordinator for onboarding."
            )
            no_application.setObjectName("supportNote")
            no_application.setWordWrap(True)
            progress_layout.addWidget(no_application)

        support_panel = QWidget()
        support_panel.setObjectName("panel")
        support_layout = QVBoxLayout(support_panel)
        support_title = QLabel("You’re not on your own")
        support_title.setObjectName("panelTitle")
        support_layout.addWidget(support_title)
        support_text = QLabel(
            "WeRhere keeps your application update, shared schedule, and support "
            "guidance together. If a status or next step is unclear, open Support "
            "to see how to reach your coordinator."
        )
        support_text.setObjectName("supportNote")
        support_text.setWordWrap(True)
        support_layout.addWidget(support_text)
        content.addWidget(progress_panel, 1)
        content.addWidget(support_panel, 1)
        layout.addLayout(content)

        journey_panel = QWidget()
        journey_panel.setObjectName("panel")
        journey_layout = QVBoxLayout(journey_panel)
        journey_title = QLabel("Your journey")
        journey_title.setObjectName("panelTitle")
        journey_layout.addWidget(journey_title)
        journey_steps = QHBoxLayout()
        current_step = {
            "Pending": 0,
            "In review": 1,
            "Needs follow-up": 1,
            "Approved": 3,
        }.get(status, 0)
        step_names = [
            "Application received",
            "Team review",
            "Decision",
            "Next steps",
        ]
        for index, step_name in enumerate(step_names):
            step = QFrame()
            step.setObjectName(
                "journeyStepComplete"
                if index < current_step
                else "journeyStepCurrent"
                if index == current_step
                else "journeyStepPending"
            )
            step_layout = QVBoxLayout(step)
            step_layout.setContentsMargins(12, 10, 12, 10)
            number = QLabel(f"{index + 1:02d}")
            number.setObjectName("journeyStepNumber")
            label = QLabel(step_name)
            label.setObjectName("journeyStepLabel")
            step_layout.addWidget(number)
            step_layout.addWidget(label)
            journey_steps.addWidget(step)
        journey_layout.addLayout(journey_steps)
        layout.addWidget(journey_panel)
        layout.addStretch()
        return page

    def _build_resident_application_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("My application")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        application = self.db.get_resident_application(self.display_name)

        panel = QWidget()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        if application is None:
            empty = QLabel(
                "No application is linked to your account yet. "
                "Please contact your coordinator for help with onboarding."
            )
            empty.setObjectName("supportNote")
            empty.setWordWrap(True)
            panel_layout.addWidget(empty)
        else:
            status_row = QHBoxLayout()
            status_title = QLabel("Current status")
            status_title.setObjectName("detailLabel")
            status_row.addWidget(status_title)
            status_row.addStretch()
            status_row.addWidget(self._status_badge(application["status"]))
            panel_layout.addLayout(status_row)
            for label, key in (
                ("Accommodation type", "type_name"),
                ("Location", "location"),
                ("Last update", "last_update"),
                ("Notes from your team", "notes"),
            ):
                value = QLabel(application.get(key) or "No update yet")
                value.setObjectName("detailValue")
                value.setWordWrap(True)
                label_widget = QLabel(label)
                label_widget.setObjectName("detailLabel")
                panel_layout.addWidget(label_widget)
                panel_layout.addWidget(value)

        layout.addWidget(panel)
        layout.addStretch()
        return page

    def _build_resident_meetings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Shared schedule")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        note = QLabel(
            "These are the team’s shared events. Contact your coordinator "
            "if you need to confirm whether an event is for you."
        )
        note.setObjectName("supportNote")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.resident_meeting_table = QTableWidget(0, 4)
        self.resident_meeting_table.setHorizontalHeaderLabels(
            ["Session", "Date and time", "Mentor", "Status"]
        )
        self.resident_meeting_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.resident_meeting_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.resident_meeting_table.verticalHeader().setVisible(False)
        self.resident_meeting_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.resident_meeting_table.setAlternatingRowColors(True)
        self.resident_meeting_table.horizontalHeader().setStretchLastSection(True)
        rows = [
            meeting
            for meeting in self.db.list_meetings()
            if not meeting.get("resident_name")
            or meeting["resident_name"] == self.display_name
        ]
        self.resident_meeting_table.setRowCount(len(rows))
        for row_index, meeting in enumerate(rows):
            self.resident_meeting_table.setItem(
                row_index, 0, QTableWidgetItem(meeting["title"])
            )
            self.resident_meeting_table.setItem(
                row_index, 1, QTableWidgetItem(meeting["meeting_time"])
            )
            self.resident_meeting_table.setItem(
                row_index, 2, QTableWidgetItem(meeting.get("mentor_name") or "Community team")
            )
            self.resident_meeting_table.setItem(
                row_index, 3, self._colored_item(meeting["status"], "status")
            )
        layout.addWidget(self.resident_meeting_table)
        return page

    def _build_resident_support_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        title = QLabel("Support and guidance")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        panel = QWidget()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        heading = QLabel("Need help with your next step?")
        heading.setObjectName("panelTitle")
        panel_layout.addWidget(heading)
        guidance = QLabel(
            "Your coordinator is the best person to help with accommodation, "
            "documents, or application updates. When contacting them, include "
            "your name and the topic you need help with.\n\n"
            "If your application says “Needs follow-up”, check the latest note "
            "on My application and ask your coordinator what information is needed.\n\n"
            "You can send a message directly to your coordinator from the Messages page."
        )
        guidance.setObjectName("supportNote")
        guidance.setWordWrap(True)
        panel_layout.addWidget(guidance)
        layout.addWidget(panel)
        layout.addStretch()
        return page

    def _build_messages_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        title_group = QVBoxLayout()
        title = QLabel("Messages")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Keep important updates and conversations together.")
        subtitle.setObjectName("pageSubtitle")
        title_group.addWidget(title)
        title_group.addWidget(subtitle)
        header_row.addLayout(title_group)
        header_row.addStretch()
        compose_button = QPushButton("+  New message")
        compose_button.setObjectName("primaryButton")
        compose_button.clicked.connect(self._compose_message)
        header_row.addWidget(compose_button)
        layout.addLayout(header_row)

        self.message_table = QTableWidget(0, 5)
        self.message_table.setHorizontalHeaderLabels(
            ["ID", "Direction", "Subject", "Conversation with", "Received"]
        )
        self.message_table.setColumnHidden(0, True)
        self.message_table.setAlternatingRowColors(True)
        self.message_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.message_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.message_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.message_table.verticalHeader().setVisible(False)
        self.message_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.message_table.horizontalHeader().setStretchLastSection(True)
        self.message_table.currentCellChanged.connect(self._show_selected_message)
        layout.addWidget(self.message_table, 3)

        preview = QWidget()
        preview.setObjectName("panel")
        preview_layout = QVBoxLayout(preview)
        self.message_preview_title = QLabel("Select a message")
        self.message_preview_title.setObjectName("panelTitle")
        self.message_preview_from = QLabel("")
        self.message_preview_from.setObjectName("pageSubtitle")
        self.message_preview_body = QLabel("Your selected message will appear here.")
        self.message_preview_body.setWordWrap(True)
        self.message_preview_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        preview_layout.addWidget(self.message_preview_title)
        preview_layout.addWidget(self.message_preview_from)
        preview_layout.addWidget(self.message_preview_body)
        layout.addWidget(preview, 1)
        self._refresh_messages()
        return page

    def _build_applications_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        title_group = QVBoxLayout()
        header = QLabel("Applications")
        header.setObjectName("pageTitle")
        subtitle = QLabel("Review, search and manage resident applications.")
        subtitle.setObjectName("pageSubtitle")
        title_group.addWidget(header)
        title_group.addWidget(subtitle)
        header_row.addLayout(title_group)
        header_row.addStretch()
        add_btn = QPushButton("+  New application")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_application)
        header_row.addWidget(add_btn)
        layout.addLayout(header_row)

        toolbar = QHBoxLayout()
        self.application_search = QLineEdit()
        self.application_search.setPlaceholderText(
            "Search by name, accommodation or location"
        )
        self.application_search.textChanged.connect(self._refresh_applications)
        toolbar.addWidget(self.application_search)
        self.application_status_filter = QComboBox()
        self.application_status_filter.addItems(
            ["All statuses", "Pending", "In review", "Approved", "Needs follow-up"]
        )
        self.application_status_filter.currentTextChanged.connect(
            self._refresh_applications
        )
        toolbar.addWidget(self.application_status_filter)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_application)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("dangerButton")
        delete_btn.clicked.connect(self._delete_application)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        layout.addLayout(toolbar)

        self.application_count = QLabel("")
        self.application_count.setObjectName("pageSubtitle")
        layout.addWidget(self.application_count)
        self.application_table = QTableWidget(0, 8)
        self.application_table.setHorizontalHeaderLabels(
            ["ID", "Applicant", "Accommodation", "Location", "Status", "Priority", "Updated", "Record check"]
        )
        self.application_table.setColumnHidden(0, True)
        self.application_table.setAlternatingRowColors(True)
        self.application_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.application_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.application_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.application_table.verticalHeader().setVisible(False)
        self.application_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.application_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.application_table)
        self._refresh_applications()
        return page

    def _build_meetings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)
        header = QLabel("Mentor sessions")
        header.setObjectName("pageTitle")
        layout.addWidget(header)
        subtitle = QLabel("Plan interviews, follow-ups and community check-ins.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.meeting_search = QLineEdit()
        self.meeting_search.setPlaceholderText("Search sessions, mentors or residents")
        self.meeting_search.textChanged.connect(self._refresh_meetings)
        toolbar.addWidget(self.meeting_search)
        add_btn = QPushButton("+  Schedule session")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_meeting)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_meeting)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("dangerButton")
        delete_btn.clicked.connect(self._delete_meeting)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        layout.addLayout(toolbar)

        self.meeting_table = QTableWidget(0, 6)
        self.meeting_table.setHorizontalHeaderLabels(
            ["ID", "Session", "Date and time", "Mentor", "Resident", "Status"]
        )
        self.meeting_table.setColumnHidden(0, True)
        self.meeting_table.setAlternatingRowColors(True)
        self.meeting_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.meeting_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.meeting_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.meeting_table.verticalHeader().setVisible(False)
        self.meeting_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.meeting_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.meeting_table)
        self._refresh_meetings()
        return page

    def _build_residents_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        header = QLabel("Residents")
        header.setObjectName("pageTitle")
        layout.addWidget(header)
        subtitle = QLabel(
            "Find residents and review their accommodation, application progress, "
            "and assigned support sessions."
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        metrics = QHBoxLayout()
        metrics.setSpacing(14)
        self.residents_total_card = DashboardCard(
            "Resident records", "0", "People in the resident directory", "#7084bb"
        )
        self.residents_applications_card = DashboardCard(
            "Linked applications", "0", "Resident records with an application", "#4f9c9b"
        )
        self.residents_sessions_card = DashboardCard(
            "Assigned sessions", "0", "Sessions linked to a resident", "#dc9a37"
        )
        for card in (
            self.residents_total_card,
            self.residents_applications_card,
            self.residents_sessions_card,
        ):
            metrics.addWidget(card)
        layout.addLayout(metrics)

        toolbar = QHBoxLayout()
        self.resident_search = QLineEdit()
        self.resident_search.setPlaceholderText("Search by resident or accommodation")
        self.resident_search.textChanged.connect(self._refresh_residents)
        toolbar.addWidget(self.resident_search)
        add_btn = QPushButton("+  Add resident")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_resident)
        edit_btn = QPushButton("Edit selected")
        edit_btn.clicked.connect(self._edit_resident)
        delete_btn = QPushButton("Delete selected")
        delete_btn.setObjectName("dangerButton")
        delete_btn.clicked.connect(self._delete_resident)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(delete_btn)
        layout.addLayout(toolbar)

        self.resident_table = QTableWidget(0, 5)
        self.resident_table.setHorizontalHeaderLabels(
            ["ID", "Resident", "Accommodation", "Application", "Next session"]
        )
        self.resident_table.setAlternatingRowColors(True)
        self.resident_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.resident_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.resident_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.resident_table.verticalHeader().setVisible(False)
        self.resident_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.resident_table.horizontalHeader().setStretchLastSection(True)
        self.resident_table.setColumnHidden(0, True)
        self.resident_table.setIconSize(QSize(34, 34))
        self.resident_table.verticalHeader().setDefaultSectionSize(54)
        layout.addWidget(self.resident_table)
        self.residents_empty_state = QLabel()
        self.residents_empty_state.setObjectName("emptyState")
        self.residents_empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.residents_empty_state.setWordWrap(True)
        self.residents_empty_state.hide()
        layout.addWidget(self.residents_empty_state)
        self._refresh_residents()
        return page

    def _refresh_messages(self):
        messages = self.db.list_messages(self.username)
        self.messages_by_id = {message["id"]: message for message in messages}
        user_names = {
            user["username"]: user["display_name"] or user["username"]
            for user in self.db.list_users()
        }
        self.message_table.setRowCount(len(messages))
        for row_index, message in enumerate(messages):
            incoming = message["recipient_username"] == self.username
            other_user = (
                message["sender_username"] if incoming else message["recipient_username"]
            )
            other_user = user_names.get(other_user, other_user)
            direction = (
                "Unread"
                if incoming and not message["is_read"]
                else "Received" if incoming else "Sent"
            )
            values = [
                str(message["id"]),
                direction,
                message["subject"],
                other_user,
                message["created_at"],
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    cell.setForeground(QColor("#2f6e9f" if incoming else "#687588"))
                if column == 2 and incoming and not message["is_read"]:
                    font = cell.font()
                    font.setWeight(QFont.Weight.Bold)
                    cell.setFont(font)
                self.message_table.setItem(row_index, column, cell)

    def _show_selected_message(
        self,
        row: int,
        _column: int,
        _previous_row: int,
        _previous_column: int,
    ):
        if row < 0:
            return
        id_item = self.message_table.item(row, 0)
        if id_item is None:
            return
        message = self.messages_by_id.get(int(id_item.text()))
        if message is None:
            return
        incoming = message["recipient_username"] == self.username
        other_user = (
            message["sender_username"] if incoming else message["recipient_username"]
        )
        other_user = next(
            (
                user["display_name"] or user["username"]
                for user in self.db.list_users()
                if user["username"] == other_user
            ),
            other_user,
        )
        self.message_preview_title.setText(message["subject"])
        self.message_preview_from.setText(
            f"From {other_user}" if incoming else f"To {other_user}"
        )
        self.message_preview_body.setText(message["body"])
        if incoming and not message["is_read"]:
            self.db.mark_message_read(message["id"], self.username)
            message["is_read"] = 1
            self.message_table.item(row, 1).setText("Received")
            self.message_table.item(row, 2).setFont(QFont())

    def _compose_message(self):
        recipient_role = "resident" if self.is_admin else "admin"
        recipients = [
            (user["username"], user["display_name"] or user["username"])
            for user in self.db.list_users(recipient_role)
            if user["username"] != self.username
        ]
        if not recipients:
            self._show_error("There is no available recipient for this message.")
            return
        dialog = MessageDialog(recipients, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            message = dialog.data()
            self.db.send_message(
                self.username,
                message["recipient"],
                message["subject"],
                message["body"],
            )
            self._refresh_messages()
            QMessageBox.information(self, "Message sent", "Your message has been sent.")

    def _build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)
        header = QLabel("Settings")
        header.setObjectName("pageTitle")
        layout.addWidget(header)
        subtitle = QLabel(
            "Review the account and access level used in this WeRhere workspace."
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        account_panel = QWidget()
        account_panel.setObjectName("panel")
        account_layout = QHBoxLayout(account_panel)
        account_layout.setContentsMargins(22, 20, 22, 20)
        account_layout.setSpacing(18)
        avatar = QLabel(self.display_name[:1].upper())
        avatar.setObjectName("accountAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(58, 58)
        account_layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        identity = QVBoxLayout()
        account_title = QLabel("Signed-in account")
        account_title.setObjectName("panelTitle")
        identity.addWidget(account_title)
        display_name = QLabel(self.display_name)
        display_name.setObjectName("accountName")
        identity.addWidget(display_name)
        username = QLabel(f"Username: {self.username}")
        username.setObjectName("pageSubtitle")
        identity.addWidget(username)
        account_layout.addLayout(identity, 1)
        layout.addWidget(account_panel)

        information_row = QHBoxLayout()
        information_row.setSpacing(16)
        access_panel = QWidget()
        access_panel.setObjectName("panel")
        access_layout = QVBoxLayout(access_panel)
        access_title = QLabel("Your access")
        access_title.setObjectName("panelTitle")
        access_layout.addWidget(access_title)
        role_name = "Administrator" if self.is_admin else "Resident"
        role_badge = QLabel(role_name)
        role_badge.setObjectName("roleBadge")
        role_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role_badge.setMaximumWidth(150)
        access_layout.addWidget(role_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        access_description = QLabel(
            "Manage applications, mentor sessions, resident records, and messages."
            if self.is_admin
            else "View your own application, shared schedule, support guidance, and messages."
        )
        access_description.setObjectName("pageSubtitle")
        access_description.setWordWrap(True)
        access_layout.addWidget(access_description)
        access_layout.addStretch()

        workspace_panel = QWidget()
        workspace_panel.setObjectName("panel")
        workspace_layout = QVBoxLayout(workspace_panel)
        workspace_title = QLabel("Workspace data")
        workspace_title.setObjectName("panelTitle")
        workspace_layout.addWidget(workspace_title)
        workspace_description = QLabel(
            "This desktop workspace stores its records in a local SQLite database. "
            "It does not sync messages or data to a hosted service."
        )
        workspace_description.setObjectName("pageSubtitle")
        workspace_description.setWordWrap(True)
        workspace_layout.addWidget(workspace_description)
        workspace_layout.addStretch()
        information_row.addWidget(access_panel)
        information_row.addWidget(workspace_panel)
        layout.addLayout(information_row)

        action_row = QHBoxLayout()
        action_row.addStretch()
        logout_btn = QPushButton("Sign out")
        logout_btn.setObjectName("secondaryButton")
        logout_btn.clicked.connect(self.close)
        action_row.addWidget(logout_btn)
        layout.addLayout(action_row)
        layout.addStretch()
        return page

    def _refresh_dashboard(self):
        stats = self.db.dashboard_stats()
        rows = stats["recent"]
        self.dashboard_table.setRowCount(len(rows))
        self.dashboard_table.setColumnCount(4)
        self.dashboard_table.setHorizontalHeaderLabels(
            ["Applicant", "Accommodation", "Status", "Priority"]
        )
        for row_index, item in enumerate(rows):
            self.dashboard_table.setItem(row_index, 0, QTableWidgetItem(item["applicant_name"]))
            self.dashboard_table.setItem(row_index, 1, QTableWidgetItem(item["type_name"]))
            self.dashboard_table.setItem(
                row_index, 2, self._colored_item(item["status"])
            )
            self.dashboard_table.setItem(
                row_index, 3, self._colored_item(item["priority"], "priority")
            )
        self.application_metric.set_value(str(stats["applications_total"]))
        self.attention_metric.set_value(str(stats["needs_attention"]))
        self.meeting_metric.set_value(str(stats["meetings_total"]))
        self.resident_metric.set_value(str(stats["residents_total"]))
        while self.attention_list.count():
            item = self.attention_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        needs_action = [
            application
            for application in self.db.list_applications()
            if application["status"] in ("Pending", "In review", "Needs follow-up")
        ]
        needs_action.sort(
            key=lambda application: (
                application["priority"] != "High",
                application["applicant_name"].casefold(),
            )
        )
        for application in needs_action[:3]:
            row = QFrame()
            row.setObjectName("attentionRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 9, 12, 9)
            row_layout.setSpacing(7)
            name = QLabel(application["applicant_name"])
            name.setObjectName("eventTitle")
            detail = QLabel(
                f"{application['location']}  ·  {application['priority']} priority"
            )
            detail.setObjectName("pageSubtitle")
            row_layout.addWidget(name)
            row_layout.addWidget(self._status_badge(application["status"]))
            row_layout.addWidget(detail)
            self.attention_list.addWidget(row)
        if not needs_action:
            empty = QLabel("Everything is up to date.")
            empty.setObjectName("pageSubtitle")
            self.attention_list.addWidget(empty)
        while self.upcoming_list.count():
            item = self.upcoming_list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        upcoming = sorted(
            self.db.list_meetings(), key=lambda meeting: meeting["meeting_time"]
        )[:4]
        if not upcoming:
            empty = QLabel("No sessions scheduled yet.")
            empty.setObjectName("pageSubtitle")
            self.upcoming_list.addWidget(empty)
        for meeting in upcoming:
            event = QFrame()
            event.setObjectName("eventRow")
            event_layout = QVBoxLayout(event)
            event_layout.setContentsMargins(12, 10, 12, 10)
            event_layout.setSpacing(3)
            event_title = QLabel(meeting["title"])
            event_title.setObjectName("eventTitle")
            event_time = QLabel(meeting["meeting_time"])
            event_time.setObjectName("pageSubtitle")
            event_layout.addWidget(event_title)
            event_layout.addWidget(event_time)
            self.upcoming_list.addWidget(event)

    def _refresh_applications(self, _value: str = ""):
        query = self.application_search.text().strip()
        status_filter = self.application_status_filter.currentText()
        rows = self.db.list_applications(query)
        if status_filter != "All statuses":
            rows = [row for row in rows if row["status"] == status_filter]
        names = Counter(
            item["applicant_name"].strip().casefold()
            for item in self.db.list_applications()
        )
        self.application_count.setText(
            f"{len(rows)} applications"
            + (
                f"  ·  {sum(count > 1 for count in names.values())} possible duplicate names"
                if any(count > 1 for count in names.values())
                else ""
            )
        )
        self.application_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            self.application_table.setItem(row_index, 0, QTableWidgetItem(str(item["id"])))
            self.application_table.setItem(row_index, 1, QTableWidgetItem(item["applicant_name"]))
            self.application_table.setItem(row_index, 2, QTableWidgetItem(item["type_name"]))
            self.application_table.setItem(row_index, 3, QTableWidgetItem(item["location"]))
            self.application_table.setItem(
                row_index, 4, self._colored_item(item["status"])
            )
            self.application_table.setItem(
                row_index, 5, self._colored_item(item["priority"], "priority")
            )
            self.application_table.setItem(row_index, 6, QTableWidgetItem(item["last_update"]))
            duplicate = names[item["applicant_name"].strip().casefold()] > 1
            check = QTableWidgetItem("Review name" if duplicate else "No match")
            check.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            check.setBackground(QColor("#fff4d8" if duplicate else "#e4f5ec"))
            check.setForeground(QColor("#976b15" if duplicate else "#287a54"))
            if duplicate:
                check.setToolTip(
                    "Another application has the same applicant name. Review before merging."
                )
            self.application_table.setItem(row_index, 7, check)

    def _refresh_meetings(self, query: str = None):
        if query is None:
            query = self.meeting_search.text()
        rows = self.db.list_meetings(query)
        self.meeting_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            self.meeting_table.setItem(row_index, 0, QTableWidgetItem(str(item["id"])))
            self.meeting_table.setItem(row_index, 1, QTableWidgetItem(item["title"]))
            self.meeting_table.setItem(row_index, 2, QTableWidgetItem(item["meeting_time"]))
            self.meeting_table.setItem(
                row_index, 3, QTableWidgetItem(item.get("mentor_name") or "Community team")
            )
            self.meeting_table.setItem(
                row_index, 4, QTableWidgetItem(item.get("resident_name", "") or "Not assigned")
            )
            self.meeting_table.setItem(
                row_index, 5, self._colored_item(item["status"])
            )

    def _refresh_residents(self, query: str = None):
        if query is None:
            query = self.resident_search.text()
        all_residents = self.db.list_residents()
        applications = {}
        for application in self.db.list_applications():
            applications.setdefault(
                application["applicant_name"].strip().casefold(), application
            )
        meetings_by_resident = {}
        for meeting in sorted(
            self.db.list_meetings(), key=lambda item: item["meeting_time"]
        ):
            resident_name = meeting.get("resident_name", "").strip().casefold()
            if resident_name:
                meetings_by_resident.setdefault(resident_name, meeting)

        normalized_query = query.strip().casefold()
        rows = [
            resident
            for resident in all_residents
            if not normalized_query
            or any(
                normalized_query in str(value or "").casefold()
                for value in (
                    resident["name"],
                    resident["role"],
                    resident.get("description"),
                    (
                        applications.get(resident["name"].strip().casefold()) or {}
                    ).get("type_name"),
                    (
                        applications.get(resident["name"].strip().casefold()) or {}
                    ).get("status"),
                )
            )
        ]
        application_count = sum(
            resident["name"].strip().casefold() in applications
            for resident in all_residents
        )
        assigned_session_count = sum(
            resident["name"].strip().casefold() in meetings_by_resident
            for resident in all_residents
        )
        self.resident_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            self.resident_table.setItem(row_index, 0, QTableWidgetItem(str(item["id"])))
            resident_name = item["name"]
            name_item = QTableWidgetItem(resident_name)
            avatar_color = QColor(item["color"])
            if not avatar_color.isValid():
                avatar_color = QColor("#DCE7F5")
            initials = item.get("initials") or resident_name[:2].upper()
            name_item.setIcon(
                QIcon(AvatarCard._make_avatar(initials, avatar_color.name()))
            )
            self.resident_table.setItem(row_index, 1, name_item)

            normalized_name = resident_name.strip().casefold()
            application = applications.get(normalized_name)
            if application:
                accommodation = application["type_name"]
                self.resident_table.setItem(
                    row_index, 3, self._colored_item(application["status"])
                )
            else:
                accommodation = item["role"]
                self.resident_table.setItem(
                    row_index, 3, QTableWidgetItem("No application linked")
                )
            self.resident_table.setItem(
                row_index, 2, QTableWidgetItem(accommodation)
            )

            meeting = meetings_by_resident.get(normalized_name)
            if meeting:
                session_time = meeting["meeting_time"]
                try:
                    session_time = datetime.strptime(
                        session_time, "%Y-%m-%d %H:%M"
                    ).strftime("%d %b %Y, %H:%M")
                except ValueError:
                    pass
                self.resident_table.setItem(
                    row_index, 4, QTableWidgetItem(session_time)
                )
            else:
                self.resident_table.setItem(
                    row_index, 4, QTableWidgetItem("Not scheduled")
                )

        self.resident_table.setVisible(bool(rows))
        self.residents_empty_state.setVisible(not rows)
        if not rows:
            self.residents_empty_state.setText(
                "No residents match your search."
                if normalized_query
                else "No resident records yet. Use “Add resident” to create the first record."
            )
        self.residents_total_card.set_value(str(len(all_residents)))
        self.residents_applications_card.set_value(str(application_count))
        self.residents_sessions_card.set_value(str(assigned_session_count))

    def _add_application(self):
        dialog = ApplicationDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.data()
            if not payload["applicant_name"] or not payload["type_name"]:
                self._show_error("Applicant name and type are required.")
                return
            self.db.add_application(payload)
            self._refresh_applications()
            self._refresh_dashboard()

    def _edit_application(self):
        selected = self.application_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select an application first.")
            return
        row_index = selected[0].row()
        application_id = int(self.application_table.item(row_index, 0).text())
        record = next(item for item in self.db.list_applications() if item["id"] == application_id)
        dialog = ApplicationDialog(record, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.db.update_application(application_id, dialog.data())
            self._refresh_applications()
            self._refresh_dashboard()

    def _delete_application(self):
        selected = self.application_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select an application to delete.")
            return
        row_index = selected[0].row()
        id_value = int(self.application_table.item(row_index, 0).text())
        self.db.delete_application(id_value)
        self._refresh_applications()
        self._refresh_dashboard()

    def _add_meeting(self):
        dialog = MeetingDialog(residents=self.db.list_residents(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.data()
            if not payload["title"]:
                self._show_error("Meeting title is required.")
                return
            if not self._valid_meeting_time(payload["meeting_time"]):
                self._show_error("Enter the date and time as YYYY-MM-DD HH:MM.")
                return
            self.db.add_meeting(payload)
            self._refresh_meetings()
            self._refresh_dashboard()

    def _edit_meeting(self):
        selected = self.meeting_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select a meeting first.")
            return
        row_index = selected[0].row()
        meeting_id = int(self.meeting_table.item(row_index, 0).text())
        record = next(item for item in self.db.list_meetings() if item["id"] == meeting_id)
        dialog = MeetingDialog(
            record, residents=self.db.list_residents(), parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.data()
            if not payload["title"]:
                self._show_error("Meeting title is required.")
                return
            if not self._valid_meeting_time(payload["meeting_time"]):
                self._show_error("Enter the date and time as YYYY-MM-DD HH:MM.")
                return
            self.db.update_meeting(meeting_id, payload)
            self._refresh_meetings()
            self._refresh_dashboard()

    @staticmethod
    def _valid_meeting_time(value: str) -> bool:
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            return False
        return True

    def _delete_meeting(self):
        selected = self.meeting_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select a meeting to delete.")
            return
        row_index = selected[0].row()
        item_id = int(self.meeting_table.item(row_index, 0).text())
        self.db.delete_meeting(item_id)
        self._refresh_meetings()
        self._refresh_dashboard()

    def _add_resident(self):
        dialog = ResidentDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.data()
            if not payload["name"] or not payload["role"]:
                self._show_error("Resident name and role are required.")
                return
            self.db.add_resident(payload)
            self._refresh_residents()
            self._refresh_dashboard()

    def _edit_resident(self):
        selected = self.resident_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select a resident first.")
            return
        row_index = selected[0].row()
        resident_id = int(self.resident_table.item(row_index, 0).text())
        record = next(item for item in self.db.list_residents() if item["id"] == resident_id)
        dialog = ResidentDialog(record, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.db.update_resident(resident_id, dialog.data())
            self._refresh_residents()
            self._refresh_dashboard()

    def _delete_resident(self):
        selected = self.resident_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select a resident to delete.")
            return
        row_index = selected[0].row()
        item_id = int(self.resident_table.item(row_index, 0).text())
        self.db.delete_resident(item_id)
        self._refresh_residents()
        self._refresh_dashboard()

    def _show_error(self, text: str):
        QMessageBox.warning(self, "WeRhere", text)


def main():
    import sys

    app = QApplication(sys.argv)
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        return

    window = WeRhereMainWindow(login.authenticated_user)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
