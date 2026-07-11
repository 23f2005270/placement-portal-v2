"""
Student API. All resources require the 'student' role. Drive browsing
only ever returns admin-approved, Active drives — students never see
pending/rejected/closed drives through this API, regardless of what the
frontend shows. Eligibility (branch/CGPA/year) is validated server-side
before an application is created, not just displayed as a hint.
"""
import io
import os

from flask import Blueprint, Response, request, send_from_directory
from flask_login import login_required
from flask_restful import Api, Resource
from flask_security import current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from application.database import db
from application.models import Application, Drive, Placement, Student
from application.permissions import student_permission
from flask_cache import cache, invalidate_cache

RESUME_UPLOAD_DIR = os.path.join("static", "resumes")
ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}


def student_required(method):
    return login_required(student_permission.require(http_exception=403)(method))


def get_own_student():
    return current_user.student_profile


def _split_csv(value):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def is_eligible(drive, student):
    branches = _split_csv(drive.eligible_branches)
    if branches and (student.branch or "").strip() not in branches:
        return False

    if drive.min_cgpa and (student.cgpa is None or student.cgpa < drive.min_cgpa):
        return False

    years = _split_csv(drive.eligible_years)
    if years and str(student.year) not in years:
        return False

    return True


def _drive_dict(d, student=None):
    result = {
        "id": d.id,
        "title": d.title,
        "description": d.description,
        "company_id": d.company_id,
        "company_name": d.company.name if d.company else None,
        "eligible_branches": d.eligible_branches,
        "min_cgpa": d.min_cgpa,
        "eligible_years": d.eligible_years,
        "skills_required": d.skills_required,
        "salary": d.salary,
        "benefits": d.benefits,
        "deadline": d.deadline.isoformat() if d.deadline else None,
        "status": d.status,
    }
    if student is not None:
        result["eligible"] = is_eligible(d, student)
    return result


def _application_dict(a):
    drive = a.drive
    return {
        "id": a.id,
        "drive_id": a.drive_id,
        "drive_title": drive.title if drive else None,
        "company_name": drive.company.name if drive and drive.company else None,
        "salary": drive.salary if drive else None,
        "status": a.status,
        "feedback": a.feedback,
        "applied_date": a.applied_date.isoformat() if a.applied_date else None,
        "interview_datetime": a.interview_datetime.isoformat() if a.interview_datetime else None,
    }


class StudentProfile(Resource):
    method_decorators = [student_required]

    def get(self):
        student = get_own_student()
        if student is None:
            return {"error": "no student profile found"}, 404
        return {
            "id": student.id,
            "full_name": student.full_name,
            "contact_number": student.contact_number,
            "branch": student.branch,
            "year": student.year,
            "cgpa": student.cgpa,
            "skills": student.skills,
            "experience": student.experience,
            "resume_path": student.resume_path,
            "is_blacklisted": student.is_blacklisted,
        }

    def patch(self):
        student = get_own_student()
        if student is None:
            return {"error": "no student profile found"}, 404

        data = request.get_json(silent=True) or {}
        for field in ("full_name", "contact_number", "branch", "skills", "experience"):
            if field in data:
                setattr(student, field, data[field])

        if "year" in data:
            try:
                student.year = int(data["year"]) if data["year"] is not None else None
            except (TypeError, ValueError):
                return {"error": "year must be an integer"}, 400

        if "cgpa" in data:
            try:
                student.cgpa = float(data["cgpa"]) if data["cgpa"] is not None else None
            except (TypeError, ValueError):
                return {"error": "cgpa must be a number"}, 400

        db.session.commit()
        return {"message": "profile updated"}


def _student_drives_cache_key(*args, **kwargs):
    # Eligibility is student-specific, so the cache key must include the
    # requesting student's id — otherwise one student's cached response
    # (with their eligible:true/false flags) would leak to another
    # student hitting the same URL with the same filters.
    return f"student_drives:{current_user.get_id()}:{request.query_string.decode('utf-8')}"


class StudentDriveList(Resource):
    method_decorators = [student_required]

    @cache.cached(timeout=60, make_cache_key=_student_drives_cache_key)
    def get(self):
        student = get_own_student()
        if student is None:
            return {"error": "no student profile found"}, 404

        query = Drive.query.filter_by(approval_status="approved", status="Active")

        company_q = request.args.get("company", "").strip()
        title_q = request.args.get("title", "").strip()
        skills_q = request.args.get("skills", "").strip()
        only_eligible = request.args.get("only_eligible", "").lower() == "true"

        drives = query.order_by(Drive.created_at.desc()).all()

        if company_q:
            drives = [d for d in drives if d.company and company_q.lower() in d.company.name.lower()]
        if title_q:
            drives = [d for d in drives if title_q.lower() in (d.title or "").lower()]
        if skills_q:
            drives = [d for d in drives if skills_q.lower() in (d.skills_required or "").lower()]

        results = [_drive_dict(d, student) for d in drives]
        if only_eligible:
            results = [r for r in results if r["eligible"]]

        return results


