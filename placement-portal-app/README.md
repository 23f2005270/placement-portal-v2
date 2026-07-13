# Placement Portal Application V2

A comprehensive placement management system built for the MAD-II course.

## Features
- Admin dashboard (tabbed: Companies / Drives / Students / Applications) for full company/drive/student/application oversight
- Company registration and drive creation with approval workflow, applicant counts on both admin and company drive tables
- Student profile, resume upload, and drive application system with eligibility-based search/filtering
- Application status tracking (Applied → Shortlisted → Interview → Offer → Placed)
- Background jobs: interview reminders, deadline reminders, monthly HTML reports, and user-triggered CSV export — all via Celery
- Student-triggered async CSV export, fully wired end-to-end: dashboard button → Celery job → live polling → toast notification → download
- Caching with Redis for fast search/listing (60s expiry, cleared on writes)
- Role-based access control (RBAC) via Flask-Principal
- Custom design system (ink/paper/emerald palette, status-accented ledger tables) built on Bootstrap only, per the project's CSS-framework constraint
- Toast notifications throughout (replacing raw `alert()` calls) for a consistent, non-blocking feedback pattern
- PWA-installable ("Add to desktop") via manifest + service worker

## Stack
- **Backend:** Flask, Flask-SQLAlchemy, Flask-Security-Too
- **Auth/RBAC:** Flask-Login, Flask-Principal
- **API:** Flask-RESTful
- **Database:** SQLite
- **Frontend:** Vue 2 (CDN), Bootstrap (CDN), custom CSS design system — no other CSS/JS framework
- **Background Jobs:** Celery + Redis
- **Caching:** Flask-Caching + Redis

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -c "from application.seed import seed_admin; seed_admin()"
python3 app.py
```

In separate terminals, also run:
```bash
celery -A app.celery worker --loglevel=info
celery -A app.celery beat --loglevel=info
```

Redis must be running locally (`redis-server`) for caching, Celery, and the CSV export/report jobs to work. A local SMTP catcher (e.g. Mailpit on port 1025) is needed for reminder/report emails to actually deliver in dev.

Default admin login: `admin@placementportal.com` / `AdminPass123!`

## API additions in this pass
- `GET /api/admin/applications` — admin-wide view of every application, with `q` (student/drive/company) and `status` filters
- `GET /api/admin/drives?q=...` — free-text search over drive title / company name (previously status-filter only)
- `GET /api/student/export-csv/<task_id>/download` — streams the finished CSV once the export job completes
- `applicant_count` added to both `/api/admin/drives` and `/api/company/drives` responses
- CSV export columns reordered to match the project statement exactly: `student_id, company_name, drive_title, application_status, applied_date`

