# RoomReserve — Classroom and Facility Reservation Management System

Offline Python desktop prototype for administrator-approved classroom reservations.

## Setup (Windows)

Requires Python 3.10 or newer with Tkinter. No third-party packages are required.

```powershell
python main.py
```

On first launch, create an administrator account (at least 8 characters for the password). The administrator creates rooms and instructor accounts in **Manage Rooms** and **Manage Users**. Instructors sign in and submit reservation requests. Administrators approve or reject them in **Approvals**. Everyone, including students without accounts, can use **View Public Timetable** and **Find Availability**.

## Reservation rules

- Reservation dates must be today or later, with strict `YYYY-MM-DD` and 24-hour `HH:MM` formatting.
- End time must be later than start time; bookings are same-day only.
- Room must be active and attendees must not exceed room capacity.
- New reservations start `Pending`; only administrators can approve/reject.
- Only `Approved` bookings occupy availability and the public timetable.
- Overlaps use `existing_start < requested_end AND existing_end > requested_start`; adjacent reservations are allowed.
- Pending requests can overlap; approval rechecks for conflicts so only one competing request can be approved.
- Instructors see and cancel only their own reservations; administrators manage all requests.
- Data is stored in local `roomreserve.db` (SQLite). Keep this file when upgrading or moving the application. It is excluded from Git.

## Project structure

- `main.py` — Tkinter GUI, public and signed-in workspaces
- `service.py` — validation, permissions, scheduling, search, bookings
- `database.py` — SQLite schema and connections
- `tests/test_service.py` — isolated automated tests with temporary databases

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Limitations

This is a classroom demonstration for **one computer**, not a networked multi-user booking portal. Public viewing means accessible without signing in on the same machine. It does not synchronize schedules across multiple PCs, send notifications, validate identities against school records, or process payments. A SQLite database stores password hashes with per-user salts, not plaintext passwords. Back up the database before significant upgrades.

## Weekly timetable and room updates

The public timetable supports both single-date search and a seven-day Monday–Sunday view. Administrators may load a selected room into the editor to change its code, name, category, and capacity. Capacity reductions are blocked when they would invalidate future approved reservations.