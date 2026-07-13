# Placement Portal Application V2 (PPA V2)

A campus placement management system with three roles — **Admin**, **Company**, and **Student** — built for MAD-II. Companies post drives (post-approval), students apply, and the whole pipeline from application to placement is tracked end to end.

## Features

- Admin dashboard: approve/reject companies & drives, blacklist companies/students, search, live stats
- Company dashboard: profile, drive creation (once approved), applicant management, status updates
- Student dashboard: profile + resume upload, browse/apply to eligible drives, application & placement history
- Full application status pipeline: `Applied → Shortlisted → Interview → Offer / Rejected → Placed`
- Background jobs via Celery: interview reminders, upcoming-deadline reminders, monthly HTML report (emailed to admin), async CSV export
- Redis-backed API caching (job listings, company search, student search) with expiry + invalidation
- RBAC via Flask-Principal (Admin / Company / Student permission boundaries)
- PWA-ready (manifest + service worker for the app shell)

## Stack

| Layer | Tech |
|---|---|
| Backend | Flask 3.1, Flask-SQLAlchemy, Flask-Security-Too |
| Auth / RBAC | Flask-Login, Flask-Principal |
| API | Flask-RESTful |
| Database | SQLite |
| Frontend | Vue 2 (CDN, single Jinja-served template) + Bootstrap 5 (CDN) |
| Background jobs | Celery 5.6 + Redis (broker/result backend, DB 0) |
| Caching | Flask-Caching + Redis (DB 1, separate from Celery) |
| Mail (dev) | SMTP via Mailpit |

## Prerequisites

- **Python 3.12** (project pins `3.12.7` in `.python-version`)
- **Redis** — used by both Celery and Flask-Caching
- **Mailpit** — local SMTP catcher so reminder/report emails are visible without real credentials

Install the two services on macOS:

```bash
brew install redis
brew install mailpit
```

## 1. Set up the app

```bash
cd placement-portal-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Start supporting services

Each of these runs in its own terminal tab (or as background services — see the note at the bottom).

**Redis:**
```bash
redis-server
```

**Mailpit** (SMTP on `localhost:1025`, inbox UI on `http://localhost:8025`):
```bash
mailpit
```

## 3. Seed the database

Creates the three roles (`admin`, `company`, `student`) and the one admin account. This is the *only* way an admin account is ever created — there's no admin self-registration.

```bash
python3 -c "from application.seed import seed_admin; seed_admin()"
```

Default admin login:
```
Email:    admin@placementportal.com
Password: AdminPass123!
```

## 4. Run the app

**Flask (dev server):**
```bash
python3 app.py
```
Serves at **http://localhost:5000**

**Celery worker** (in a new terminal, venv activated):
```bash
celery -A app.celery worker --loglevel=info
```

**Celery beat** (scheduler, in another new terminal):
```bash
celery -A app.celery beat --loglevel=info
```

Beat triggers, on schedule (`celery_config.py`):
- Interview reminders — daily, 8:00 AM IST
- Deadline reminders — daily, 8:30 AM IST
- Monthly placement report (emailed to admin) — 1st of each month, midnight IST

## 5. Try it out

Open **http://localhost:5000**:

1. Click **"Don't have an account? Register"** to create a student or company account.
2. Company accounts start `pending` — log in as admin (`admin@placementportal.com` / `AdminPass123!`) and approve it under **Companies**.
3. Log in as the company, create a drive — it also needs admin approval before students can see it.
4. Log in as the student, apply, and track status changes made by the company.
5. Move an application to `Placed` from the company dashboard — it auto-creates a placement record, visible in the student's **Placement History**.

## Running scheduled jobs on demand (for testing/demo)

You don't have to wait for Celery beat's schedule — trigger any task directly and watch the result:

```bash
python3 -c "
from app import app
from application.tasks import deadline_reminder, interview_reminder, monthly_placement_report
with app.app_context():
    print(deadline_reminder.apply().get())
    print(interview_reminder.apply().get())
    print(monthly_placement_report.apply().get())
"
```

