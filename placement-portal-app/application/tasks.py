"""
Background jobs. interview_reminder, deadline_reminder, and
monthly_placement_report are scheduled via Celery Beat (see
celery_config.py). export_csv is user-triggered from a Flask route and
runs async, with its Celery AsyncResult state acting as the completion
signal the frontend polls.

Also includes an async mail task for immediate application-status update
notifications when a company changes a student's application status.
"""
import csv
import os
from datetime import datetime, timedelta

from application.celery_app import celery
from application.mail import send_email
from application.models import Application, Drive, Placement, Role, Student


def _get_admin_email():
    admin_role = Role.query.filter_by(name="admin").first()
    admin_user = admin_role.users.first() if admin_role else None
    return admin_user.email if admin_user else None


def _split_csv(value):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _is_student_eligible_for_drive(student, drive):
    branches = _split_csv(drive.eligible_branches)
    if branches and (student.branch or "").strip() not in branches:
        return False

    if drive.min_cgpa and (student.cgpa is None or student.cgpa < drive.min_cgpa):
        return False

    years = _split_csv(drive.eligible_years)
    if years and str(student.year) not in years:
        return False

    return True


def _runtime_dir():
    path = os.path.join("instance", "runtime")
    os.makedirs(path, exist_ok=True)
    return path


def _seen_keys_path(name):
    return os.path.join(_runtime_dir(), f"{name}.txt")


def _load_seen_keys(name):
    path = _seen_keys_path(name)
    if not os.path.exists(path):
        return set()
    with open(path, "r") as f:
        return {line.strip() for line in f if line.strip()}


def _append_seen_key(name, key):
    path = _seen_keys_path(name)
    with open(path, "a") as f:
        f.write(f"{key}\n")


@celery.task(name="application.tasks.interview_reminder")
def interview_reminder():
    """
    Find applications with an interview scheduled in the next 24 hours
    and email the student, but only once per application + interview slot.
    """
    now = datetime.utcnow()
    window_end = now + timedelta(hours=24)
    seen = _load_seen_keys("interview_reminders")

    upcoming = Application.query.filter(
        Application.status == "Interview",
        Application.interview_datetime.isnot(None),
        Application.interview_datetime >= now,
        Application.interview_datetime <= window_end,
    ).all()

    sent = []
    skipped = []

    for a in upcoming:
        student = a.student
        drive = a.drive

        if not student or not drive or not student.user or not student.user.email:
            skipped.append(
                {
                    "application_id": a.id,
                    "reason": "missing_student_drive_or_email",
                }
            )
            continue

        slot_key = f"{a.id}|{a.interview_datetime.isoformat()}"
        if slot_key in seen:
            skipped.append(
                {
                    "application_id": a.id,
                    "reason": "already_sent_for_this_interview_slot",
                }
            )
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
            _append_seen_key("interview_reminders", slot_key)
            sent.append(
                {
                    "application_id": a.id,
                    "student_id": student.id,
                    "student_email": student.user.email,
                }
            )
        else:
            skipped.append(
                {
                    "application_id": a.id,
                    "reason": "send_email_failed",
                    "student_email": student.user.email,
                }
            )

    return {
        "window_start": now.isoformat(),
        "window_end": window_end.isoformat(),
        "candidates_found": len(upcoming),
        "reminders_sent": len(sent),
        "details": sent,
        "skipped": skipped,
    }


