"""
Thin Flask routes around the Celery task queue: trigger the async CSV
export, and poll its completion state. Plain Blueprint (not
Flask-RESTful) since this isn't really a REST resource, just a
job-trigger/job-status pair.
"""
from flask import Blueprint, jsonify
from flask_login import login_required
from flask_security import current_user

from application.celery_app import celery
from application.tasks import export_csv

task_bp = Blueprint("task_bp", __name__)


@task_bp.route("/api/student/export-csv", methods=["POST"])
@login_required
def trigger_export():
    student = current_user.student_profile
    if student is None:
        return jsonify({"error": "no student profile found"}), 404

    task = export_csv.delay(student.id)
    return jsonify({"task_id": task.id, "status": "queued"}), 202


@task_bp.route("/api/tasks/<task_id>/status")
@login_required
def task_status(task_id):
    result = celery.AsyncResult(task_id)
    response = {"task_id": task_id, "state": result.state}

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.result)

    return jsonify(response)