"""
Standalone Celery instance. Kept free of any dependency on app.py so
tasks.py (and any route that triggers a task) can import it without
risking a circular import. app.py binds Flask-application-context
awareness onto this same instance inside create_app(), which is what
makes `celery -A app.celery worker` work correctly.
"""
from celery import Celery

celery = Celery("placement_portal")
celery.config_from_object("celery_config")

