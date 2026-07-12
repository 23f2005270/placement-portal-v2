"""
Celery configuration. Loaded via `celery_app.config_from_object("celery_config")`.
Kept as a plain settings module (not inside application/) to match the
project layout convention — one file, project root, easy to find.
"""
from celery.schedules import crontab

broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"
timezone = "Asia/Kolkata"
enable_utc = True

beat_schedule = {
    "interview-reminder-daily": {
        "task": "application.tasks.interview_reminder",
        "schedule": crontab(hour=8, minute=0),  # once a day, 8 AM IST
    },
     "deadline-reminder-daily": {
        "task": "application.tasks.deadline_reminder",
        "schedule": crontab(hour=8, minute=30),  # staggered from interview reminder
    },
    "monthly-placement-report": {
        "task": "application.tasks.monthly_placement_report",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),  # 1st of each month
    },
}