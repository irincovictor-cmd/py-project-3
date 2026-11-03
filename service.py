"""RoomReserve validation, permissions and scheduling rules (GUI-independent)."""
from __future__ import annotations
from datetime import date, datetime
import hashlib
import hmac
import secrets
import re
import sqlite3
from database import Database

class BookingError(ValueError):
    pass


def _check_date(day):
    try:
        d = date.fromisoformat(day)
        if d.isoformat() != day:
            raise ValueError
        return d
    except (ValueError, TypeError):
        raise BookingError('Date must use YYYY-MM-DD.') from None


def _check_window(start, end):
    for val in (start, end):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(val)):
            raise BookingError('Time must use 24-hour HH:MM.')
    if start >= end:
        raise BookingError('End time must be after start time.')


def _hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 300_000).hex()

class RoomReserve:
    def __init__(self, path):
        self.db = Database(path)

    def has_users(self):
        with self.db.connect() as cx:
            return bool(cx.execute('SELECT 1 FROM users LIMIT 1').fetchone())

    def create_user(self, actor_id, username, password, role):
        username = username.strip().lower()
        if not re.fullmatch(r'[a-z0-9_]{3,30}', username):
            raise BookingError('Username: 3–30 letters, digits or underscores.')
        if len(password) < 8:
            raise BookingError('Password must have at least 8 characters.')
        if role not in ('admin', 'instructor'):
            raise BookingError('Invalid role.')
        with self.db.connect() as cx:
            if cx.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                self._require(cx, actor_id, 'admin')
            elif actor_id is not None or role != 'admin':
                raise BookingError('The first account must be an administrator.')
            salt = secrets.token_hex(16)
            try:
                cur = cx.execute('INSERT INTO users(username,password_hash,salt,role) VALUES(?,?,?,?)',
                                 (username, _hash(password,salt),salt,role))
            except sqlite3.IntegrityError:
                raise BookingError('Username already exists.') from None
            return cur.lastrowid

    def login(self, username, password):
        with self.db.connect() as cx:
            row = cx.execute('SELECT * FROM users WHERE username=? AND active=1', (username.strip(),)).fetchone()
            if not row or not hmac.compare_digest(_hash(password,row['salt']),row['password_hash']):
                raise BookingError('Invalid username or password.')
            return dict(row)

    def _require(self, cx, user_id, role=None):
        user = cx.execute('SELECT * FROM users WHERE id=? AND active=1', (user_id,)).fetchone()
        if not user or (role and user['role'] != role):
            raise BookingError('You do not have permission for this action.')
        return user

    def users(self, actor_id):
        with self.db.connect() as cx:
            self._require(cx, actor_id, 'admin')
            return [dict(r) for r in cx.execute('SELECT id,username,role,active FROM users ORDER BY username')]

    def add_room(self, actor_id, code, name, category, capacity):
        code, name, category = code.strip().upper(), name.strip(), category.strip()
        if not re.fullmatch(r'[A-Z0-9-]{2,20}',code) or not name or not category:
            raise BookingError('Enter a valid room code, name and category.')
        try:
            capacity = int(capacity)
        except (ValueError, TypeError):
            raise BookingError('Capacity must be a whole number.') from None
        if not 1 <= capacity <= 5000:
            raise BookingError('Capacity must be between 1 and 5000.')
        with self.db.connect() as cx:
            self._require(cx, actor_id, 'admin')
            try:
                return cx.execute('INSERT INTO rooms(code,name,category,capacity) VALUES(?,?,?,?)',
                                  (code,name,category,capacity)).lastrowid
            except sqlite3.IntegrityError:
                raise BookingError('Room code already exists.') from None

    def edit_room(self, actor_id, room_id, code, name, category, capacity):
        code, name, category = code.strip().upper(), name.strip(), category.strip()
        if not re.fullmatch(r'[A-Z0-9-]{2,20}', code) or not name or not category:
            raise BookingError('Enter a valid room code, name and category.')
        try:
            capacity = int(capacity)
        except (ValueError, TypeError):
            raise BookingError('Capacity must be a whole number.') from None
        if not 1 <= capacity <= 5000:
            raise BookingError('Capacity must be between 1 and 5000.')
        with self.db.connect() as cx:
            self._require(cx, actor_id, 'admin')
            if not cx.execute('SELECT 1 FROM rooms WHERE id=?', (room_id,)).fetchone():
                raise BookingError('Room not found.')
            if cx.execute("SELECT 1 FROM reservations WHERE room_id=? AND status='Approved' AND attendees>? AND event_date>=date('now') LIMIT 1", (room_id,capacity)).fetchone():
                raise BookingError('Room capacity is below an existing approved booking.')
            try:
                cx.execute('UPDATE rooms SET code=?,name=?,category=?,capacity=? WHERE id=?',
                           (code,name,category,capacity,room_id))
            except sqlite3.IntegrityError:
                raise BookingError('Room code already exists.') from None

    def set_room_active(self, actor_id, room_id, active):
        with self.db.connect() as cx:
            self._require(cx,actor_id,'admin')
            if not cx.execute('SELECT 1 FROM rooms WHERE id=?',(room_id,)).fetchone():
                raise BookingError('Room not found.')
            cx.execute('UPDATE rooms SET active=? WHERE id=?',(int(bool(active)),room_id))

    def rooms(self, active_only=False):
        with self.db.connect() as cx:
            q = 'SELECT * FROM rooms' + (' WHERE active=1' if active_only else '') + ' ORDER BY code'
            return [dict(r) for r in cx.execute(q)]

    @staticmethod
    def _conflict(cx, room_id, day, start, end, omit=None):
        return cx.execute('''SELECT r.id FROM reservations r WHERE room_id=? AND event_date=?
          AND status='Approved' AND start_time < ? AND end_time > ? AND (? IS NULL OR id != ?) LIMIT 1''',
          (room_id,day,end,start,omit,omit)).fetchone()

    def request(self, user_id, room_id, day, start, end, purpose, attendees):
        _check_date(day)
        _check_window(start,end)
        if _check_date(day) < date.today():
            raise BookingError('Cannot reserve a date in the past.')
        if not 3 <= len(purpose.strip()) <= 200:
            raise BookingError('Purpose must contain 3–200 characters.')
        try:
            attendees = int(attendees)
        except (ValueError, TypeError):
            raise BookingError('Attendees must be a whole number.') from None
        with self.db.connect() as cx:
            self._require(cx,user_id)
            room = cx.execute('SELECT * FROM rooms WHERE id=? AND active=1',(room_id,)).fetchone()
            if not room:
                raise BookingError('Room is unavailable.')
            if not 1 <= attendees <= room['capacity']:
                raise BookingError(f'Attendees must be 1–{room["capacity"]} for this room.')
            if self._conflict(cx,room_id,day,start,end):
                raise BookingError('This room is already booked during the requested time.')
            return cx.execute('''INSERT INTO reservations(room_id,user_id,event_date,start_time,end_time,purpose,attendees)
                VALUES(?,?,?,?,?,?,?)''',(room_id,user_id,day,start,end,purpose.strip(),attendees)).lastrowid

    def review(self, admin_id, reservation_id, approve, note=''):
        with self.db.connect() as cx:
            self._require(cx,admin_id,'admin')
            row = cx.execute('SELECT * FROM reservations WHERE id=?',(reservation_id,)).fetchone()
            if not row or row['status'] != 'Pending':
                raise BookingError('Only pending requests can be reviewed.')
            if approve:
                room = cx.execute('SELECT * FROM rooms WHERE id=?',(row['room_id'],)).fetchone()
                if not room['active']:
                    raise BookingError('Cannot approve a request for a disabled room.')
                if self._conflict(cx,row['room_id'],row['event_date'],row['start_time'],row['end_time'],reservation_id):
                    raise BookingError('Approval blocked: another reservation overlaps this time.')
                if row['attendees'] > room['capacity']:
                    raise BookingError('Reservation exceeds room capacity.')
            cx.execute('''UPDATE reservations SET status=?,reviewed_by=?,review_note=? WHERE id=?''',
                       ('Approved' if approve else 'Rejected',admin_id,note.strip()[:500],reservation_id))

    def cancel(self, user_id, reservation_id):
        with self.db.connect() as cx:
            actor = self._require(cx,user_id)
            row = cx.execute('SELECT * FROM reservations WHERE id=?',(reservation_id,)).fetchone()
            if not row or (row['user_id'] != user_id and actor['role'] != 'admin'):
                raise BookingError('Reservation not found or access denied.')
            if row['status'] not in ('Pending','Approved'):
                raise BookingError('Only pending or approved reservations can be cancelled.')
            cx.execute("UPDATE reservations SET status='Cancelled' WHERE id=?",(reservation_id,))

    def reservations(self, actor_id=None, public=False, day=None, room_id=None, status=None):
        if day:
            _check_date(day)
        with self.db.connect() as cx:
            if not public:
                actor = self._require(cx,actor_id)
            clauses, vals = [], []
            if public:
                clauses.append("r.status='Approved'")
            elif actor['role'] != 'admin':
                clauses.append('r.user_id=?'); vals.append(actor_id)
            if day:
                clauses.append('r.event_date=?'); vals.append(day)
            if room_id is not None:
                clauses.append('r.room_id=?'); vals.append(room_id)
            if status:
                if status not in ('Pending','Approved','Rejected','Cancelled'):
                    raise BookingError('Invalid status filter.')
                clauses.append('r.status=?'); vals.append(status)
            query = '''SELECT r.*,rooms.code AS room_code,rooms.name AS room_name,u.username AS requester
               FROM reservations r JOIN rooms ON rooms.id=r.room_id JOIN users u ON u.id=r.user_id'''
            if clauses:
                query += ' WHERE ' + ' AND '.join(clauses)
            query += ' ORDER BY r.event_date DESC,r.start_time,r.id DESC'
            return [dict(r) for r in cx.execute(query, vals)]

    def available(self, day, start, end, attendees=1, category=None):
        _check_date(day); _check_window(start,end)
        try:
            attendees=int(attendees)
        except (ValueError, TypeError):
            raise BookingError('Attendees must be a whole number.') from None
        if attendees < 1:
            raise BookingError('Attendees must be positive.')
        with self.db.connect() as cx:
            query='''SELECT rooms.* FROM rooms WHERE active=1 AND capacity>=? AND NOT EXISTS (
               SELECT 1 FROM reservations r WHERE r.room_id=rooms.id AND r.event_date=?
               AND r.status='Approved' AND r.start_time < ? AND r.end_time > ?)'''
            vals=[attendees,day,end,start]
            if category and category != 'All':
                query+=' AND category=?'; vals.append(category)
            query+=' ORDER BY code'
            return [dict(r) for r in cx.execute(query,vals)]
