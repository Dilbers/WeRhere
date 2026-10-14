from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "wehere.db"


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_parent_dir()
        self._init_db()

    def _ensure_parent_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'resident',
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
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'resident'"
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
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
                INSERT OR IGNORE INTO users (username, password, role, display_name)
                VALUES (?, ?, ?, ?)
                """,
                ("admin", "admin123", "admin", "Administrator"),
            )
            conn.execute(
                """
                UPDATE users SET role = 'admin', display_name = 'Administrator'
                WHERE username = 'admin'
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO users (username, password, role, display_name)
                VALUES (?, ?, ?, ?)
                """,
                ("resident", "resident123", "resident", "Ava Martin"),
            )

            if conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] == 0:
                conn.executemany(
                    """
                    INSERT INTO applications (applicant_name, type_name, location, status, priority, last_update, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("Maya Chen", "Shared room", "Dockside", "Approved", "High", "Today, 10:40 AM", "Documents verified and assigned to the preferred accommodation."),
                        ("Daniel Smith", "Private room", "Harbor View", "In review", "Medium", "Today, 09:10 AM", "Awaiting final confirmation from the housing coordinator."),
                        ("Ava Martin", "Container unit", "North site", "Pending", "High", "Yesterday", "Needs a follow-up interview before approval."),
                        ("Liam Scott", "Studio", "West block", "Approved", "Medium", "Mon", "Application cleared and move-in scheduled."),
                        ("Sofia Kim", "Shared room", "South market", "Needs follow-up", "High", "Sun", "Additional ID verification requested."),
                    ],
                )

            if conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 0:
                conn.executemany(
                    "INSERT INTO meetings (title, meeting_time, status) VALUES (?, ?, ?)",
                    [
                        ("Interview", "2026-10-15 09:00", "Scheduled"),
                        ("Review", "2026-10-15 11:30", "Pending"),
                        ("Move-in check", "2026-10-15 14:00", "Approved"),
                        ("Resident support", "2026-10-16 16:30", "Scheduled"),
                    ],
                )
            conn.execute(
                """
                UPDATE meetings SET mentor_name = 'Community team'
                WHERE mentor_name = ''
                """
            )

            if conn.execute("SELECT COUNT(*) FROM residents").fetchone()[0] == 0:
                conn.executemany(
                    """
                    INSERT INTO residents (name, role, description, initials, color)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        ("Ahamed", "Shared accommodation", "Profile summary and onboarding context.", "AH", "#DCE7F5"),
                        ("Sara", "Container accommodation", "Profile summary and onboarding context.", "SA", "#E5F0DF"),
                        ("Ali", "Commercial accommodation", "Profile summary and onboarding context.", "AL", "#F0E1D8"),
                    ],
                )
            conn.execute(
                """
                INSERT INTO residents (name, role, description, initials, color)
                SELECT ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM residents WHERE LOWER(TRIM(name)) = LOWER(?)
                )
                """,
                (
                    "Ava Martin",
                    "Resident",
                    "Resident profile and onboarding context.",
                    "AM",
                    "#E5F0DF",
                    "Ava Martin",
                ),
            )
            message_exists = conn.execute(
                """
                SELECT 1 FROM messages
                WHERE sender_username = 'admin'
                  AND recipient_username = 'resident'
                  AND subject = 'Your WeRhere support update'
                LIMIT 1
                """
            ).fetchone()
            if message_exists is None:
                conn.execute(
                    """
                    INSERT INTO messages (sender_username, recipient_username, subject, body)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "admin",
                        "resident",
                        "Your WeRhere support update",
                        "Welcome. Your application updates, scheduled meetings and support "
                        "information are available from your account. Please reply here "
                        "if you need help with your next step.",
                    ),
                )

    def authenticate_user(self, username: str, password: str) -> bool:
        return self.get_authenticated_user(username, password) is not None

    def get_authenticated_user(
        self, username: str, password: str
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT username, role, display_name
                FROM users WHERE username = ? AND password = ?
                """,
                (username.strip(), password),
            ).fetchone()
            return dict(row) if row is not None else None

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
