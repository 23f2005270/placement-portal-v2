"""
Background jobs. interview_reminder, deadline_reminder, and
monthly_placement_report are scheduled via Celery Beat (see
celery_config.py). export_csv is user-triggered from a Flask route and
runs async, with its Celery AsyncResult state acting as the completion
signal the frontend polls.
"""
import csv
import os
from datetime import datetime, timedelta

from application.celery_app import celery
from application.database import db
from application.mail import send_email
from application.models import Application, Drive, Placement, Role, Student


def _get_admin_email():
    admin_role = Role.query.filter_by(name="admin").first()
    admin_user = admin_role.users.first() if admin_role else None
    return admin_user.email if admin_user else None


@celery.task(name="application.tasks.interview_reminder")
def interview_reminder():
    """
    Daily: find applications with an interview scheduled in the next 24
    hours and email the student.
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
        if not student or not drive or not student.user:
            continue
        when = a.interview_datetime.strftime("%d %b %Y, %I:%M %p")
        subject = f"Interview reminder: {drive.title}"
        html_body = f"""
        <p>Hi {student.full_name},</p>
        <p>This is a reminder that your interview for
           <strong>{drive.title}</strong>
           ({drive.company.name if drive.company else ''}) is scheduled for
           <strong>{when}</strong>.</p>
        <p>Good luck!</p>
        """
        ok = send_email(student.user.email, subject, html_body)
        if ok:
            sent.append({"application_id": a.id, "student": student.full_name})

    return {"reminders_sent": len(sent), "details": sent}


@celery.task(name="application.tasks.deadline_reminder")
def deadline_reminder():
    """
    Daily: find approved, active drives whose application deadline falls
    in the next 24 hours, and email every eligible-to-remind student
    (not blacklisted, hasn't already applied) that time is running out.
    This is the "upcoming application deadline" reminder required by the
    project statement — distinct from interview_reminder above.
    """
    window_end = datetime.utcnow() + timedelta(hours=24)
    closing_drives = Drive.query.filter(
        Drive.approval_status == "approved",
        Drive.status == "Active",
        Drive.deadline.isnot(None),
        Drive.deadline >= datetime.utcnow(),
        Drive.deadline <= window_end,
    ).all()

    students = Student.query.filter_by(is_blacklisted=False).all()
    sent = []
    for drive in closing_drives:
        already_applied_ids = {
            a.student_id for a in Application.query.filter_by(drive_id=drive.id).all()
        }
        deadline_str = drive.deadline.strftime("%d %b %Y, %I:%M %p")
        for student in students:
            if student.id in already_applied_ids or not student.user:
                continue
            subject = f"Deadline approaching: {drive.title}"
            html_body = f"""
            <p>Hi {student.full_name},</p>
            <p>The application deadline for <strong>{drive.title}</strong>
               ({drive.company.name if drive.company else ''}) is
               <strong>{deadline_str}</strong>.</p>
            <p>Log in to the Placement Portal to apply before it closes.</p>
            """
            ok = send_email(student.user.email, subject, html_body)
            if ok:
                sent.append({"student_id": student.id, "drive_id": drive.id})

    return {"reminders_sent": len(sent), "details": sent}


@celery.task(name="application.tasks.monthly_placement_report")
def monthly_placement_report():
    """
    Runs on the 1st of each month. Builds an HTML summary of the previous
    ~30 days of placements and emails it to the admin — per the statement's
    "created using HTML and sent via mail" requirement. Also archives a
    copy under instance/reports/ so there's a record even if mail delivery
    fails.
    """
    since = datetime.utcnow() - timedelta(days=30)
    placements = Placement.query.filter(Placement.created_at >= since).all()
    total_applications = Application.query.filter(Application.applied_date >= since).count()
    drives_conducted = Drive.query.filter(Drive.created_at >= since).count()

    rows = "".join(
        f"<tr><td>{p.student.full_name if p.student else 'Unknown'}</td>"
        f"<td>{p.company.name if p.company else 'Unknown'}</td>"
        f"<td>{p.position or ''}</td><td>{p.salary or ''}</td></tr>"
        for p in placements
    )

    html_body = f"""
    <h2>Monthly Placement Report</h2>
    <p>Period: last 30 days &middot; generated {datetime.utcnow().strftime('%d %b %Y')}</p>
    <ul>
      <li>Drives conducted: {drives_conducted}</li>
      <li>Applications received: {total_applications}</li>
      <li>Students placed: {len(placements)}</li>
    </ul>
    <table border="1" cellpadding="6" cellspacing="0">
      <thead><tr><th>Student</th><th>Company</th><th>Position</th><th>Salary</th></tr></thead>
      <tbody>{rows or '<tr><td colspan="4">No placements this period</td></tr>'}</tbody>
    </table>
    """

    reports_dir = os.path.join("instance", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    filename = os.path.join(
        reports_dir, f"placement_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
    )
    with open(filename, "w") as f:
        f.write(html_body)

    admin_email = _get_admin_email()
    mailed = send_email(admin_email, "Monthly Placement Report", html_body) if admin_email else False

    return {"report_file": filename, "placement_count": len(placements), "mailed": mailed}


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
            ["student_id", "company_name", "drive_title", "application_status", "applied_date"]
        )
        for a in applications:
            writer.writerow(
                [
                    a.student_id,
                    a.drive.company.name if a.drive and a.drive.company else "",
                    a.drive.title if a.drive else "",
                    a.status,
                    a.applied_date.isoformat() if a.applied_date else "",
                ]
            )

    return {"status": "completed", "file": filename, "row_count": len(applications)}


