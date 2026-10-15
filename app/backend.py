from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional

from .drive_import import DriveImportError, GoogleSheetsStore, read_workbooks

DB_PATH = Path(__file__).resolve().parent.parent / "wehere.db"
_PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
_PASSWORD_HASH_ITERATIONS = 310_000
_NOT_PROVIDED = "Not provided"


class DatabaseManager:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        import_drive_data: bool = True,
    ):
        self.db_path = db_path or DB_PATH
        self.drive = GoogleSheetsStore()
        self._ensure_parent_dir()
        self._init_db()
        if import_drive_data:
            self._sync_drive_data()

    def _ensure_parent_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    display_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            user_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(users)")
            }
            if "role" not in user_columns:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
                )
            if "display_name" not in user_columns:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_name TEXT NOT NULL,
                    type_name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    last_update TEXT NOT NULL,
                    notes TEXT,
                    current_status TEXT NOT NULL DEFAULT '',
                    source_row INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            application_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(applications)")
            }
            if "current_status" not in application_columns:
                conn.execute(
                    "ALTER TABLE applications ADD COLUMN current_status TEXT NOT NULL DEFAULT ''"
                )
            if "source_row" not in application_columns:
                conn.execute("ALTER TABLE applications ADD COLUMN source_row INTEGER")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_source_row
                ON applications(source_row) WHERE source_row IS NOT NULL
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    meeting_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mentor_name TEXT NOT NULL DEFAULT 'Community team',
                    resident_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            meeting_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(meetings)")
            }
            if "mentor_name" not in meeting_columns:
                conn.execute(
                    "ALTER TABLE meetings ADD COLUMN mentor_name TEXT NOT NULL DEFAULT 'Community team'"
                )
            if "resident_name" not in meeting_columns:
                conn.execute(
                    "ALTER TABLE meetings ADD COLUMN resident_name TEXT NOT NULL DEFAULT ''"
                )
            if "mentor_source_row" not in meeting_columns:
                conn.execute(
                    "ALTER TABLE meetings ADD COLUMN mentor_source_row INTEGER"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS residents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    description TEXT,
                    initials TEXT NOT NULL,
                    color TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_username TEXT NOT NULL,
                    recipient_username TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                UPDATE meetings SET mentor_name = 'Community team'
                WHERE mentor_name = ''
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workbook_name TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE (workbook_name, sheet_name, source_row)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def _sync_drive_data(self) -> None:
        with self._connect() as conn:
            imported = conn.execute(
                "SELECT 1 FROM app_meta WHERE key = 'drive_import_completed'"
            ).fetchone()
        workbook_sources = self.drive.download_workbooks()
        if imported is None:
            self.import_workbooks(workbook_sources)
        else:
            self._refresh_source_records(workbook_sources)

    def _refresh_source_records(self, workbook_sources: Mapping[str, bytes]) -> None:
        parsed = read_workbooks(workbook_sources)
        imported_usernames: set[str] = set()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._mark_existing_imported_applications(conn)
            conn.execute("DELETE FROM source_records")
            conn.execute("DELETE FROM applications WHERE source_row IS NOT NULL")
            conn.execute("DELETE FROM meetings WHERE title = 'Mentor review'")
            for workbook_name, sheets in parsed.items():
                for sheet in sheets:
                    headers = sheet["headers"]
                    password_indices = {
                        index
                        for index, header in enumerate(headers)
                        if header.casefold() == "password"
                    }
                    for row_number, row in sheet["rows"]:
                        values = list(row)
                        source_values = list(values)
                        for password_index in password_indices:
                            if password_index < len(source_values):
                                source_values[password_index] = "[REDACTED]"
                        payload = json.dumps(
                            {
                                "headers": headers,
                                "values": [
                                    self._json_value(value) for value in source_values
                                ],
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        conn.execute(
                            """
                            INSERT INTO source_records
                                (workbook_name, sheet_name, source_row, payload_json)
                            VALUES (?, ?, ?, ?)
                            """,
                            (workbook_name, sheet["sheet_name"], row_number, payload),
                        )
                        if workbook_name == "Applications":
                            self._import_application_row(
                                conn, headers, values, source_row=row_number
                            )
                        elif workbook_name == "Mentor" and sheet["sheet_name"] == "Mentor":
                            self._import_mentor_row(conn, headers, values)
                        if workbook_name == "Users" and sheet["sheet_name"] == "Users":
                            username = self._source_text(headers, values, "Username")
                            password = self._source_text(headers, values, "Password")
                            source_role = self._source_text(
                                headers, values, "Role"
                            ).casefold()
                            roles = {"admin": "admin", "user": "user"}
                            if (
                                not username
                                or not password.strip()
                                or source_role not in roles
                            ):
                                raise DriveImportError(
                                    "Users.xlsx contains a row with a missing username, "
                                    "password, or supported role."
                                )
                            if username in imported_usernames:
                                raise DriveImportError(
                                    "Users.xlsx contains duplicate usernames."
                                )
                            imported_usernames.add(username)
                            conn.execute(
                                """
                                INSERT INTO users (username, password, role, display_name)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(username) DO UPDATE SET
                                    password = excluded.password,
                                    role = excluded.role,
                                    display_name = excluded.display_name
                                """,
                                (
                                    username,
                                    self._hash_password(password),
                                    roles[source_role],
                                    username,
                                ),
                            )
            if not imported_usernames:
                raise DriveImportError("Users.xlsx contains no user accounts.")
            placeholders = ", ".join("?" for _ in imported_usernames)
            conn.execute(
                f"DELETE FROM users WHERE username NOT IN ({placeholders})",
                tuple(imported_usernames),
            )

    def _mark_existing_imported_applications(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT source_row, payload_json FROM source_records
            WHERE workbook_name = 'Applications' AND sheet_name = 'Applications'
            ORDER BY source_row
            """
        ).fetchall()
        for source in rows:
            payload = json.loads(source["payload_json"])
            fields = dict(zip(payload["headers"], payload["values"]))
            imported = (
                str(fields.get("Full Name") or "").strip(),
                str(fields.get("Desired Training") or _NOT_PROVIDED).strip(),
                str(fields.get("Province") or _NOT_PROVIDED).strip(),
            )
            conn.execute(
                """
                UPDATE applications SET source_row = ?
                WHERE id = (
                    SELECT id FROM applications
                    WHERE source_row IS NULL AND applicant_name = ? AND type_name = ?
                      AND location = ?
                    ORDER BY id LIMIT 1
                )
                """,
                (source["source_row"], *imported),
            )

    def save_application_source_record_to_drive(
        self, values: Mapping[str, Any], source_row: Optional[int] = None
    ) -> int:
        with self._connect() as conn:
            template = conn.execute(
                """
                SELECT payload_json FROM source_records
                WHERE workbook_name = 'Applications' AND sheet_name = 'Applications'
                ORDER BY source_row LIMIT 1
                """
            ).fetchone()
        if template is None:
            raise ValueError("Application workbook source fields are unavailable.")
        headers = json.loads(template["payload_json"])["headers"]
        if source_row is None:
            source_row = self.drive.append_application(headers, values)
        else:
            self.drive.update_application(headers, values, source_row)
        self.save_application_source_record(values, source_row=source_row)
        with self._connect() as conn:
            self._import_application_row(
                conn,
                headers,
                [values.get(header) for header in headers],
                source_row=source_row,
            )
        return source_row

    def save_mentor_interview_to_drive(
        self, meeting_id: int, values: Mapping[str, Any]
    ) -> int:
        headers = [
            "Date",
            "VIT Group",
            "Candidate Name",
            "Mentor Name",
            "Score",
            "Recommendation",
            "Alternative Recommendation",
            "Secondary Score",
            "Notes",
        ]
        source_row = self.drive.append_mentor_record(headers, values)
        payload = json.dumps(
            {"headers": headers, "values": [self._json_value(values.get(h, "")) for h in headers]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_records
                    (workbook_name, sheet_name, source_row, payload_json)
                VALUES ('Mentor', 'Mentor', ?, ?)
                ON CONFLICT(workbook_name, sheet_name, source_row)
                DO UPDATE SET payload_json = excluded.payload_json
                """,
                (source_row, payload),
            )
            conn.execute(
                """
                UPDATE meetings
                SET status = 'Completed', mentor_source_row = ?
                WHERE id = ?
                """,
                (source_row, meeting_id),
            )
        return source_row

    def import_workbooks(self, workbook_sources: Mapping[str, bytes]) -> bool:
        parsed = read_workbooks(workbook_sources)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute(
                "SELECT 1 FROM app_meta WHERE key = 'drive_import_completed'"
            ).fetchone():
                return False
            self._insert_imported_workbooks(conn, parsed)
            conn.execute(
                """
                INSERT INTO app_meta (key, value)
                VALUES ('drive_import_completed', ?)
                """,
                (datetime.now().astimezone().isoformat(timespec="seconds"),),
            )
        return True

    def _insert_imported_workbooks(
        self,
        conn: sqlite3.Connection,
        workbooks: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        source_usernames: set[str] = set()
        for workbook_name, sheets in workbooks.items():
            for sheet in sheets:
                headers = sheet["headers"]
                password_indices = {
                    index
                    for index, header in enumerate(headers)
                    if header.casefold() == "password"
                }
                for row_number, row in sheet["rows"]:
                    values = list(row)
                    for password_index in password_indices:
                        if password_index < len(values):
                            values[password_index] = "[REDACTED]"
                    payload = json.dumps(
                        {
                            "headers": headers,
                            "values": [self._json_value(value) for value in values],
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    conn.execute(
                        """
                        INSERT INTO source_records
                            (workbook_name, sheet_name, source_row, payload_json)
                        VALUES (?, ?, ?, ?)
                        """,
                        (workbook_name, sheet["sheet_name"], row_number, payload),
                    )

                    if workbook_name == "Applications":
                        self._import_application_row(
                            conn, headers, row, source_row=row_number
                        )
                    elif workbook_name == "Mentor":
                        if sheet["sheet_name"] == "Mentor":
                            self._import_mentor_row(conn, headers, row)
                    elif workbook_name == "Users" and sheet["sheet_name"] == "Users":
                        username = self._source_text(headers, row, "Username")
                        password = self._source_text(headers, row, "Password")
                        source_role = self._source_text(headers, row, "Role").casefold()
                        roles = {"admin": "admin", "user": "user"}
                        if not username or not password.strip() or source_role not in roles:
                            raise DriveImportError(
                                "Users.xlsx contains a row with a missing username, password, or supported role."
                            )
                        if username in source_usernames:
                            raise DriveImportError(
                                "Users.xlsx contains duplicate usernames."
                            )
                        source_usernames.add(username)
                        conn.execute(
                            """
                            INSERT INTO users (username, password, role, display_name)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(username) DO UPDATE SET
                                password = excluded.password,
                                role = excluded.role,
                                display_name = excluded.display_name
                            """,
                            (
                                username,
                                self._hash_password(password),
                                roles[source_role],
                                username,
                            ),
                        )
        self._remove_demo_records(conn, source_usernames)

    def _import_application_row(
        self,
        conn: sqlite3.Connection,
        headers: List[str],
        row: List[Any],
        source_row: Optional[int] = None,
    ) -> None:
        name = self._source_text(headers, row, "Full Name")
        if not name:
            return
        current_status = self._source_text(headers, row, "Current Status")
        values = (
            name,
            self._source_text(headers, row, "Desired Training") or _NOT_PROVIDED,
            self._source_text(headers, row, "Province") or _NOT_PROVIDED,
            self._source_text(headers, row, "Processing Status") or _NOT_PROVIDED,
            "Not specified",
            self._source_text(headers, row, "Timestamp") or _NOT_PROVIDED,
            "",
            current_status,
        )
        if source_row is not None:
            existing = conn.execute(
                "SELECT id FROM applications WHERE source_row = ?", (source_row,)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE applications SET applicant_name = ?, type_name = ?, location = ?,
                        status = ?, priority = ?, last_update = ?, notes = ?, current_status = ?
                    WHERE source_row = ?
                    """,
                    (*values, source_row),
                )
                return
        conn.execute(
            """
            INSERT INTO applications
                (applicant_name, type_name, location, status, priority, last_update,
                 notes, current_status, source_row)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, source_row),
        )
    def _import_mentor_row(
        self,
        conn: sqlite3.Connection,
        headers: List[str],
        row: List[Any],
    ) -> None:
        candidate = self._source_text(headers, row, "Candidate Name")
        mentor = self._source_text(headers, row, "Mentor Name")
        session_date = self._source_date(headers, row, "Date")
        if not candidate or not mentor or not session_date:
            return
        conn.execute(
            """
            INSERT INTO meetings
                (title, meeting_time, status, mentor_name, resident_name)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Mentor review", session_date, "Completed", mentor, candidate),
        )

    @staticmethod
    def _source_text(headers: List[str], row: List[Any], column: str) -> str:
        column_index = next(
            index
            for index, header in enumerate(headers)
            if header.casefold() == column.casefold()
        )
        if column_index >= len(row) or row[column_index] is None:
            return ""
        value = row[column_index]
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value).strip()

    @classmethod
    def _source_date(cls, headers: List[str], row: List[Any], column: str) -> str:
        value = cls._source_text(headers, row, column)
        if not value:
            return ""
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError as error:
            raise DriveImportError(
                "Mentor.xlsx contains an invalid session date."
            ) from error

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        isoformat = getattr(value, "isoformat", None)
        if callable(isoformat):
            return isoformat()
        return str(value)

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            _PASSWORD_HASH_ITERATIONS,
        )
        return "$".join(
            (
                _PASSWORD_HASH_PREFIX,
                str(_PASSWORD_HASH_ITERATIONS),
                salt.hex(),
                digest.hex(),
            )
        )

    @staticmethod
    def _verify_password(password: str, stored_password: str) -> bool:
        if not stored_password.startswith(f"{_PASSWORD_HASH_PREFIX}$"):
            return hmac.compare_digest(stored_password, password)
        try:
            prefix, iteration_text, salt_hex, digest_hex = stored_password.split("$")
            iterations = int(iteration_text)
            expected_digest = bytes.fromhex(digest_hex)
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False
        if prefix != _PASSWORD_HASH_PREFIX or iterations < 1:
            return False
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual_digest, expected_digest)

    @staticmethod
    def _remove_demo_records(
        conn: sqlite3.Connection, imported_usernames: set[str]
    ) -> None:
        demo_applications = (
            ("Maya Chen", "Shared room", "Dockside", "Approved", "High", "Today, 10:40 AM", "Documents verified and assigned to the preferred accommodation."),
            ("Daniel Smith", "Private room", "Harbor View", "In review", "Medium", "Today, 09:10 AM", "Awaiting final confirmation from the housing coordinator."),
            ("Ava Martin", "Container unit", "North site", "Pending", "High", "Yesterday", "Needs a follow-up interview before approval."),
            ("Liam Scott", "Studio", "West block", "Approved", "Medium", "Mon", "Application cleared and move-in scheduled."),
            ("Sofia Kim", "Shared room", "South market", "Needs follow-up", "High", "Sun", "Additional ID verification requested."),
        )
        for application in demo_applications:
            conn.execute(
                """
                DELETE FROM applications
                WHERE applicant_name = ? AND type_name = ? AND location = ?
                  AND status = ? AND priority = ? AND last_update = ? AND notes = ?
                """,
                application,
            )

        demo_meetings = (
            ("Interview", "2026-10-15 09:00", "Scheduled"),
            ("Review", "2026-10-15 11:30", "Pending"),
            ("Move-in check", "2026-10-15 14:00", "Approved"),
            ("Resident support", "2026-10-16 16:30", "Scheduled"),
        )
        for meeting in demo_meetings:
            conn.execute(
                """
                DELETE FROM meetings
                WHERE title = ? AND meeting_time = ? AND status = ?
                  AND mentor_name = 'Community team' AND resident_name = ''
                """,
                meeting,
            )

        demo_residents = (
            ("Ahamed", "Shared accommodation", "Profile summary and onboarding context.", "AH", "#DCE7F5"),
            ("Sara", "Container accommodation", "Profile summary and onboarding context.", "SA", "#E5F0DF"),
            ("Ali", "Commercial accommodation", "Profile summary and onboarding context.", "AL", "#F0E1D8"),
            ("Ava Martin", "Resident", "Resident profile and onboarding context.", "AM", "#E5F0DF"),
        )
        for resident in demo_residents:
            conn.execute(
                """
                DELETE FROM residents
                WHERE name = ? AND role = ? AND description = ?
                  AND initials = ? AND color = ?
                """,
                resident,
            )

        conn.execute(
            """
            DELETE FROM messages
            WHERE sender_username = 'admin' AND recipient_username = 'resident'
              AND subject = 'Your WeRhere support update'
              AND body = ?
            """,
            (
                "Welcome. Your application updates, scheduled meetings and support "
                "information are available from your account. Please reply here "
                "if you need help with your next step.",
            ),
        )
        demo_users = (
            ("admin", "admin123", "Administrator"),
            ("resident", "resident123", "Ava Martin"),
        )
        imported_usernames_normalized = {
            username.casefold() for username in imported_usernames
        }
        for username, password, display_name in demo_users:
            if username.casefold() not in imported_usernames_normalized:
                conn.execute(
                    """
                    DELETE FROM users
                    WHERE username = ? AND password = ? AND display_name = ?
                    """,
                    (username, password, display_name),
                )

    def authenticate_user(self, username: str, password: str) -> bool:
        return self.get_authenticated_user(username, password) is not None

    def get_authenticated_user(
        self, username: str, password: str
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT username, password, role, display_name
                FROM users WHERE username = ?
                """,
                (username.strip(),),
            ).fetchone()
            if row is None or not self._verify_password(password, row["password"]):
                return None
            if not row["password"].startswith(f"{_PASSWORD_HASH_PREFIX}$"):
                conn.execute(
                    "UPDATE users SET password = ? WHERE username = ?",
                    (self._hash_password(password), row["username"]),
                )
            result = dict(row)
            del result["password"]
            return result

    def list_applications(self, query: str = "") -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if query:
                term = f"%{query.lower()}%"
                rows = conn.execute(
                    """
                    SELECT * FROM applications
                    WHERE LOWER(applicant_name) LIKE ?
                       OR LOWER(type_name) LIKE ?
                       OR LOWER(location) LIKE ?
                       OR LOWER(status) LIKE ?
                       OR LOWER(priority) LIKE ?
                    ORDER BY id DESC
                    """,
                    (term, term, term, term, term),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM applications ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    def get_resident_application(
        self, display_name: str
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM applications
                WHERE LOWER(TRIM(applicant_name)) = LOWER(TRIM(?))
                ORDER BY id DESC LIMIT 1
                """,
                (display_name,),
            ).fetchone()
            return dict(row) if row is not None else None

    def add_application(self, payload: Dict[str, Any]) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO applications (applicant_name, type_name, location, status, priority, last_update, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["applicant_name"],
                    payload["type_name"],
                    payload["location"],
                    payload["status"],
                    payload["priority"],
                    payload["last_update"],
                    payload.get("notes", ""),
                ),
            )
            return int(cursor.lastrowid)

    def update_application(self, application_id: int, payload: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE applications
                SET applicant_name = ?, type_name = ?, location = ?, status = ?, priority = ?, last_update = ?, notes = ?
                WHERE id = ?
                """,
                (
                    payload["applicant_name"],
                    payload["type_name"],
                    payload["location"],
                    payload["status"],
                    payload["priority"],
                    payload["last_update"],
                    payload.get("notes", ""),
                    application_id,
                ),
            )

    def delete_application(self, application_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))

    def list_meetings(self, query: str = "") -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if query:
                term = f"%{query.lower()}%"
                rows = conn.execute(
                    """
                    SELECT * FROM meetings
                    WHERE LOWER(title) LIKE ?
                       OR LOWER(status) LIKE ?
                       OR LOWER(meeting_time) LIKE ?
                       OR LOWER(mentor_name) LIKE ?
                       OR LOWER(resident_name) LIKE ?
                    ORDER BY meeting_time ASC
                    """,
                    (term, term, term, term, term),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM meetings ORDER BY meeting_time ASC"
                ).fetchall()
            return [dict(row) for row in rows]

    def add_meeting(self, payload: Dict[str, Any]) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO meetings
                    (title, meeting_time, status, mentor_name, resident_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["title"],
                    payload["meeting_time"],
                    payload["status"],
                    payload.get("mentor_name", "Community team"),
                    payload.get("resident_name", ""),
                ),
            )
            return int(cursor.lastrowid)

    def update_meeting(self, meeting_id: int, payload: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE meetings
                SET title = ?, meeting_time = ?, status = ?, mentor_name = ?, resident_name = ?
                WHERE id = ?
                """,
                (
                    payload["title"],
                    payload["meeting_time"],
                    payload["status"],
                    payload.get("mentor_name", "Community team"),
                    payload.get("resident_name", ""),
                    meeting_id,
                ),
            )

    def delete_meeting(self, meeting_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))

    def list_users(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if role:
                rows = conn.execute(
                    """
                    SELECT username, role, display_name FROM users
                    WHERE role = ? ORDER BY display_name, username
                    """,
                    (role,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT username, role, display_name FROM users ORDER BY display_name, username"
                ).fetchall()
            return [dict(row) for row in rows]

    def list_source_records(
        self, workbook_name: str, sheet_name: str
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source_row, payload_json
                FROM source_records
                WHERE workbook_name = ? AND sheet_name = ?
                ORDER BY source_row
                """,
                (workbook_name, sheet_name),
            ).fetchall()
            return [
                {"source_row": row["source_row"], **json.loads(row["payload_json"])}
                for row in rows
            ]

    def save_application_source_record(
        self, values: Mapping[str, Any], source_row: Optional[int] = None
    ) -> int:
        with self._connect() as conn:
            template = conn.execute(
                """
                SELECT payload_json FROM source_records
                WHERE workbook_name = 'Applications' AND sheet_name = 'Applications'
                ORDER BY source_row LIMIT 1
                """
            ).fetchone()
            if template is None:
                raise ValueError("Application workbook source fields are unavailable.")
            headers = json.loads(template["payload_json"])["headers"]
            payload = json.dumps(
                {
                    "headers": headers,
                    "values": [
                        self._json_value(values.get(header)) for header in headers
                    ],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if source_row is None:
                next_source_row = conn.execute(
                    """
                    SELECT COALESCE(MAX(source_row), 1) + 1
                    FROM source_records
                    WHERE workbook_name = 'Applications' AND sheet_name = 'Applications'
                    """
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO source_records
                        (workbook_name, sheet_name, source_row, payload_json)
                    VALUES ('Applications', 'Applications', ?, ?)
                    """,
                    (next_source_row, payload),
                )
                return int(next_source_row)

            conn.execute(
                """
                INSERT INTO source_records
                    (workbook_name, sheet_name, source_row, payload_json)
                VALUES ('Applications', 'Applications', ?, ?)
                ON CONFLICT(workbook_name, sheet_name, source_row)
                DO UPDATE SET payload_json = excluded.payload_json
                """,
                (source_row, payload),
            )
            return source_row

    def list_messages(self, username: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE sender_username = ? OR recipient_username = ?
                ORDER BY created_at DESC, id DESC
                """,
                (username, username),
            ).fetchall()
            return [dict(row) for row in rows]

    def send_message(
        self, sender: str, recipient: str, subject: str, body: str
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (sender_username, recipient_username, subject, body)
                VALUES (?, ?, ?, ?)
                """,
                (sender, recipient, subject, body),
            )
            return int(cursor.lastrowid)

    def mark_message_read(self, message_id: int, username: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE messages SET is_read = 1
                WHERE id = ? AND recipient_username = ?
                """,
                (message_id, username),
            )

    def list_residents(self, query: str = "") -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if query:
                term = f"%{query.lower()}%"
                rows = conn.execute(
                    "SELECT * FROM residents WHERE LOWER(name) LIKE ? OR LOWER(role) LIKE ? OR LOWER(description) LIKE ? ORDER BY id DESC",
                    (term, term, term),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM residents ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    def add_resident(self, payload: Dict[str, Any]) -> int:
        with self._connect() as conn:
            initials = payload.get("initials") or self._build_initials(payload["name"])
            color = payload.get("color") or "#DCE7F5"
            cursor = conn.execute(
                "INSERT INTO residents (name, role, description, initials, color) VALUES (?, ?, ?, ?, ?)",
                (payload["name"], payload["role"], payload.get("description", ""), initials, color),
            )
            return int(cursor.lastrowid)

    def update_resident(self, resident_id: int, payload: Dict[str, Any]) -> None:
        with self._connect() as conn:
            initials = payload.get("initials") or self._build_initials(payload["name"])
            conn.execute(
                "UPDATE residents SET name = ?, role = ?, description = ?, initials = ?, color = ? WHERE id = ?",
                (
                    payload["name"],
                    payload["role"],
                    payload.get("description", ""),
                    initials,
                    payload.get("color") or "#DCE7F5",
                    resident_id,
                ),
            )

    def delete_resident(self, resident_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM residents WHERE id = ?", (resident_id,))

    def dashboard_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            app_total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
            open_count = conn.execute("SELECT COUNT(*) FROM applications WHERE status IN ('Pending', 'In review', 'Needs follow-up')").fetchone()[0]
            meeting_total = conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0]
            resident_total = conn.execute("SELECT COUNT(*) FROM residents").fetchone()[0]
            recent = conn.execute(
                """
                SELECT applicant_name, type_name, status, priority
                FROM applications ORDER BY id DESC LIMIT 5
                """
            ).fetchall()
            return {
                "applications_total": app_total,
                "needs_attention": open_count,
                "meetings_total": meeting_total,
                "residents_total": resident_total,
                "recent": [dict(row) for row in recent],
            }

    @staticmethod
    def _build_initials(name: str) -> str:
        parts = [p for p in name.split() if p]
        if not parts:
            return "??"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class ApplicationRecord:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MeetingRecord:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if hasattr(self, "meeting_time") and not hasattr(self, "time"):
            self.time = self.meeting_time


class ResidentRecord:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class DataRepository(DatabaseManager):
    def get_applications(self) -> List[ApplicationRecord]:
        return [ApplicationRecord(**item) for item in self.list_applications()]

    def get_meetings(self) -> List[MeetingRecord]:
        return [MeetingRecord(**item) for item in self.list_meetings()]

    def get_residents(self) -> List[ResidentRecord]:
        return [ResidentRecord(**item) for item in self.list_residents()]

    def refresh(self) -> None:
        return None


def initialize_database() -> DatabaseManager:
    return DatabaseManager()
