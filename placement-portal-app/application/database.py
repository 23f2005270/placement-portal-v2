"""
Shared SQLAlchemy instance. Imported by models.py, app.py, and anything
else that needs `db` without triggering a circular import.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()