class StudentApplicationList(Resource):
    method_decorators = [student_required]

    def get(self):
        student = get_own_student()
        if student is None:
            return {"error": "no student profile found"}, 404

        apps = (
            Application.query.filter_by(student_id=student.id)
            .order_by(Application.applied_date.desc())
            .all()
        )
        return [_application_dict(a) for a in apps]

    def post(self):
        student = get_own_student()
        if student is None:
            return {"error": "no student profile found"}, 404
        if student.is_blacklisted:
            return {"error": "your account has been blacklisted and cannot apply to drives"}, 403

        data = request.get_json(silent=True) or {}
        drive_id = data.get("drive_id")
        if not drive_id:
            return {"error": "drive_id is required"}, 400

        drive = Drive.query.get(drive_id)
        if drive is None or drive.approval_status != "approved" or drive.status != "Active":
            return {"error": "this drive is not open for applications"}, 404

        if not is_eligible(drive, student):
            return {"error": "you do not meet the eligibility criteria for this drive"}, 403

        existing = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
        if existing:
            return {"error": "you have already applied to this drive"}, 409

        application = Application(student_id=student.id, drive_id=drive.id, status="Applied")
        db.session.add(application)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "you have already applied to this drive"}, 409

        invalidate_cache()
        return _application_dict(application), 201


class StudentPlacementList(Resource):
    method_decorators = [student_required]

    def get(self):
        student = get_own_student()
        if student is None:
            return {"error": "no student profile found"}, 404

        placements = Placement.query.filter_by(student_id=student.id).all()
        return [
            {
                "id": p.id,
                "company_name": p.company.name if p.company else None,
                "position": p.position,
                "salary": p.salary,
                "joining_date": p.joining_date.isoformat() if p.joining_date else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in placements
        ]


def register_student_resources(app):
    api = Api(app)
    api.add_resource(StudentProfile, "/api/student/profile")
    api.add_resource(StudentDriveList, "/api/student/drives")
    api.add_resource(StudentApplicationList, "/api/student/applications")
    api.add_resource(StudentPlacementList, "/api/student/placements")


# ---------------------------------------------------------------------
# Plain Flask routes (file upload + file download don't fit Flask-RESTful's
# JSON-in/JSON-out model as cleanly, so these live on a small blueprint).
# ---------------------------------------------------------------------

student_files_bp = Blueprint("student_files_bp", __name__)


@student_files_bp.route("/api/student/profile/resume", methods=["POST"])
@student_required
def upload_resume():
    student = get_own_student()
    if student is None:
        return {"error": "no student profile found"}, 404

    if "resume" not in request.files:
        return {"error": "no file part named 'resume'"}, 400

    file = request.files["resume"]
    if file.filename == "":
        return {"error": "no file selected"}, 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        return {"error": f"file type must be one of {sorted(ALLOWED_RESUME_EXTENSIONS)}"}, 400

    os.makedirs(RESUME_UPLOAD_DIR, exist_ok=True)
    filename = secure_filename(f"student_{student.id}_resume.{ext}")
    filepath = os.path.join(RESUME_UPLOAD_DIR, filename)
    file.save(filepath)

    student.resume_path = filepath
    db.session.commit()

    return {"message": "resume uploaded", "resume_path": filepath}


@student_files_bp.route("/api/student/placements/<int:placement_id>/offer-letter")
@student_required
def download_offer_letter(placement_id):
    student = get_own_student()
    if student is None:
        return {"error": "no student profile found"}, 404

    placement = Placement.query.filter_by(id=placement_id, student_id=student.id).first()
    if placement is None:
        return {"error": "placement not found"}, 404

    company_name = placement.company.name if placement.company else "the company"
    text = (
        f"OFFER / PLACEMENT CONFIRMATION\n"
        f"{'-' * 40}\n\n"
        f"This confirms that {student.full_name} has been placed with "
        f"{company_name}.\n\n"
        f"Position: {placement.position or '-'}\n"
        f"Salary: {placement.salary or '-'}\n"
        f"Confirmed on: {placement.created_at.strftime('%Y-%m-%d') if placement.created_at else '-'}\n\n"
        f"Issued by Placement Portal V2.\n"
    )

    buffer = io.BytesIO(text.encode("utf-8"))
    return Response(
        buffer.getvalue(),
        mimetype="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=offer_letter_{placement.id}.txt"
        },
    )