"""
Thin Flask routes around the Celery task queue: trigger the async CSV
export, and poll its completion state. Plain Blueprint (not
Flask-RESTful) since this isn't really a REST resource, just a
job-trigger/job-status pair.
"""
import os

from flask import Blueprint, jsonify, send_file
from flask_login import login_required
from flask_security import current_user

from application.celery_app import celery
from application.tasks import export_csv
from application.permissions import admin_permission
from application.models import ReminderLog
from application.tasks import interview_reminder, deadline_reminder, monthly_placement_report
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


@task_bp.route("/api/student/export-csv/<task_id>/download")
@login_required
def download_export(task_id):
    """
    Streams the finished CSV back once the Celery task has completed.
    Ownership isn't tracked per-task (course-project scope), but the
    file only ever contains rows for whichever student triggered it, and
    a task_id is an unguessable UUID, so this is fine for a local demo.
    """
    student = current_user.student_profile
    if student is None:
        return jsonify({"error": "no student profile found"}), 404

    result = celery.AsyncResult(task_id)
    if result.state != "SUCCESS":
        return jsonify({"error": "export is not ready yet"}), 409

    filepath = (result.result or {}).get("file")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "export file not found"}), 404

    return send_file(
        filepath,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"my_applications_{student.id}.csv",
    )




def admin_required(method):
    return login_required(admin_permission.require(http_exception=403)(method))


@task_bp.route("/api/admin/reminders/trigger/<kind>", methods=["POST"])
@admin_required
def trigger_reminder(kind):
    """Fire any scheduled job on demand — handy for demoing without waiting for Beat."""
    mapping = {
        "interview": interview_reminder,
        "deadline": deadline_reminder,
        "monthly-report": monthly_placement_report,
    }
    task_fn = mapping.get(kind)
    if not task_fn:
        return jsonify({"error": "unknown reminder kind"}), 400
    task = task_fn.delay()
    return jsonify({"task_id": task.id, "status": "queued"}), 202


@task_bp.route("/api/admin/reminders/log")
@admin_required
def reminder_log():
    logs = ReminderLog.query.order_by(ReminderLog.sent_at.desc()).limit(200).all()
    return jsonify([
        {"id": l.id, "kind": l.kind, "student_id": l.student_id,
         "reference_id": l.reference_id, "sent_at": l.sent_at.isoformat() if l.sent_at else None}
        for l in logs
    ])