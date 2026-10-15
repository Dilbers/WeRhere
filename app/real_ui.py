from __future__ import annotations

from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import re
from urllib.parse import quote

from PyQt6.QtCore import QSettings, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QPainter, QPixmap
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
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .backend import DriveImportError, initialize_database
from .localization import LANGUAGES, translate


_UI_FONT_FAMILY: str | None = None
_CURRENT_LANGUAGE = "en"
_SOURCE_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 20


def _localized_stylesheet() -> str:
    style_path = Path(__file__).with_name("styles.qss")
    chevron_path = (
        Path(__file__).resolve().parent / "assets" / "chevron-down.svg"
    ).as_posix()
    return style_path.read_text(encoding="utf-8").replace(
        "@CHEVRON_DOWN@", chevron_path
    )


def _apply_language_to_widgets(root: QWidget, language: str) -> None:
    def translate_widget_text(widget: QWidget, property_name: str, getter, setter) -> None:
        source = widget.property(property_name)
        applied = widget.property(f"{property_name}Applied")
        current = getter()
        if source is None or current != applied:
            source = current
            widget.setProperty(property_name, source)
        translated = translate(source, language)
        setter(translated)
        widget.setProperty(f"{property_name}Applied", translated)

    for widget in root.findChildren(QWidget):
        translate_widget_text(
            widget,
            "languageSourceToolTip",
            widget.toolTip,
            widget.setToolTip,
        )
        if isinstance(widget, QLabel):
            translate_widget_text(
                widget,
                "languageSourceText",
                widget.text,
                widget.setText,
            )
        elif isinstance(widget, QPushButton):
            translate_widget_text(
                widget,
                "languageSourceText",
                widget.text,
                widget.setText,
            )

        if isinstance(widget, QLineEdit):
            translate_widget_text(
                widget,
                "languageSourcePlaceholder",
                widget.placeholderText,
                widget.setPlaceholderText,
            )
        elif isinstance(widget, QTextEdit):
            translate_widget_text(
                widget,
                "languageSourcePlaceholder",
                widget.placeholderText,
                widget.setPlaceholderText,
            )

        if isinstance(widget, QComboBox) and widget.objectName() != "languageSelector":
            was_blocked = widget.blockSignals(True)
            for index in range(widget.count()):
                source = widget.itemData(index, _SOURCE_TEXT_ROLE)
                if source is None:
                    source = widget.itemText(index)
                    widget.setItemData(index, source, _SOURCE_TEXT_ROLE)
                widget.setItemText(index, translate(source, language))
            widget.blockSignals(was_blocked)

        if isinstance(widget, QTableWidget):
            for column in range(widget.columnCount()):
                header = widget.horizontalHeaderItem(column)
                if header is not None:
                    source = header.data(_SOURCE_TEXT_ROLE)
                    if source is None:
                        source = header.text()
                        header.setData(_SOURCE_TEXT_ROLE, source)
                    header.setText(translate(source, language))
            for row in range(widget.rowCount()):
                for column in range(widget.columnCount()):
                    item = widget.item(row, column)
                    if item is not None:
                        source = item.data(_SOURCE_TEXT_ROLE)
                        if source is not None:
                            item.setText(translate(source, language))


