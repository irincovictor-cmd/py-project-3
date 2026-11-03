"""SQLite setup and transactional connections for RoomReserve."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL, salt TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','instructor')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS rooms (
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
 name TEXT NOT NULL, category TEXT NOT NULL,
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 5000),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS reservations (
 id INTEGER PRIMARY KEY, room_id INTEGER NOT NULL REFERENCES rooms(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 event_date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
 purpose TEXT NOT NULL, attendees INTEGER NOT NULL CHECK(attendees>0),
 status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected','Cancelled')),
 reviewed_by INTEGER REFERENCES users(id), review_note TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_booking_window ON reservations(room_id,event_date,status,start_time,end_time);
"""

class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