@celery.task(name="application.tasks.deadline_reminder")
def deadline_reminder():
    """
    Find approved, active drives whose application deadline falls in the
    next 24 hours, and email every eligible student who:
    - is not blacklisted
    - is not already placed
    - has not already applied
    - has a valid email

    Each student gets only one reminder per drive.
    """
    now = datetime.utcnow()
    window_end = now + timedelta(hours=24)
    seen = _load_seen_keys("deadline_reminders")

    closing_drives = Drive.query.filter(
        Drive.approval_status == "approved",
        Drive.status == "Active",
        Drive.deadline.isnot(None),
        Drive.deadline >= now,
        Drive.deadline <= window_end,
    ).all()

    students = Student.query.filter_by(is_blacklisted=False).all()

    sent = []
    skipped = []
    drive_debug = []

    for drive in closing_drives:
        already_applied_ids = {
            a.student_id for a in Application.query.filter_by(drive_id=drive.id).all()
        }

        drive_debug.append(
            {
                "drive_id": drive.id,
                "title": drive.title,
                "deadline": drive.deadline.isoformat() if drive.deadline else None,
                "already_applied_ids": list(already_applied_ids),
            }
        )

        deadline_str = drive.deadline.strftime("%d %b %Y, %I:%M %p")

        for student in students:
            reminder_key = f"{drive.id}|{student.id}"

            if reminder_key in seen:
                skipped.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "reason": "already_sent_for_this_drive",
                    }
                )
                continue

            if student.id in already_applied_ids:
                skipped.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "reason": "already_applied",
                    }
                )
                continue

            if student.placements:
                skipped.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "reason": "already_placed",
                    }
                )
                continue

            if not _is_student_eligible_for_drive(student, drive):
                skipped.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "reason": "not_eligible",
                    }
                )
                continue

            if not student.user or not student.user.email:
                skipped.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "reason": "missing_email",
                    }
                )
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
                _append_seen_key("deadline_reminders", reminder_key)
                sent.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "student_email": student.user.email,
                    }
                )
            else:
                skipped.append(
                    {
                        "drive_id": drive.id,
                        "student_id": student.id,
                        "student_email": student.user.email,
                        "reason": "send_email_failed",
                    }
                )

    return {
        "window_start": now.isoformat(),
        "window_end": window_end.isoformat(),
        "closing_drives_found": len(closing_drives),
        "drive_debug": drive_debug,
        "students_considered": len(students),
        "reminders_sent": len(sent),
        "details": sent,
        "skipped": skipped,
    }


@celery.task(name="application.tasks.monthly_placement_report")
def monthly_placement_report():
    """
    Builds an HTML summary of the previous ~30 days of placements and
    emails it to the admin. Archives a copy under instance/reports/.

    Duplicate protection: only one mailed report per generated time-window key.
    """
    since = datetime.utcnow() - timedelta(days=30)
    window_key = since.strftime("%Y-%m-%d")
    seen = _load_seen_keys("monthly_reports")

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
    <p>Period: last 30 days &middot; generated {datetime.utcnow().strftime('%d %b %Y %I:%M %p')}</p>
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
    if not admin_email:
        return {
            "report_file": filename,
            "placement_count": len(placements),
            "mailed": False,
            "reason": "admin_email_missing",
        }

    if window_key in seen:
        return {
            "report_file": filename,
            "placement_count": len(placements),
            "mailed": False,
            "reason": "already_sent_for_this_window",
        }

    mailed = send_email(admin_email, "Monthly Placement Report", html_body)
    if mailed:
        _append_seen_key("monthly_reports", window_key)

    return {
        "report_file": filename,
        "placement_count": len(placements),
        "mailed": mailed,
        "admin_email": admin_email,
    }


@celery.task(name="application.tasks.export_csv", bind=True)
def export_csv(self, student_id):
    """
    User-triggered async CSV export of one student's application history.
    Returns the file path and row count on completion.
    """
    exports_dir = os.path.join("instance", "exports")
    os.makedirs(exports_dir, exist_ok=True)
    filename = os.path.join(exports_dir, f"export_{self.request.id}.csv")

    applications = Application.query.filter_by(student_id=student_id).all()
    student = Student.query.get(student_id)

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["student_id", "company_name", "drive_title", "application_status", "applied_date"]
        )
        for a in applications:
            writer.writerow(
                [
                    student.id if student else student_id,
                    a.drive.company.name if a.drive and a.drive.company else "",
                    a.drive.title if a.drive else "",
                    a.status,
                    a.applied_date.isoformat() if a.applied_date else "",
                ]
            )

    return {"status": "completed", "file": filename, "row_count": len(applications)}