def _applicant_status_legend() -> QWidget:
    legend = QWidget()
    legend.setObjectName("statusLegend")
    row = QHBoxLayout(legend)
    row.setContentsMargins(0, 2, 0, 2)
    row.setSpacing(12)

    title = QLabel("Name color (based on Current Status and Processing Status):")
    title.setObjectName("statusLegendTitle")
    row.addWidget(title)

    for label, color in (
        ("Done", "#287a54"),
        ("Moved into housing", "#2f6e9f"),
        ("Waiting", "#976b15"),
        ("Other", "#687588"),
    ):
        entry = QWidget()
        entry_row = QHBoxLayout(entry)
        entry_row.setContentsMargins(0, 0, 0, 0)
        entry_row.setSpacing(5)
        dot = QLabel()
        dot.setObjectName("statusLegendDot")
        dot.setFixedSize(15, 15)
        dot.setStyleSheet(f"background-color: {color}; border-radius: 7px;")
        dot.setAccessibleName(f"{label} color")
        text = QLabel(label)
        text.setObjectName("statusLegendLabel")
        entry_row.addWidget(dot)
        entry_row.addWidget(text)
        row.addWidget(entry)

    row.addStretch(1)
    return legend


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
        logo_path = Path(__file__).resolve().parent / "assets" / "brand-logo2.png"
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
        self.settings = QSettings("WeRhere", "CommunityWorkspace")
        self.language = self.settings.value("language", "en", type=str)
        if self.language not in {code for _name, code in LANGUAGES}:
            self.language = "en"
        global _CURRENT_LANGUAGE
        _CURRENT_LANGUAGE = self.language
        self.setWindowTitle(translate("WeRhere | Welcome", self.language))
        self.setFixedSize(820, 600)
        self.setStyleSheet(_localized_stylesheet())
        self.db = initialize_database()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.auth_stack = QStackedWidget()
        self.welcome_page = self._build_welcome_page()
        self.sign_in_page = self._build_sign_in_page()
        self.auth_stack.addWidget(self.welcome_page)
        self.auth_stack.addWidget(self.sign_in_page)
        layout.addWidget(self.auth_stack)
        self.auth_stack.setCurrentWidget(self.welcome_page)
        self._sync_language_selectors()
        _apply_language_to_widgets(self, self.language)

    def _create_language_selector(self) -> QComboBox:
        selector = QComboBox()
        selector.setObjectName("languageSelector")
        selector.setMinimumWidth(148)
        for name, code in LANGUAGES:
            selector.addItem(f"{code.upper()}  ·  {name}", code)
        selector.setCurrentIndex(
            max(0, selector.findData(self.language))
        )
        selector.currentIndexChanged.connect(self._change_language)
        return selector

    def _sync_language_selectors(self) -> None:
        selectors = self.findChildren(QComboBox, "languageSelector")
        for selector in selectors:
            index = selector.findData(self.language)
            if index >= 0 and selector.currentIndex() != index:
                selector.blockSignals(True)
                selector.setCurrentIndex(index)
                selector.blockSignals(False)

    def _change_language(self, _index: int) -> None:
        selector = self.sender()
        if not isinstance(selector, QComboBox):
            return
        self.language = selector.currentData()
        global _CURRENT_LANGUAGE
        _CURRENT_LANGUAGE = self.language
        self.settings.setValue("language", self.language)
        self.error_label.clear()
        self.setWindowTitle(
            translate("WeRhere | Welcome", self.language)
            if self.auth_stack.currentWidget() is self.welcome_page
            else translate("WeRhere | Sign in", self.language)
        )
        self._sync_language_selectors()
        _apply_language_to_widgets(self, self.language)

    def _build_welcome_page(self):
        page = QWidget()
        page.setObjectName("welcomePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(44, 28, 44, 30)
        layout.setSpacing(22)

        header = QHBoxLayout()
        header.addWidget(BrandLogoWidget(210, 62))
        header.addStretch()
        access_label = QLabel("VIT CANDIDATE CRM")
        access_label.setObjectName("accessLabel")
        header.addWidget(access_label)
        header.addSpacing(12)
        header.addWidget(self._create_language_selector())
        layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(24)
        welcome_content = QVBoxLayout()
        welcome_content.setSpacing(14)

        eyebrow = QLabel("CANDIDATE PROGRESS, IN ONE PLACE")
        eyebrow.setObjectName("welcomeEyebrow")
        welcome_content.addWidget(eyebrow)
        title = QLabel("Welcome to\nWeRhere")
        title.setObjectName("welcomeTitle")
        title.setWordWrap(True)
        welcome_content.addWidget(title)
        introduction = QLabel(
            "Review IT training applications, mentor recommendations, and project interviews."
        )
        introduction.setObjectName("welcomeDescription")
        introduction.setWordWrap(True)
        welcome_content.addWidget(introduction)
        welcome_content.addSpacing(6)

        benefits = QVBoxLayout()
        benefits.setSpacing(12)
        for text in (
            "Find applicants and review mentor assignment status",
            "Read mentor recommendations, scores, and notes",
            "Track projects sent to candidates and received back",
        ):
            item = QLabel(f"✓   {text}")
            item.setObjectName("welcomeBenefit")
            item.setWordWrap(True)
            benefits.addWidget(item)
        welcome_content.addLayout(benefits)
        welcome_content.addStretch()
        sign_in_button = QPushButton("Sign in to your account")
        sign_in_button.setObjectName("primaryButton")
        sign_in_button.setMinimumHeight(48)
        sign_in_button.clicked.connect(self._show_sign_in)
        welcome_content.addWidget(sign_in_button)

        sign_up_note = QLabel(
            "Need access? Contact your programme coordinator."
        )
        sign_up_note.setObjectName("welcomeFootnote")
        sign_up_note.setWordWrap(True)
        welcome_content.addWidget(sign_up_note)
        content.addLayout(welcome_content, 3)

        highlight = QFrame()
        highlight.setObjectName("welcomeHighlight")
        highlight_layout = QVBoxLayout(highlight)
        highlight_layout.setContentsMargins(24, 26, 24, 26)
        highlight_layout.setSpacing(16)
        highlight_label = QLabel("THE CANDIDATE JOURNEY")
        highlight_label.setObjectName("highlightEyebrow")
        highlight_layout.addWidget(highlight_label)
        highlight_title = QLabel("From application to interview.")
        highlight_title.setObjectName("highlightTitle")
        highlight_title.setWordWrap(True)
        highlight_layout.addWidget(highlight_title)
        highlight_description = QLabel(
            "Keep applications, mentor reviews, and project progress visible together."
        )
        highlight_description.setObjectName("highlightDescription")
        highlight_description.setWordWrap(True)
        highlight_layout.addWidget(highlight_description)
        highlight_layout.addStretch()
        for number, caption in (
            ("01", "Applications"),
            ("02", "Mentor interviews"),
            ("03", "Project interviews"),
        ):
            line = QHBoxLayout()
            number_label = QLabel(number)
            number_label.setObjectName("highlightNumber")
            caption_label = QLabel(caption)
            caption_label.setObjectName("highlightCaption")
            line.addWidget(number_label)
            line.addWidget(caption_label)
            line.addStretch()
            highlight_layout.addLayout(line)
        content.addWidget(highlight, 2)
        layout.addLayout(content, 1)

        footer = QLabel("One clear workspace for the VIT programme.")
        footer.setObjectName("welcomeFooter")
        layout.addWidget(footer, alignment=Qt.AlignmentFlag.AlignHCenter)
        return page

    def _build_sign_in_page(self):
        page = QWidget()
        page.setObjectName("signInPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 28, 80, 30)
        layout.setSpacing(14)

        header = QHBoxLayout()
        back_button = QPushButton("←  Back")
        back_button.setObjectName("textButton")
        back_button.clicked.connect(self._show_welcome)
        header.addWidget(back_button)
        header.addStretch()
        header.addWidget(BrandLogoWidget(165, 48))
        header.addStretch()
        header.addWidget(self._create_language_selector())
        layout.addLayout(header)

        layout.addStretch()
        secure_access = QLabel("SECURE ACCESS")
        secure_access.setObjectName("welcomeEyebrow")
        layout.addWidget(secure_access)
        title = QLabel("Welcome back")
        title.setObjectName("loginTitle")
        layout.addWidget(title)
        introduction = QLabel("Sign in to continue to your WeRhere workspace.")
        introduction.setObjectName("pageSubtitle")
        layout.addWidget(introduction)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        self.username_edit = QLineEdit()
        self.username_edit.setMinimumHeight(42)
        self.username_edit.setPlaceholderText("Username")
        self.password_edit = QLineEdit()
        self.password_edit.setMinimumHeight(42)
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        username_label = QLabel("Username")
        username_label.setFixedWidth(81)
        username_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        username_row = QHBoxLayout()
        username_row.setSpacing(0)
        username_row.addWidget(username_label)
        username_row.addWidget(self.username_edit, 1)
        form.addLayout(username_row)
        password_row = QHBoxLayout()
        password_row.setSpacing(8)
        password_row.addWidget(self.password_edit, 1)
        self.password_visibility_button = QPushButton("Show")
        self.password_visibility_button.setObjectName("passwordVisibilityButton")
        self.password_visibility_button.setCheckable(True)
        self.password_visibility_button.toggled.connect(self._toggle_password_visibility)
        password_row.addWidget(self.password_visibility_button)
        password_label = QLabel("Password")
        password_label.setFixedWidth(81)
        password_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        password_labeled_row = QHBoxLayout()
        password_labeled_row.setSpacing(0)
        password_labeled_row.addWidget(password_label)
        password_labeled_row.addLayout(password_row, 1)
        form.addLayout(password_labeled_row)
        layout.addLayout(form)

        help_row = QHBoxLayout()
        self.account_help = QLabel("Accounts are provided by your coordinator.")
        self.account_help.setObjectName("pageSubtitle")
        help_row.addWidget(self.account_help)
        help_row.addStretch()
        self.forgot_password_button = QPushButton("Forgot password?")
        self.forgot_password_button.setObjectName("textButton")
        self.forgot_password_button.clicked.connect(self._show_password_help)
        help_row.addWidget(self.forgot_password_button)
        layout.addLayout(help_row)

        self.sign_in_button = QPushButton("Sign in")
        self.sign_in_button.setObjectName("primaryButton")
        self.sign_in_button.setMinimumHeight(46)
        self.sign_in_button.clicked.connect(self._attempt_login)
        layout.addWidget(self.sign_in_button)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorMessage")
        layout.addWidget(self.error_label)
        self.password_edit.returnPressed.connect(self._attempt_login)
        layout.addStretch()
        return page

    def _show_sign_in(self):
        self.setWindowTitle(translate("WeRhere | Sign in", self.language))
        self.auth_stack.setCurrentWidget(self.sign_in_page)
        self.username_edit.setFocus()

    def _show_welcome(self):
        self.setWindowTitle(translate("WeRhere | Welcome", self.language))
        self.auth_stack.setCurrentWidget(self.welcome_page)

    def _toggle_password_visibility(self, visible: bool):
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.password_visibility_button.setText("Hide" if visible else "Show")
        self.password_visibility_button.setProperty(
            "languageSourceText", "Hide" if visible else "Show"
        )
        self.password_visibility_button.setProperty(
            "languageSourceTextApplied", translate(
                "Hide" if visible else "Show", self.language
            )
        )
        self.password_visibility_button.setText(
            translate("Hide" if visible else "Show", self.language)
        )

    def _show_password_help(self):
        self.error_label.setText(
            translate(
                "Password reset is not available in this local app. "
                "Please contact your programme coordinator.",
                self.language,
            )
        )

    def _attempt_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        self.authenticated_user = self.db.get_authenticated_user(username, password)
        if self.authenticated_user is not None:
            self.accept()
        else:
            self.error_label.setText(
                translate("Invalid username or password.", self.language)
            )
            self.password_edit.clear()
            self.password_edit.setFocus()


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
        self.language = _CURRENT_LANGUAGE
        self.setStyleSheet(_localized_stylesheet())
        self.setWindowTitle(
            translate("Application" if record is None else "Edit Application", self.language)
        )
        self.resize(520, 420)

        self.applicant_name = QLineEdit(record["applicant_name"] if record else "")
        self.applicant_name.setPlaceholderText("Applicant's full name")
        self.type_name = QLineEdit(record["type_name"] if record else "")
        self.type_name.setPlaceholderText("Programme or application type")
        self.location = QLineEdit(record["location"] if record else "")
        self.location.setPlaceholderText("City or province")

        self.status = QComboBox()
        self.status.addItems(
            ["Pending", "In review", "Approved", "Needs follow-up", "DONE", "Not provided"]
        )
        if record and self.status.findText(record["status"]) < 0:
            self.status.addItem(record["status"])
        self.status.setCurrentText(record["status"] if record else "Pending")

        self.priority = QComboBox()
        self.priority.addItems(["High", "Medium", "Low", "Not specified"])
        if record and self.priority.findText(record["priority"]) < 0:
            self.priority.addItem(record["priority"])
        self.priority.setCurrentText(record["priority"] if record else "Medium")

        self.last_update = QLineEdit(record["last_update"] if record else "Today")
        self.last_update.setPlaceholderText("Date of the latest update")
        self.notes = QTextEdit(record["notes"] if record else "")
        self.notes.setPlaceholderText("Relevant application or follow-up notes")

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
        _apply_language_to_widgets(self, self.language)

    def data(self):
        return {
            "applicant_name": self.applicant_name.text().strip(),
            "type_name": self.type_name.text().strip(),
            "location": self.location.text().strip(),
            "status": self.status.currentData(_SOURCE_TEXT_ROLE),
            "priority": self.priority.currentData(_SOURCE_TEXT_ROLE),
            "last_update": self.last_update.text().strip() or "Today",
            "notes": self.notes.toPlainText().strip(),
        }


class ApplicationSourceDialog(QDialog):
    CURRENT_STATUS_OPTIONS = (
        "Moved into housing (studying the language and/or looking for a job and/or working)",
        "In the camp, waiting for residence-permit interview",
        "In the camp, received residence permit, municipality is assigned, waiting for housing",
        "Other",
    )
    MENTOR_MEETING_OPTIONS = ("OK", "NOT ASSIGNED", "Other")
    YES_NO_FIELDS = (
        "Municipal Pressure Regarding Work",
        "Completed Another IT Bootcamp",
        "Followed an Online IT Course",
        "Prior IT Work Experience",
        "Currently Involved in Another Project",
    )

    def __init__(self, headers, values=None, parent=None):
        super().__init__(parent)
        self.language = _CURRENT_LANGUAGE
        self.setStyleSheet(_localized_stylesheet())
        self.setWindowTitle(
            translate("New applicant" if values is None else "Edit applicant", self.language)
        )
        self.resize(760, 700)
        self.fields = {}
        self.original_values = values or {}
        placeholders = {
            "Timestamp": "YYYY-MM-DD",
            "Full Name": "Applicant's full name as provided",
            "Email": "Applicant's email address",
            "Phone": "Include the country code",
            "Desired Training": "Training requested in the application",
            "Province": "Province of residence",
            "Current Status": "Status from the application",
            "Processing Status": "Processing status from the register",
            "Mentor Meeting": "Mentor meeting status or details",
            "Application Period": "e.g. VIT3",
        }

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setObjectName("applicantFormScroll")
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_widget.setObjectName("applicantForm")
        form = QFormLayout(form_widget)
        values = values or {}
        for header in headers:
            current_value = "" if values.get(header) is None else str(values[header])
            if header == "Current Status":
                editor = self._choice_field(
                    self.CURRENT_STATUS_OPTIONS, current_value, allow_blank=True
                )
            elif header == "Mentor Meeting":
                editor = self._choice_field(
                    self.MENTOR_MEETING_OPTIONS, current_value, allow_blank=True
                )
            elif header in self.YES_NO_FIELDS:
                editor = self._choice_field(("Yes", "No"), current_value, allow_blank=True)
            else:
                editor = QLineEdit(current_value)
                editor.setPlaceholderText(
                    placeholders.get(header, f"Enter {header.lower()}")
                )
            self.fields[header] = editor
            form.addRow(header, editor)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorMessage")
        layout.addWidget(self.error_label)
        _apply_language_to_widgets(self, self.language)

    @staticmethod
    def _choice_field(options, current_value, allow_blank=False):
        editor = QComboBox()
        if allow_blank:
            editor.addItem("Select…", "")
            editor.setItemData(0, "Select…", _SOURCE_TEXT_ROLE)
        for option in options:
            editor.addItem(option, option)
            editor.setItemData(editor.count() - 1, option, _SOURCE_TEXT_ROLE)
        # Keep legacy source values available when editing, so opening and saving
        # an existing record does not silently replace its answer.
        if current_value and editor.findData(current_value) < 0:
            editor.addItem(current_value, current_value)
            editor.setItemData(editor.count() - 1, current_value, _SOURCE_TEXT_ROLE)
        if current_value:
            editor.setCurrentIndex(editor.findData(current_value))
        return editor

    def _accept_if_valid(self):
        name = self.fields.get("Full Name")
        if name is None or not name.text().strip():
            self.error_label.setText(
                translate("Candidate name is required.", self.language)
            )
            return
        self.accept()

    def data(self):
        values = {}
        for header, editor in self.fields.items():
            text = (
                editor.currentData()
                if isinstance(editor, QComboBox)
                else editor.text().strip()
            )
            original = self.original_values.get(header)
            values[header] = (
                original
                if (original is None and not text)
                or (original is not None and text == str(original))
                else text
            )
        if values.get("Full Name"):
            values["Full Name"] = str(values["Full Name"]).strip().title()
        return values


class MeetingDialog(QDialog):
    def __init__(self, record=None, parent=None, candidates=None, mentors=None):
        super().__init__(parent)
        self.language = _CURRENT_LANGUAGE
        self.setStyleSheet(_localized_stylesheet())
        self.setWindowTitle(
            translate("Schedule mentor interview" if record is None else "Edit mentor interview", self.language)
        )
        self.resize(480, 260)

        self.title = QLineEdit("Mentor interview")
        self.title.setReadOnly(True)
        self.meeting_time = QLineEdit(record["meeting_time"] if record else "")
        self.meeting_time.setPlaceholderText("YYYY-MM-DD HH:MM")
        self.mentor_name = QComboBox()
        self.mentor_name.setEditable(True)
        self.mentor_name.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for mentor in mentors or []:
            self.mentor_name.addItem(mentor, mentor)
        self.mentor_name.lineEdit().setPlaceholderText(
            translate("Select or type an interviewer", self.language)
        )
        if record and record.get("mentor_name"):
            self.mentor_name.setCurrentText(record["mentor_name"])
        self.mentor_name.setEditText(
            record.get("mentor_name", "") if record else ""
        )
        self.candidate_name = QComboBox()
        for candidate in candidates or []:
            self.candidate_name.addItem(candidate, candidate)
        if record:
            match = self.candidate_name.findData(record.get("resident_name", ""))
            if match < 0 and record.get("resident_name"):
                self.candidate_name.addItem(record["resident_name"])
                match = self.candidate_name.count() - 1
            self.candidate_name.setCurrentIndex(max(match, 0))
        self.status = QComboBox()
        self.status.addItems(["Scheduled", "Pending", "Approved", "Cancelled", "Completed"])
        self.status.setCurrentText(record["status"] if record else "Scheduled")

        form = QFormLayout(self)
        form.addRow("Title", self.title)
        form.addRow("Time", self.meeting_time)
        form.addRow("Mentor", self.mentor_name)
        form.addRow("Candidate", self.candidate_name)
        form.addRow("Status", self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)
        _apply_language_to_widgets(self, self.language)

    def data(self):
        return {
            "title": self.title.text().strip(),
            "meeting_time": self.meeting_time.text().strip(),
            "mentor_name": self.mentor_name.currentText().strip(),
            "resident_name": self.candidate_name.currentData() or "",
            "status": self.status.currentData(_SOURCE_TEXT_ROLE),
        }


class MentorOutcomeDialog(QDialog):
    def __init__(self, meeting, recommendation_options, vit_group="", parent=None):
        super().__init__(parent)
        self.language = _CURRENT_LANGUAGE
        self.setStyleSheet(_localized_stylesheet())
        self.setWindowTitle(translate("Record interview outcome", self.language))
        self.resize(560, 620)

        self.interview_date = QLineEdit(meeting["meeting_time"][:10])
        self.interview_date.setPlaceholderText("YYYY-MM-DD")
        self.vit_group = QLineEdit(vit_group)
        self.vit_group.setPlaceholderText("e.g. VIT3")
        self.candidate_name = QLineEdit(meeting["resident_name"])
        self.candidate_name.setReadOnly(True)
        self.mentor_name = QLineEdit(meeting["mentor_name"])
        self.mentor_name.setReadOnly(True)
        self.score = QLineEdit()
        self.score.setPlaceholderText(translate("Enter score", self.language))
        self.recommendation = QComboBox()
        self.recommendation.setEditable(True)
        self.recommendation.addItem("")
        for option in recommendation_options:
            if option and self.recommendation.findText(option) < 0:
                self.recommendation.addItem(option)
        self.alternative_recommendation = QLineEdit()
        self.secondary_score = QLineEdit()
        self.secondary_score.setPlaceholderText(translate("Enter score", self.language))
        self.notes = QTextEdit()

        form = QFormLayout(self)
        form.addRow("Date", self.interview_date)
        form.addRow("VIT Group", self.vit_group)
        form.addRow("Candidate Name", self.candidate_name)
        form.addRow("Mentor Name", self.mentor_name)
        form.addRow("Score", self.score)
        form.addRow("Recommendation", self.recommendation)
        form.addRow("Alternative Recommendation", self.alternative_recommendation)
        form.addRow("Secondary Score", self.secondary_score)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)
        _apply_language_to_widgets(self, self.language)

    def _accept_if_valid(self):
        try:
            datetime.strptime(self.interview_date.text().strip(), "%Y-%m-%d")
        except ValueError:
            QMessageBox.warning(self, "Invalid date", "Enter the interview date as YYYY-MM-DD.")
            return
        self.accept()

    def data(self):
        return {
            "Date": self.interview_date.text().strip(),
            "VIT Group": self.vit_group.text().strip(),
            "Candidate Name": self.candidate_name.text().strip(),
            "Mentor Name": self.mentor_name.text().strip(),
            "Score": self.score.text().strip(),
            "Recommendation": self.recommendation.currentText().strip(),
            "Alternative Recommendation": self.alternative_recommendation.text().strip(),
            "Secondary Score": self.secondary_score.text().strip(),
            "Notes": self.notes.toPlainText().strip(),
        }


class MessageDialog(QDialog):
    def __init__(self, recipients, parent=None):
        super().__init__(parent)
        self.language = _CURRENT_LANGUAGE
        self.setStyleSheet(_localized_stylesheet())
        self.setWindowTitle(translate("New message", self.language))
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
        _apply_language_to_widgets(self, self.language)

    def _accept_if_valid(self):
        if not self.recipient.currentData():
            self.error_label.setText(translate("Choose a recipient.", self.language))
        elif not self.subject.text().strip() or not self.body.toPlainText().strip():
            self.error_label.setText(
                translate("Add a subject and message before sending.", self.language)
            )
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
        self.language = _CURRENT_LANGUAGE
        self.setStyleSheet(_localized_stylesheet())
        self.setWindowTitle(
            translate("Resident" if record is None else "Edit Resident", self.language)
        )
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
        _apply_language_to_widgets(self, self.language)

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
    def __init__(self, user, language: str = "en"):
        super().__init__()
        _register_windows_font()
        self.language = language if language in {code for _name, code in LANGUAGES} else "en"
        global _CURRENT_LANGUAGE
        _CURRENT_LANGUAGE = self.language
        self.settings = QSettings("WeRhere", "CommunityWorkspace")
        self.settings.setValue("language", self.language)
        self.username = user["username"]
        self.display_name = user["display_name"] or self.username
        self.role = user["role"]
        self.is_admin = self.role == "admin"
        self.db = initialize_database()
        self.setWindowTitle(
            translate("WeRhere | VIT applicant CRM", self.language)
        )
        self.resize(1440, 920)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(_localized_stylesheet())
        self._build_ui()
        _apply_language_to_widgets(self, self.language)

    def _build_ui(self):
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        logo = BrandLogoWidget(184, 54)
        sidebar_layout.addWidget(logo)
        self.language_selector = QComboBox()
        self.language_selector.setObjectName("languageSelector")
        for name, code in LANGUAGES:
            self.language_selector.addItem(f"{code.upper()}  ·  {name}", code)
        self.language_selector.setCurrentIndex(
            max(0, self.language_selector.findData(self.language))
        )
        self.language_selector.currentIndexChanged.connect(self._change_language)
        sidebar_layout.addWidget(self.language_selector)

        self.nav_buttons = {}
        if self.is_admin:
            self.page_builders = [
                ("Applications", self._build_applications_page),
                ("Mentor interviews", self._build_meetings_page),
                ("Mentors", self._build_mentors_page),
                ("Interviews", self._build_residents_page),
                ("Admin", self._build_settings_page),
            ]
        else:
            self.page_builders = [
                ("Applications", self._build_applications_page),
                ("Mentor interviews", self._build_meetings_page),
                ("Mentors", self._build_mentors_page),
                ("Interviews", self._build_residents_page),
            ]

        for index, (name, _) in enumerate(self.page_builders):
            btn = QPushButton(name)
            btn.setObjectName("navButton")
            btn.clicked.connect(lambda checked, current=index: self._switch_page(current))
            self.nav_buttons[name] = btn
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()
        role_label = QLabel("ADMINISTRATOR" if self.is_admin else "USER")
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

    def _change_language(self, _index: int) -> None:
        self.language = self.language_selector.currentData()
        global _CURRENT_LANGUAGE
        _CURRENT_LANGUAGE = self.language
        self.settings.setValue("language", self.language)
        self._refresh_applications()
        self._refresh_meetings()
        self._refresh_mentors()
        self._refresh_interviews()
        self.setWindowTitle(
            translate("WeRhere | VIT applicant CRM", self.language)
        )
        _apply_language_to_widgets(self, self.language)

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
        item.setData(_SOURCE_TEXT_ROLE, text)
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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("dashboardHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(18)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(5)
        header = QLabel(f"Welcome back, {self.display_name}")
        header.setObjectName("dashboardHeroTitle")
        subtitle = QLabel(
            "Your community at a glance. Here are the updates that need your attention."
        )
        subtitle.setObjectName("dashboardHeroSubtitle")
        subtitle.setWordWrap(True)
        hero_text.addWidget(header)
        hero_text.addWidget(subtitle)
        hero_layout.addLayout(hero_text, 1)
        new_application = QPushButton("+  New application")
        new_application.setObjectName("heroButton")
        new_application.clicked.connect(self._add_application)
        new_application.setMinimumHeight(44)
        hero_layout.addWidget(new_application)
        layout.addWidget(hero)

        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
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
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("dashboardHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(5)
        welcome = QLabel(f"Welcome, {self.display_name}")
        welcome.setObjectName("dashboardHeroTitle")
        hero_subtitle = QLabel(
            "Pick up where you left off and see what is coming up."
        )
        hero_subtitle.setObjectName("dashboardHeroSubtitle")
        hero_layout.addWidget(welcome)
        hero_layout.addWidget(hero_subtitle)
        layout.addWidget(hero)

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

        upcoming_panel = QWidget()
        upcoming_panel.setObjectName("panel")
        upcoming_layout = QVBoxLayout(upcoming_panel)
        upcoming_header = QHBoxLayout()
        upcoming_title = QLabel("Upcoming sessions")
        upcoming_title.setObjectName("panelTitle")
        upcoming_header.addWidget(upcoming_title)
        upcoming_header.addStretch()
        view_schedule = QPushButton("View schedule")
        view_schedule.setObjectName("textButton")
        view_schedule.clicked.connect(lambda: self._switch_page(2))
        upcoming_header.addWidget(view_schedule)
        upcoming_layout.addLayout(upcoming_header)
        upcoming_meetings = sorted(
            (
                meeting
                for meeting in meetings
                if self._is_upcoming_meeting(meeting)
            ),
            key=lambda meeting: meeting["meeting_time"],
        )[:3]
        if upcoming_meetings:
            for meeting in upcoming_meetings:
                event = QFrame()
                event.setObjectName("eventRow")
                event_layout = QVBoxLayout(event)
                event_layout.setContentsMargins(12, 9, 12, 9)
                event_layout.setSpacing(3)
                event_title = QLabel(meeting["title"])
                event_title.setObjectName("eventTitle")
                event_time = QLabel(
                    f"{meeting['meeting_time']}  ·  "
                    f"{meeting.get('mentor_name') or 'Community team'}"
                )
                event_time.setObjectName("pageSubtitle")
                event_layout.addWidget(event_title)
                event_layout.addWidget(event_time)
                upcoming_layout.addWidget(event)
        else:
            empty_sessions = QLabel(
                "No sessions are scheduled yet. New shared sessions will appear here."
            )
            empty_sessions.setObjectName("supportNote")
            empty_sessions.setWordWrap(True)
            upcoming_layout.addWidget(empty_sessions)
        content.addWidget(progress_panel, 1)
        content.addWidget(upcoming_panel, 1)
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
        subtitle = QLabel(
            "Search the VIT applicant register and review mentor assignment and application status."
        )
        subtitle.setObjectName("pageSubtitle")
        title_group.addWidget(header)
        title_group.addWidget(subtitle)
        header_row.addLayout(title_group)
        header_row.addStretch()
        layout.addLayout(header_row)

        toolbar = QHBoxLayout()
        self.application_search = QLineEdit()
        self.application_search.setPlaceholderText("Search applicants by name or keyword")
        self.application_search.textChanged.connect(self._refresh_applications)
        toolbar.addWidget(self.application_search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._refresh_applications)
        self.application_search.returnPressed.connect(search_btn.click)
        toolbar.addWidget(search_btn)
        self.application_filter = QComboBox()
        for label, value in (
            ("All applications", "all"),
            ("Mentor meeting identified", "mentor_identified"),
            ("Mentor meeting not identified", "mentor_not_identified"),
            ("Duplicate records (name + email)", "duplicates"),
            ("Application filter (show one per name)", "unique_names"),
            ("Previous VIT applicants (VIT1/VIT2 and current)", "previous_vit"),
            ("Different VIT applicants", "different_vit"),
        ):
            self.application_filter.addItem(label, value)
            self.application_filter.setItemData(
                self.application_filter.count() - 1, label, _SOURCE_TEXT_ROLE
            )
        self.application_filter.currentIndexChanged.connect(
            self._refresh_applications
        )
        toolbar.addWidget(self.application_filter)
        add_btn = QPushButton("+  New applicant")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_applicant)
        edit_btn = QPushButton("Edit selected")
        edit_btn.clicked.connect(self._edit_applicant)
        email_btn = QPushButton("Email candidate")
        email_btn.clicked.connect(self._email_selected_applicant)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(email_btn)
        layout.addLayout(toolbar)

        self.application_count = QLabel("")
        self.application_count.setObjectName("pageSubtitle")
        layout.addWidget(self.application_count)
        layout.addWidget(_applicant_status_legend())
        self.previous_vit_note = QLabel("")
        self.previous_vit_note.setObjectName("supportNote")
        self.previous_vit_note.setWordWrap(True)
        layout.addWidget(self.previous_vit_note)

        self.application_table = QTableWidget(0, 11)
        self.application_table.setHorizontalHeaderLabels(
            [
                "Source Row",
                "#",
                "Full Name",
                "Email",
                "Phone",
                "Desired Training",
                "Province",
                "Current Status (source)",
                "Mentor Meeting",
                "Application Period",
                "Processing Status",
            ]
        )
        self.application_table.setColumnHidden(0, True)
        self.application_table.setAlternatingRowColors(True)
        self.application_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.application_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.application_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.application_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.application_table.verticalHeader().setVisible(False)
        self.application_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.application_table.currentCellChanged.connect(
            self._show_application_details
        )
        layout.addWidget(self.application_table)

        self.application_details = QTextEdit()
        self.application_details.setReadOnly(True)
        self.application_details.setMaximumHeight(180)
        self.application_details.setPlaceholderText(
            "Select an application to review all source fields."
        )
        layout.addWidget(self.application_details)
        self._refresh_applications()
        return page

    def _build_meetings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)
        header = QLabel("Mentor interviews")
        header.setObjectName("pageTitle")
        layout.addWidget(header)
        subtitle = QLabel(
            "Review all recorded candidate conversations, scores, recommendations, and notes."
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.meeting_search = QLineEdit()
        self.meeting_search.setPlaceholderText("Search candidates, mentors, or notes")
        self.meeting_search.textChanged.connect(self._refresh_meetings)
        toolbar.addWidget(self.meeting_search)
        self.mentor_recommendation_filter = QComboBox()
        self.mentor_recommendation_filter.addItem("All conversations", "")
        self.mentor_recommendation_filter.setItemData(
            0, "All conversations", _SOURCE_TEXT_ROLE
        )
        for record in self.db.list_source_records(
            "Mentor", "Mentor Recommendation Options"
        ):
            values = dict(zip(record["headers"], record["values"]))
            option = next(iter(values.values()), None)
            if option:
                self.mentor_recommendation_filter.addItem(str(option), str(option))
                self.mentor_recommendation_filter.setItemData(
                    self.mentor_recommendation_filter.count() - 1,
                    str(option),
                    _SOURCE_TEXT_ROLE,
                )
        self.mentor_recommendation_filter.currentIndexChanged.connect(
            self._refresh_meetings
        )
        toolbar.addWidget(self.mentor_recommendation_filter)
        schedule_btn = QPushButton("+  Schedule interview")
        schedule_btn.setObjectName("primaryButton")
        schedule_btn.clicked.connect(self._schedule_mentor_interview)
        edit_schedule_btn = QPushButton("Edit selected appointment")
        edit_schedule_btn.clicked.connect(self._edit_mentor_interview)
        record_outcome_btn = QPushButton("Record interview outcome")
        record_outcome_btn.clicked.connect(self._record_mentor_outcome)
        toolbar.addWidget(schedule_btn)
        toolbar.addWidget(edit_schedule_btn)
        toolbar.addWidget(record_outcome_btn)
        layout.addLayout(toolbar)

        self.mentor_count = QLabel("")
        self.mentor_count.setObjectName("pageSubtitle")
        layout.addWidget(self.mentor_count)
        layout.addWidget(_applicant_status_legend())
        self.meeting_table = QTableWidget(0, 12)
        self.meeting_table.setHorizontalHeaderLabels(
            [
                "Meeting ID",
                "#",
                "Candidate Name",
                "Date and time",
                "VIT Group",
                "Mentor Name",
                "Score",
                "Recommendation",
                "Alternative Recommendation",
                "Secondary Score",
                "Notes",
                "Appointment Status",
            ]
        )
        self.meeting_table.setColumnHidden(0, True)
        self.meeting_table.setAlternatingRowColors(True)
        self.meeting_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.meeting_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.meeting_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.meeting_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.meeting_table.verticalHeader().setVisible(False)
        self.meeting_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.meeting_table)
        self._refresh_meetings()
        return page

    def _build_mentors_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)

        header = QLabel("Mentors")
        header.setObjectName("pageTitle")
        layout.addWidget(header)
        subtitle = QLabel("Mentors who appear in recorded or scheduled interviews.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        self.mentor_search = QLineEdit()
        self.mentor_search.setPlaceholderText("Search mentors")
        self.mentor_search.textChanged.connect(self._refresh_mentors)
        layout.addWidget(self.mentor_search)

        self.mentor_directory_count = QLabel("")
        self.mentor_directory_count.setObjectName("pageSubtitle")
        layout.addWidget(self.mentor_directory_count)

        self.mentor_directory_table = QTableWidget(0, 3)
        self.mentor_directory_table.setHorizontalHeaderLabels(
            ["#", "Mentor", "Interviews"]
        )
        self.mentor_directory_table.setAlternatingRowColors(True)
        self.mentor_directory_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.mentor_directory_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.mentor_directory_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.mentor_directory_table.verticalHeader().setVisible(False)
        self.mentor_directory_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.mentor_directory_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.mentor_directory_table)
        self._refresh_mentors()
        return page

    def _build_residents_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)
        header = QLabel("Interviews")
        header.setObjectName("pageTitle")
        layout.addWidget(header)
        subtitle = QLabel("Track projects sent to candidates and received back.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.interview_search = QLineEdit()
        self.interview_search.setPlaceholderText("Search candidates")
        self.interview_search.textChanged.connect(self._refresh_interviews)
        toolbar.addWidget(self.interview_search)
        self.interview_filter_value = "all"
        self.interview_filter_buttons = {}
        for label, value in (
            ("All candidates", "all"),
            ("Projects sent", "sent"),
            ("Projects received", "received"),
        ):
            button = QPushButton(label)
            button.setObjectName("interviewFilterButton")
            button.setCheckable(True)
            button.setChecked(value == self.interview_filter_value)
            button.clicked.connect(
                lambda _checked, selected=value: self._set_interview_filter(selected)
            )
            self.interview_filter_buttons[value] = button
            toolbar.addWidget(button)
        layout.addLayout(toolbar)

        self.interview_count = QLabel("")
        self.interview_count.setObjectName("pageSubtitle")
        layout.addWidget(self.interview_count)
        self.interview_table = QTableWidget(0, 4)
        self.interview_table.setHorizontalHeaderLabels(
            ["#", "Full Name", "Project sent", "Project received"]
        )
        self.interview_table.setAlternatingRowColors(True)
        self.interview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.interview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.interview_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.interview_table.verticalHeader().setVisible(False)
        self.interview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.interview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.interview_table)
        self._refresh_interviews()
        return page

    def _set_interview_filter(self, selected_filter: str) -> None:
        self.interview_filter_value = selected_filter
        for value, button in self.interview_filter_buttons.items():
            button.setChecked(value == selected_filter)
        self._refresh_interviews()

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
                    cell.setData(_SOURCE_TEXT_ROLE, value)
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    cell.setForeground(QColor("#2f6e9f" if incoming else "#687588"))
                if column == 2 and incoming and not message["is_read"]:
                    font = cell.font()
                    font.setWeight(QFont.Weight.Bold)
                    cell.setFont(font)
                self.message_table.setItem(row_index, column, cell)
        _apply_language_to_widgets(self, self.language)

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
        preview_source = f"From {other_user}" if incoming else f"To {other_user}"
        preview_text = translate(preview_source, self.language)
        self.message_preview_from.setProperty(
            "languageSourceText", preview_source
        )
        self.message_preview_from.setProperty(
            "languageSourceTextApplied", preview_text
        )
        self.message_preview_from.setText(preview_text)
        self.message_preview_body.setText(message["body"])
        if incoming and not message["is_read"]:
            self.db.mark_message_read(message["id"], self.username)
            message["is_read"] = 1
            direction_item = self.message_table.item(row, 1)
            direction_item.setData(_SOURCE_TEXT_ROLE, "Received")
            direction_item.setText(translate("Received", self.language))
            self.message_table.item(row, 2).setFont(QFont())
        _apply_language_to_widgets(self, self.language)

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
            QMessageBox.information(
                self,
                translate("Message sent", self.language),
                translate("Your message has been sent.", self.language),
            )

    def _build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(18)
        header = QLabel("Admin" if self.is_admin else "Settings")
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
        role_name = "Administrator" if self.is_admin else "User"
        role_badge = QLabel(role_name)
        role_badge.setObjectName("roleBadge")
        role_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        role_badge.setMaximumWidth(150)
        access_layout.addWidget(role_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        access_description = QLabel(
            "Review the application, mentor interview, and project interview workbooks."
            if self.is_admin
            else "Review candidate applications, mentor interviews, and project interviews."
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
            "Connected Google Sheets workbooks sync at startup. New and edited applicants "
            "are saved to the Applications sheet. Workspace messages and appointments remain local."
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
                f"{application['location']}  ·  "
                f"{translate(application['priority'], self.language)} "
                f"{translate('Priority', self.language)}"
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
            (
                meeting
                for meeting in self.db.list_meetings()
                if self._is_upcoming_meeting(meeting)
            ),
            key=lambda meeting: meeting["meeting_time"],
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
        _apply_language_to_widgets(self, self.language)

    @staticmethod
    def _source_record_values(record):
        return dict(zip(record["headers"], record["values"]))

    @staticmethod
    def _source_value(record, field: str) -> str:
        value = record.get(field)
        return "" if value is None else str(value).strip()

    @classmethod
    def _application_identity(cls, fields):
        email = cls._source_value(fields, "Email").casefold()
        if email:
            return ("email", email)
        name = re.sub(r"\s+", " ", cls._source_value(fields, "Full Name")).casefold()
        return ("name", name) if name else None

    @classmethod
    def _application_vit_period(cls, fields):
        value = cls._source_value(fields, "Application Period")
        match = re.fullmatch(r"VIT\s*[- ]?\s*(\d+)", value, flags=re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _set_vit_filter_available(self, filter_value, available, tooltip):
        for index in range(self.application_filter.count()):
            if self.application_filter.itemData(index) != filter_value:
                continue
            item = self.application_filter.model().item(index)
            if item is not None:
                item.setEnabled(available)
                item.setToolTip("" if available else tooltip)
            return

    def _refresh_applications(self, _value=None):
        raw_records = self.db.list_source_records("Applications", "Applications")
        all_records = [
            {
                **record,
                "fields": self._source_record_values(record),
                "vit_period": self._application_vit_period(
                    self._source_record_values(record)
                ),
            }
            for record in raw_records
        ]
        period_identities = {}
        for record in all_records:
            period = record["vit_period"]
            identity = self._application_identity(record["fields"])
            if period is not None and identity is not None:
                period_identities.setdefault(period, set()).add(identity)

        latest_period = max(period_identities, default=None)
        prior_periods = {
            period for period in period_identities
            if period in {1, 2} and (latest_period is None or period < latest_period)
        }
        previous_filter_available = bool(
            latest_period is not None
            and latest_period not in {1, 2}
            and prior_periods
        )
        different_filter_available = 1 in period_identities and 2 in period_identities
        self._set_vit_filter_available(
            "previous_vit",
            previous_filter_available,
            "Add VIT1 or VIT2 rows with Application Period values to enable this filter.",
        )
        self._set_vit_filter_available(
            "different_vit",
            different_filter_available,
            "Add both VIT1 and VIT2 rows with Application Period values to enable this filter.",
        )
        if previous_filter_available and different_filter_available:
            self.previous_vit_note.hide()
        elif previous_filter_available:
            self.previous_vit_note.setText(
                "Different Record needs both VIT1 and VIT2 rows in the Applications sheet."
            )
            self.previous_vit_note.show()
        else:
            self.previous_vit_note.setText(
                "Previous VIT filters need VIT1 or VIT2 rows in the Applications sheet."
            )
            self.previous_vit_note.show()

        latest_identities = (
            period_identities.get(latest_period, set()) if latest_period is not None else set()
        )
        earlier_identities = set().union(
            *(period_identities.get(period, set()) for period in prior_periods)
        ) if prior_periods else set()
        previous_vit_matches = latest_identities & earlier_identities
        different_vit_matches = (
            period_identities.get(1, set()) ^ period_identities.get(2, set())
        )
        records = list(all_records)
        query = self.application_search.text().strip().casefold()
        if query:
            records = [
                record
                for record in records
                if any(
                    query in str(value or "").casefold()
                    for value in record["fields"].values()
                )
            ]

        duplicate_keys = Counter(
            (
                self._source_value(record["fields"], "Full Name").casefold(),
                self._source_value(record["fields"], "Email").casefold(),
            )
            for record in all_records
            if self._source_value(record["fields"], "Full Name")
            and self._source_value(record["fields"], "Email")
        )
        selected_filter = self.application_filter.currentData()
        if selected_filter == "mentor_identified":
            records = [
                record
                for record in records
                if self._source_value(
                    record["fields"], "Mentor Meeting"
                ).casefold() == "ok"
            ]
        elif selected_filter == "mentor_not_identified":
            records = [
                record
                for record in records
                if self._source_value(
                    record["fields"], "Mentor Meeting"
                ).casefold()
                == "not assigned"
            ]
        elif selected_filter == "duplicates":
            records = [
                record
                for record in records
                if duplicate_keys[
                    (
                        self._source_value(record["fields"], "Full Name").casefold(),
                        self._source_value(record["fields"], "Email").casefold(),
                    )
                ]
                > 1
                and self._source_value(record["fields"], "Full Name")
                and self._source_value(record["fields"], "Email")
            ]
        elif selected_filter == "unique_names":
            unique_records = []
            seen_names = set()
            for record in records:
                name = self._source_value(record["fields"], "Full Name").casefold()
                if not name or name not in seen_names:
                    unique_records.append(record)
                    if name:
                        seen_names.add(name)
            records = unique_records
        elif selected_filter == "previous_vit":
            records = [
                record for record in records
                if record["vit_period"] == latest_period
                and self._application_identity(record["fields"]) in previous_vit_matches
            ]
        elif selected_filter == "different_vit":
            records = [
                record for record in records
                if record["vit_period"] in {1, 2}
                and self._application_identity(record["fields"]) in different_vit_matches
            ]

        self.application_visible_records = records
        self.application_status_colors = {
            self._source_value(record["fields"], "Full Name").casefold():
            self._status_color(record["fields"])
            for record in all_records
        }
        self.application_count.setText(
            translate("Showing {shown} of {total} candidates", self.language).format(
                shown=len(records), total=len(all_records)
            )
        )
        columns = (
            "Full Name",
            "Email",
            "Phone",
            "Desired Training",
            "Province",
            "Current Status",
            "Mentor Meeting",
            "Application Period",
            "Processing Status",
        )
        self.application_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            self.application_table.setItem(
                row_index, 0, QTableWidgetItem(str(record["source_row"]))
            )
            row_number = QTableWidgetItem(str(row_index + 1))
            row_number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.application_table.setItem(row_index, 1, row_number)
            for column_index, column in enumerate(columns):
                value = self._source_value(record["fields"], column)
                if column == "Full Name":
                    value = value.title()
                item = QTableWidgetItem(value)
                if column == "Current Status":
                    item.setToolTip("Current Status (source)")
                if column == "Full Name":
                    item.setForeground(
                        QColor(self._status_color(record["fields"]))
                    )
                    item.setFont(QFont(item.font().family(), item.font().pointSize(), QFont.Weight.Bold))
                self.application_table.setItem(row_index, column_index + 2, item)
        if records:
            self._show_application_details(0, 0, -1, -1)
        else:
            self.application_details.clear()
        _apply_language_to_widgets(self, self.language)

    def _show_application_details(
        self, row: int, _column: int, _previous_row: int, _previous_column: int
    ):
        if row < 0 or row >= len(getattr(self, "application_visible_records", [])):
            return
        record = self.application_visible_records[row]
        details = []
        for header, value in record["fields"].items():
            if header == "Full Name" and value:
                value = str(value).title()
            details.append(f"{header}: {value if value is not None else ''}")
        self.application_details.setPlainText("\n".join(details))

    @staticmethod
    def _status_color(record):
        processing_status = WeRhereMainWindow._source_value(
            record, "Processing Status"
        ).casefold()
        current_status = WeRhereMainWindow._source_value(
            record, "Current Status"
        ).casefold()
        if processing_status == "done":
            return "#287a54"
        if "moved into housing" in current_status:
            return "#2f6e9f"
        if "waiting" in current_status:
            return "#976b15"
        return "#687588"

    def _candidate_names(self):
        records = [
            self._source_record_values(record)
            for record in self.db.list_source_records(
                "Applications", "Applications"
            )
        ]
        return sorted(
            {
                self._source_value(record, "Full Name").title()
                for record in records
                if self._source_value(record, "Full Name")
            },
            key=str.casefold,
        )

    def _mentor_names(self):
        return [record["name"] for record in self._mentor_summaries()]

    def _mentor_summaries(self):
        summaries = {}

        def add_mentor(name: str, count: int = 1) -> None:
            name = name.strip()
            if not name:
                return
            key = name.casefold()
            summary = summaries.setdefault(
                key, {"name": name, "interviews": 0}
            )
            summary["interviews"] += count

        for record in self.db.list_source_records("Mentor", "Mentor"):
            fields = self._source_record_values(record)
            add_mentor(self._source_value(fields, "Mentor Name"))
        for meeting in self.db.list_meetings():
            if meeting["title"] == "Mentor interview":
                add_mentor(meeting["mentor_name"])
        return sorted(
            summaries.values(), key=lambda record: record["name"].casefold()
        )

    def _refresh_mentors(self, _value=None):
        mentors = self._mentor_summaries()
        total = len(mentors)
        query = self.mentor_search.text().strip().casefold()
        if query:
            mentors = [
                mentor for mentor in mentors
                if query in mentor["name"].casefold()
            ]

        self.mentor_directory_count.setText(
            translate(
                "Showing {shown} of {total} mentors", self.language
            ).format(shown=len(mentors), total=total)
        )
        self.mentor_directory_table.setRowCount(len(mentors))
        for row_index, mentor in enumerate(mentors):
            number = QTableWidgetItem(str(row_index + 1))
            number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.mentor_directory_table.setItem(row_index, 0, number)
            self.mentor_directory_table.setItem(
                row_index, 1, QTableWidgetItem(mentor["name"])
            )
            self.mentor_directory_table.setItem(
                row_index, 2, QTableWidgetItem(str(mentor["interviews"]))
            )
        _apply_language_to_widgets(self, self.language)

    def _add_applicant(self):
        records = self.db.list_source_records("Applications", "Applications")
        if not records:
            self._show_error("Application workbook source fields are unavailable.")
            return
        headers = records[0]["headers"]
        dialog = ApplicationSourceDialog(headers, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.db.save_application_source_record_to_drive(dialog.data())
        except (DriveImportError, ValueError, OSError) as error:
            message = translate("Could not save the candidate: {error}", self.language)
            self._show_error(message.format(error=error))
            return
        self._refresh_applications()
        self._refresh_meetings()
        self._refresh_interviews()

    def _edit_applicant(self):
        selected = self.application_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select an application first.")
            return
        row_index = selected[0].row()
        record = self.application_visible_records[row_index]
        dialog = ApplicationSourceDialog(
            record["headers"], record["fields"], self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.db.save_application_source_record_to_drive(
                dialog.data(), source_row=record["source_row"]
            )
        except (DriveImportError, ValueError, OSError) as error:
            message = translate(
                "Could not update the candidate: {error}", self.language
            )
            self._show_error(message.format(error=error))
            return
        self._refresh_applications()
        self._refresh_meetings()
        self._refresh_interviews()

    def _email_selected_applicant(self):
        selected = self.application_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select a candidate first.")
            return
        record = self.application_visible_records[selected[0].row()]["fields"]
        email = self._source_value(record, "Email")
        if not email:
            self._show_error("The selected candidate has no email address.")
            return
        mailto_url = (
            f"mailto:{quote(email, safe='@.+-_')}"
            f"?subject={quote('VIT programme application', safe='')}"
        )
        try:
            if os.name == "nt":
                os.startfile(mailto_url)
            elif not QDesktopServices.openUrl(QUrl(mailto_url)):
                self._show_error("Could not open the default email application.")
        except OSError:
            self._show_error("Could not open the default email application.")

    def _candidate_name_color(self, name: str) -> QColor:
        return QColor(self.application_status_colors.get(name.strip().casefold(), "#687588"))

    def _refresh_meetings(self, _value=None):
        raw_records = self.db.list_source_records("Mentor", "Mentor")
        records = [
            {
                "kind": "source",
                "source_row": record["source_row"],
                "fields": self._source_record_values(record),
            }
            for record in raw_records
        ]
        appointments = [
            {
                "kind": "appointment",
                "meeting": meeting,
                "fields": {
                    "Candidate Name": meeting["resident_name"],
                    "Date": meeting["meeting_time"],
                    "VIT Group": "",
                    "Mentor Name": meeting["mentor_name"],
                    "Score": "",
                    "Recommendation": "",
                    "Alternative Recommendation": "",
                    "Secondary Score": "",
                    "Notes": "",
                },
            }
            for meeting in self.db.list_meetings()
            if meeting["title"] == "Mentor interview"
            and not meeting.get("mentor_source_row")
        ]
        records.extend(appointments)
        query = self.meeting_search.text().strip().casefold()
        recommendation = self.mentor_recommendation_filter.currentData()
        if query:
            records = [
                record
                for record in records
                if any(
                    query in str(value or "").casefold()
                    for value in record["fields"].values()
                )
            ]
        if recommendation:
            records = [
                record
                for record in records
                if self._source_value(
                    record["fields"], "Recommendation"
                ) == recommendation
            ]

        self.mentor_visible_records = records
        self.mentor_count.setText(
            translate("Showing {shown} of {total} mentor interviews", self.language).format(
                shown=len(records), total=len(raw_records) + len(appointments)
            )
        )
        columns = (
            "Candidate Name",
            "Date",
            "VIT Group",
            "Mentor Name",
            "Score",
            "Recommendation",
            "Alternative Recommendation",
            "Secondary Score",
            "Notes",
        )
        self.meeting_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            meeting = record.get("meeting")
            self.meeting_table.setItem(
                row_index,
                0,
                QTableWidgetItem(str(meeting["id"]) if meeting else ""),
            )
            number_item = QTableWidgetItem(str(row_index + 1))
            number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.meeting_table.setItem(row_index, 1, number_item)
            for column_index, column in enumerate(columns):
                value = self._source_value(record["fields"], column)
                if column == "Candidate Name" and value:
                    value = value.title()
                item = QTableWidgetItem(value)
                if column == "Candidate Name":
                    item.setForeground(self._candidate_name_color(value))
                    item.setFont(
                        QFont(
                            item.font().family(),
                            item.font().pointSize(),
                            QFont.Weight.Bold,
                        )
                    )
                self.meeting_table.setItem(row_index, column_index + 2, item)
            status = meeting["status"] if meeting else "Recorded"
            self.meeting_table.setItem(
                row_index, 11, self._colored_item(status)
            )
        _apply_language_to_widgets(self, self.language)

    def _schedule_mentor_interview(self):
        dialog = MeetingDialog(
            candidates=self._candidate_names(),
            mentors=self._mentor_names(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.data()
        if not payload["resident_name"] or not payload["mentor_name"]:
            self._show_error("Candidate and interviewer are required.")
            return
        if not self._valid_interview_datetime(payload["meeting_time"]):
            self._show_error("Enter the interview date and time as YYYY-MM-DD HH:MM.")
            return
        self.db.add_meeting(payload)
        self._refresh_meetings()
        self._refresh_mentors()

    def _edit_mentor_interview(self):
        selected = self.meeting_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select an appointment first.")
            return
        row_index = selected[0].row()
        entry = self.mentor_visible_records[row_index]
        meeting = entry.get("meeting")
        if meeting is None:
            self._show_error("Only scheduled appointments can be edited here.")
            return
        dialog = MeetingDialog(
            record=meeting,
            candidates=self._candidate_names(),
            mentors=self._mentor_names(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.data()
        if not payload["resident_name"] or not payload["mentor_name"]:
            self._show_error("Candidate and interviewer are required.")
            return
        if not self._valid_interview_datetime(payload["meeting_time"]):
            self._show_error("Enter the interview date and time as YYYY-MM-DD HH:MM.")
            return
        self.db.update_meeting(meeting["id"], payload)
        self._refresh_meetings()
        self._refresh_mentors()

    def _record_mentor_outcome(self):
        selected = self.meeting_table.selectionModel().selectedRows()
        if not selected:
            self._show_error("Please select a scheduled appointment first.")
            return
        entry = self.mentor_visible_records[selected[0].row()]
        meeting = entry.get("meeting")
        if meeting is None:
            self._show_error("Select a scheduled appointment to record its outcome.")
            return

        vit_group = ""
        for record in self.db.list_source_records("Applications", "Applications"):
            fields = self._source_record_values(record)
            if self._source_value(fields, "Full Name").casefold() == meeting["resident_name"].casefold():
                vit_group = self._source_value(fields, "Application Period")
                if vit_group:
                    break
        recommendation_options = [
            next(iter(record["values"]), "")
            for record in self.db.list_source_records(
                "Mentor", "Mentor Recommendation Options"
            )
        ]
        dialog = MentorOutcomeDialog(
            meeting, recommendation_options, vit_group=vit_group, parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.db.save_mentor_interview_to_drive(meeting["id"], dialog.data())
        except (DriveImportError, ValueError) as error:
            self._show_error(str(error))
            return
        self._refresh_meetings()
        self._refresh_mentors()

    @staticmethod
    def _valid_interview_datetime(value: str) -> bool:
        try:
            datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            return False
        return True

    def _refresh_interviews(self, _value=None):
        raw_records = self.db.list_source_records("Interviews", "Interviews")
        records = [self._source_record_values(record) for record in raw_records]
        query = self.interview_search.text().strip().casefold()
        selected_filter = self.interview_filter_value
        if query:
            records = [
                record
                for record in records
                if query in self._source_value(record, "Full Name").casefold()
            ]
        if selected_filter == "sent":
            records = [
                record
                for record in records
                if self._source_value(record, "Project Sent Date")
            ]
        elif selected_filter == "received":
            records = [
                record
                for record in records
                if self._source_value(record, "Project Received Date")
            ]

        self.interview_count.setText(
            translate("Showing {shown} of {total} candidates", self.language).format(
                shown=len(records), total=len(raw_records)
            )
        )
        columns = ("Full Name", "Project Sent Date", "Project Received Date")
        self.interview_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            number_item = QTableWidgetItem(str(row_index + 1))
            number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.interview_table.setItem(row_index, 0, number_item)
            for column_index, column in enumerate(columns):
                value = self._source_value(record, column)
                if column == "Full Name" and value:
                    value = value.title()
                item = QTableWidgetItem(value)
                if column == "Full Name":
                    item.setForeground(self._candidate_name_color(value))
                    item.setFont(
                        QFont(
                            item.font().family(),
                            item.font().pointSize(),
                            QFont.Weight.Bold,
                        )
                    )
                self.interview_table.setItem(
                    row_index,
                    column_index + 1,
                    item,
                )
        _apply_language_to_widgets(self, self.language)

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
                self._show_error(
                    "Enter a date as YYYY-MM-DD or a date and time as YYYY-MM-DD HH:MM."
                )
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
                self._show_error(
                    "Enter a date as YYYY-MM-DD or a date and time as YYYY-MM-DD HH:MM."
                )
                return
            self.db.update_meeting(meeting_id, payload)
            self._refresh_meetings()
            self._refresh_dashboard()

    @staticmethod
    def _valid_meeting_time(value: str) -> bool:
        return WeRhereMainWindow._meeting_datetime(value) is not None

    @staticmethod
    def _meeting_datetime(value: str) -> datetime | None:
        for format_string in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, format_string)
            except ValueError:
                continue
        return None

    @classmethod
    def _is_upcoming_meeting(cls, meeting: dict) -> bool:
        if meeting["status"].casefold() in {"completed", "cancelled"}:
            return False
        meeting_datetime = cls._meeting_datetime(meeting["meeting_time"])
        return meeting_datetime is not None and meeting_datetime >= datetime.now()

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
        QMessageBox.warning(self, "WeRhere", translate(text, self.language))


def main():
    import sys

    app = QApplication(sys.argv)
    try:
        login = LoginDialog()
    except DriveImportError as error:
        QMessageBox.critical(
            None,
            "WeRhere",
            f"Could not load the shared CRM data. Check your internet connection "
            f"and Drive access, then restart the app.\n\n{error}",
        )
        return
    if login.exec() != QDialog.DialogCode.Accepted:
        return

    window = WeRhereMainWindow(login.authenticated_user, login.language)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
