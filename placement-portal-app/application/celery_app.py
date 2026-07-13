"""
Standalone Celery instance.

Why this file matters:
- It must stay importable without creating a circular import with app.py.
- It must load celery_config.py for broker/backend/beat settings.
- It must also import the task module so Celery workers and Celery Beat
  both know about all registered tasks (scheduled + user-triggered).

Without importing application.tasks here, periodic tasks may exist in
beat_schedule but the worker may not register them properly, causing the
"works with .apply() manually, but not automatically" symptom.
"""
from celery import Celery

celery = Celery("placement_portal")
celery.config_from_object("celery_config")

# Force task registration on worker/beat startup.
# This makes sure these named tasks are discoverable:
# - application.tasks.interview_reminder
# - application.tasks.deadline_reminder
# - application.tasks.monthly_placement_report
# - application.tasks.export_csv
import application.tasks  # noqa: F401