Then check **http://localhost:8025** — sent emails (deadline/interview reminders, the HTML monthly report) land there, fully rendered.

CSV export is triggered from the student dashboard UI itself (async via Celery, polled by task ID) rather than on a schedule.

## Redis debugging

```bash
redis-cli -n 0 keys "*"   # Celery broker/result keys
redis-cli -n 1 keys "*"   # Flask-Caching keys (student drives, admin company/student search)
```

## Ports reference

| Service | URL/Port |
|---|---|
| Flask app | http://localhost:5000 |
| Redis | localhost:6379 |
| Mailpit SMTP | localhost:1025 |
| Mailpit inbox UI | http://localhost:8025 |

## Environment variables (all optional — sane defaults for local dev)

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-secret-change-me` | Flask session signing |
| `SECURITY_PASSWORD_SALT` | `dev-salt-change-me` | Flask-Security password hashing |
| `SMTP_HOST` | `localhost` | Mail server (Mailpit) |
| `SMTP_PORT` | `1025` | Mail server port |
| `SMTP_SENDER` | `placements@ppa-portal.local` | From address on outgoing mail |
| `SMTP_USER` / `SMTP_PASSWORD` | *(empty)* | Only needed for a real SMTP account, not Mailpit |
| `SMTP_USE_TLS` | `false` | Only needed for a real SMTP account |

## Project structure

```
placement-portal-app/
├── app.py                      # App factory, Flask-Security setup, Celery binding
├── celery_config.py             # Broker/backend URLs + beat schedule
├── flask_cache.py               # Redis-backed Flask-Caching instance (DB 1)
├── requirements.txt
├── application/
│   ├── models.py                 # User/Role, Student, Company, Drive, Application, Placement
│   ├── database.py
│   ├── permissions.py            # Flask-Principal RBAC setup
│   ├── auth_routes.py            # /login, /register, /logout
│   ├── admin_routes.py           # Admin API (stats, companies, drives, students)
│   ├── company_routes.py         # Company API (profile, drives, applicants)
│   ├── student_routes.py         # Student API (profile, resume, drives, applications, placements)
│   ├── task_routes.py            # CSV export trigger + polling
│   ├── tasks.py                  # Celery tasks (reminders, report, CSV export)
│   ├── mail.py                   # SMTP helper used by tasks.py
│   ├── celery_app.py             # Standalone Celery instance
│   └── seed.py                   # Admin/role seeding script
├── templates/index.html          # Single Vue 2 SPA (all three dashboards + login/register)
├── static/manifest.json, sw.js   # PWA manifest + service worker
└── instance/
    ├── placement.db              # SQLite (auto-created on first run)
    ├── reports/                  # Archived monthly HTML reports
    └── exports/                  # Generated CSV exports
```

## Troubleshooting

**"There's no register button / I land straight on a dashboard"**
You likely still have a valid session cookie from earlier testing. The login/register screen only shows when logged out — click **Log out**, or open the app in a private/incognito window.

**`MemoryError` from the Celery worker on macOS**
Already handled — `app.py` disposes the inherited SQLAlchemy engine on worker process init (`worker_process_init` signal), since SQLite connections aren't safe to share across Celery's forked worker processes.

**Emails aren't showing up in Mailpit**
Confirm `mailpit` is actually running and check `http://localhost:8025` directly. `mail.py`'s `send_email()` never raises — a Celery task result will still show `"mailed": false` in its return value if delivery silently failed, which is the fastest way to check.

**Reset everything (fresh DB)**
```bash
rm instance/placement.db
python3 -c "from application.seed import seed_admin; seed_admin()"
```

## Running services in the background (optional)

Instead of holding four terminal tabs open:
```bash
brew services start redis
brew services start mailpit
```
Flask, the Celery worker, and Celery beat still need their own terminals since they're project-specific processes, not system services.