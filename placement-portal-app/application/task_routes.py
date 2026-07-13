"""
Thin Flask routes around the Celery task queue: trigger the async CSV
export, poll its completion state, and download the finished file. Plain
Blueprint (not Flask-RESTful) since this isn't really a REST resource,
just a job-trigger/job-status/job-download set.
"""
import os

from flask import Blueprint, jsonify, send_file
from flask_login import login_required
from flask_security import current_user

from application.celery_app import celery
from application.tasks import export_csv

task_bp = Blueprint("task_bp", __name__)

# Tracks which student owns which export task_id, in-process, so the
# download route can confirm the requester actually triggered this export
# before handing back the file. Fine for a single-worker course project;
# a real deployment would persist this alongside the task result.
_export_owners = {}


@task_bp.route("/api/student/export-csv", methods=["POST"])
@login_required
def trigger_export():
    student = current_user.student_profile
    if student is None:
        return jsonify({"error": "no student profile found"}), 404

    task = export_csv.delay(student.id)
    _export_owners[task.id] = student.id
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
    student = current_user.student_profile
    if student is None:
        return jsonify({"error": "no student profile found"}), 404

    if _export_owners.get(task_id) != student.id:
        return jsonify({"error": "not your export"}), 403

    result = celery.AsyncResult(task_id)
    if result.state != "SUCCESS":
        return jsonify({"error": "export not ready"}), 409

    filepath = (result.result or {}).get("file")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "export file not found"}), 404

    return send_file(filepath, mimetype="text/csv", as_attachment=True,
                      download_name=f"my_applications_{student.id}.csv")