@celery.task(name="application.tasks.send_application_update_email")
def send_application_update_email(application_id, old_status=None, old_interview_datetime=None):
    """
    Async mail task fired when a company updates a student's application.
    Sends an immediate email notification if the status or interview time changed.
    """
    application = Application.query.get(application_id)
    if application is None:
        return {"sent": False, "reason": "application_not_found"}

    student = application.student
    drive = application.drive
    company = drive.company if drive else None

    if not student or not student.user or not student.user.email or not drive:
        return {"sent": False, "reason": "missing_student_or_drive_data"}

    new_status = application.status
    new_interview_datetime = application.interview_datetime

    status_changed = old_status != new_status
    interview_changed = old_interview_datetime != (
        new_interview_datetime.isoformat() if new_interview_datetime else None
    )

    if not status_changed and not interview_changed:
        return {"sent": False, "reason": "no_relevant_change"}

    student_name = student.full_name or "Student"
    company_name = company.name if company else "the company"
    interview_str = (
        new_interview_datetime.strftime("%d %b %Y, %I:%M %p")
        if new_interview_datetime
        else "To be announced"
    )

    if new_status == "Interview":
        subject = f"Interview update: {drive.title} at {company_name}"
        html_body = f"""
        <p>Hi {student_name},</p>
        <p>Your application for <strong>{drive.title}</strong> at
        <strong>{company_name}</strong> has been updated to
        <strong>Interview</strong>.</p>
        <p><strong>Interview time:</strong> {interview_str}</p>
        <p>Please log in to the Placement Portal for the latest details.</p>
        """
    elif new_status == "Offer":
        subject = f"Offer update: {drive.title} at {company_name}"
        html_body = f"""
        <p>Hi {student_name},</p>
        <p>Good news — your application for <strong>{drive.title}</strong> at
        <strong>{company_name}</strong> has been updated to
        <strong>Offer</strong>.</p>
        <p>Please log in to the Placement Portal to review the latest status.</p>
        """
    elif new_status == "Placed":
        subject = f"Placement confirmed: {drive.title} at {company_name}"
        html_body = f"""
        <p>Hi {student_name},</p>
        <p>Congratulations — your application for <strong>{drive.title}</strong> at
        <strong>{company_name}</strong> has been updated to
        <strong>Placed</strong>.</p>
        <p>Please log in to the Placement Portal to view your placement record.</p>
        """
    elif new_status == "Rejected":
        subject = f"Application update: {drive.title} at {company_name}"
        html_body = f"""
        <p>Hi {student_name},</p>
        <p>Your application for <strong>{drive.title}</strong> at
        <strong>{company_name}</strong> has been updated to
        <strong>Rejected</strong>.</p>
        <p>Please log in to the Placement Portal for more details.</p>
        """
    elif new_status == "Shortlisted":
        subject = f"Shortlisted: {drive.title} at {company_name}"
        html_body = f"""
        <p>Hi {student_name},</p>
        <p>Your application for <strong>{drive.title}</strong> at
        <strong>{company_name}</strong> has been updated to
        <strong>Shortlisted</strong>.</p>
        <p>Please log in to the Placement Portal for the latest updates.</p>
        """
    else:
        subject = f"Application status updated: {drive.title} at {company_name}"
        html_body = f"""
        <p>Hi {student_name},</p>
        <p>Your application for <strong>{drive.title}</strong> at
        <strong>{company_name}</strong> has been updated to
        <strong>{new_status}</strong>.</p>
        <p>Please log in to the Placement Portal for more details.</p>
        """

    mailed = send_email(student.user.email, subject, html_body)
    return {
        "sent": mailed,
        "application_id": application.id,
        "student_email": student.user.email,
        "new_status": new_status,
    }