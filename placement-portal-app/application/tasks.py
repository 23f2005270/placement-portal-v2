"""
Background jobs. interview_reminder and monthly_placement_report are
scheduled via Celery Beat (see celery_config.py). export_csv is
user-triggered from a Flask route and runs async, with its Celery
AsyncResult state acting as the completion signal the frontend polls.
"""
import csv
import os
from datetime import datetime, timedelta

from application.celery_app import celery
from application.database import db
from application.models import Application, Placement


@celery.task(name="application.tasks.interview_reminder")
def interview_reminder():
    """
    Daily: find applications with an interview scheduled in the next 24
    hours and notify the student. No email/SMS integration yet, so this
    logs the reminder — the hook is here for whichever channel gets
    wired in later.
    """
    window_end = datetime.utcnow() + timedelta(hours=24)
    upcoming = Application.query.filter(
        Application.status == "Interview",
        Application.interview_datetime.isnot(None),
        Application.interview_datetime >= datetime.utcnow(),
        Application.interview_datetime <= window_end,
    ).all()

    sent = []
    for a in upcoming:
        student = a.student
        drive = a.drive
        if not student or not drive:
            continue
        email = student.user.email if student.user else "unknown"
        message = (
            f"[REMINDER] {student.full_name} <{email}> has an interview for "
            f"'{drive.title}' at {a.interview_datetime.isoformat()}"
        )
        print(message)
        sent.append({"application_id": a.id, "student": student.full_name})

    return {"reminders_sent": len(sent), "details": sent}


@celery.task(name="application.tasks.monthly_placement_report")
def monthly_placement_report():
    """
    Runs on the 1st of each month. Summarizes the previous ~30 days of
    placements into a text report for admin, saved under instance/reports/.
    """
    since = datetime.utcnow() - timedelta(days=30)
    placements = Placement.query.filter(Placement.created_at >= since).all()

    lines = [
        f"Monthly Placement Report — generated {datetime.utcnow().isoformat()}",
        "-" * 50,
    ]
    for p in placements:
        student_name = p.student.full_name if p.student else "Unknown"
        company_name = p.company.name if p.company else "Unknown"
        lines.append(f"{student_name} -> {company_name} ({p.position}, {p.salary})")
    lines.append(f"\nTotal placements this period: {len(placements)}")

    reports_dir = os.path.join("instance", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    filename = os.path.join(
        reports_dir, f"placement_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(filename, "w") as f:
        f.write("\n".join(lines))

    return {"report_file": filename, "placement_count": len(placements)}


@celery.task(name="application.tasks.export_csv", bind=True)
def export_csv(self, student_id):
    """
    User-triggered async CSV export of one student's application history.
    Returns the file path and row count on completion — polled via the
    task's AsyncResult state from the frontend.
    """
    exports_dir = os.path.join("instance", "exports")
    os.makedirs(exports_dir, exist_ok=True)
    filename = os.path.join(exports_dir, f"export_{self.request.id}.csv")

    applications = Application.query.filter_by(student_id=student_id).all()

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["application_id", "drive_title", "company_name", "status", "applied_date"]
        )
        for a in applications:
            writer.writerow(
                [
                    a.id,
                    a.drive.title if a.drive else "",
                    a.drive.company.name if a.drive and a.drive.company else "",
                    a.status,
                    a.applied_date.isoformat() if a.applied_date else "",
                ]
            )

    return {"status": "completed", "file": filename, "row_count": len(applications)}