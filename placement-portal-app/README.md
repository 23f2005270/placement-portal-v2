# Placement Portal Application V2

A comprehensive placement management system built for the MAD-II course.

## Features
- Admin dashboard for company/drive/student management
- Company registration and drive creation with approval workflow
- Student profile, resume upload, and drive application system
- Application status tracking (Applied → Shortlisted → Interview → Offer)
- Background jobs: interview reminders, monthly reports, CSV exports via Celery
- Caching with Redis for fast search/listing
- Role-based access control (RBAC) via Flask-Principal

## Stack
- **Backend:** Flask, Flask-SQLAlchemy, Flask-Security-Too
- **Auth/RBAC:** Flask-Login, Flask-Principal
- **API:** Flask-RESTful
- **Database:** SQLite
- **Frontend:** Vue 2 (CDN), Bootstrap (CDN)
- **Background Jobs:** Celery + Redis
- **Caching:** Flask-Caching + Redis

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py