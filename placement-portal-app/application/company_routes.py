"""
Company API. All resources require the 'company' role (RBAC via
Flask-Principal). Past the profile endpoint, actions that create or
manage drives require the company to be admin-approved and not
blacklisted — enforced here in code, not just hidden in the UI.
"""
from datetime import datetime

from flask import request
from flask_login import login_required
from flask_restful import Api, Resource
from flask_security import current_user

from application.database import db
from application.models import Application, Drive, Placement
from application.permissions import company_permission
from flask_cache import invalidate_cache

VALID_APPLICATION_STATUSES = (
    "Applied",
    "Shortlisted",
    "Interview",
    "Offer",
    "Rejected",
    "Placed",
)


def company_required(method):
    return login_required(company_permission.require(http_exception=403)(method))


def get_own_company():
    """Returns the Company row for the logged-in company user, or None."""
    return current_user.company_profile


def is_approved(company):
    return (
        company is not None
        and company.approval_status == "approved"
        and not company.is_blacklisted
    )


def _drive_dict(d):
    return {
        "id": d.id,
        "title": d.title,
        "description": d.description,
        "eligible_branches": d.eligible_branches,
        "min_cgpa": d.min_cgpa,
        "eligible_years": d.eligible_years,
        "skills_required": d.skills_required,
        "salary": d.salary,
        "benefits": d.benefits,
        "deadline": d.deadline.isoformat() if d.deadline else None,
        "approval_status": d.approval_status,
        "status": d.status,
        "applicant_count": len(d.applications),
    }


def _application_dict(a):
    student = a.student
    return {
        "id": a.id,
        "student_id": a.student_id,
        "student_name": student.full_name if student else None,
        "branch": student.branch if student else None,
        "cgpa": student.cgpa if student else None,
        "resume_path": student.resume_path if student else None,
        "status": a.status,
        "feedback": a.feedback,
        "applied_date": a.applied_date.isoformat() if a.applied_date else None,
        "interview_datetime": a.interview_datetime.isoformat() if a.interview_datetime else None,
    }


def _get_own_drive_or_none(drive_id, company):
    return Drive.query.filter_by(id=drive_id, company_id=company.id).first()


class CompanyProfile(Resource):
    method_decorators = [company_required]

    def get(self):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404
        return {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "location": company.location,
            "hr_contact_name": company.hr_contact_name,
            "hr_contact_phone": company.hr_contact_phone,
            "website": company.website,
            "description": company.description,
            "approval_status": company.approval_status,
            "is_blacklisted": company.is_blacklisted,
        }

    def patch(self):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404

        data = request.get_json(silent=True) or {}
        for field in (
            "name",
            "industry",
            "location",
            "hr_contact_name",
            "hr_contact_phone",
            "website",
            "description",
        ):
            if field in data:
                setattr(company, field, data[field])

        db.session.commit()
        return {"message": "profile updated"}


class CompanyDriveList(Resource):
    method_decorators = [company_required]

    def get(self):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404

        drives = (
            Drive.query.filter_by(company_id=company.id)
            .order_by(Drive.created_at.desc())
            .all()
        )
        return [_drive_dict(d) for d in drives]

    def post(self):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404
        if not is_approved(company):
            return {"error": "company must be approved by admin before posting drives"}, 403

        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not title:
            return {"error": "title is required"}, 400

        deadline = None
        if data.get("deadline"):
            try:
                deadline = datetime.fromisoformat(data["deadline"])
            except ValueError:
                return {"error": "deadline must be ISO format, e.g. 2026-08-01T23:59:00"}, 400

        drive = Drive(
            company_id=company.id,
            title=title,
            description=data.get("description"),
            eligible_branches=data.get("eligible_branches"),
            min_cgpa=data.get("min_cgpa", 0.0),
            eligible_years=data.get("eligible_years"),
            skills_required=data.get("skills_required"),
            salary=data.get("salary"),
            benefits=data.get("benefits"),
            deadline=deadline,
            approval_status="pending",
            status="Active",
        )
        db.session.add(drive)
        db.session.commit()
        invalidate_cache()
        return _drive_dict(drive), 201


class CompanyDriveDetail(Resource):
    method_decorators = [company_required]

    def patch(self, drive_id):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404

        drive = _get_own_drive_or_none(drive_id, company)
        if drive is None:
            return {"error": "drive not found"}, 404

        data = request.get_json(silent=True) or {}

        if "status" in data:
            if data["status"] not in ("Active", "Closed"):
                return {"error": "status must be 'Active' or 'Closed'"}, 400
            drive.status = data["status"]

        for field in (
            "title",
            "description",
            "eligible_branches",
            "min_cgpa",
            "eligible_years",
            "skills_required",
            "salary",
            "benefits",
        ):
            if field in data:
                setattr(drive, field, data[field])

        db.session.commit()
        invalidate_cache()
        return _drive_dict(drive)


class CompanyDriveApplicants(Resource):
    method_decorators = [company_required]

    def get(self, drive_id):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404

        drive = _get_own_drive_or_none(drive_id, company)
        if drive is None:
            return {"error": "drive not found"}, 404

        apps = (
            Application.query.filter_by(drive_id=drive.id)
            .order_by(Application.applied_date.desc())
            .all()
        )
        return [_application_dict(a) for a in apps]


class CompanyApplicationDetail(Resource):
    method_decorators = [company_required]

    def patch(self, application_id):
        company = get_own_company()
        if company is None:
            return {"error": "no company profile found"}, 404

        application = Application.query.get_or_404(application_id)
        if application.drive.company_id != company.id:
            return {"error": "not your drive"}, 403

        data = request.get_json(silent=True) or {}

        if "status" in data:
            if data["status"] not in VALID_APPLICATION_STATUSES:
                return {"error": f"status must be one of {VALID_APPLICATION_STATUSES}"}, 400
            application.status = data["status"]

            if data["status"] == "Placed":
                existing = Placement.query.filter_by(application_id=application.id).first()
                if not existing:
                    db.session.add(
                        Placement(
                            student_id=application.student_id,
                            company_id=company.id,
                            application_id=application.id,
                            position=application.drive.title,
                            salary=application.drive.salary,
                        )
                    )

        if "feedback" in data:
            application.feedback = data["feedback"]

        if "interview_datetime" in data:
            if data["interview_datetime"]:
                try:
                    application.interview_datetime = datetime.fromisoformat(
                        data["interview_datetime"]
                    )
                except ValueError:
                    return {"error": "interview_datetime must be ISO format"}, 400
            else:
                application.interview_datetime = None

        db.session.commit()
        invalidate_cache()
        return _application_dict(application)


def register_company_resources(app):
    api = Api(app)
    api.add_resource(CompanyProfile, "/api/company/profile")
    api.add_resource(CompanyDriveList, "/api/company/drives")
    api.add_resource(CompanyDriveDetail, "/api/company/drives/<int:drive_id>")
    api.add_resource(
        CompanyDriveApplicants, "/api/company/drives/<int:drive_id>/applicants"
    )
    api.add_resource(
        CompanyApplicationDetail, "/api/company/applications/<int:application_id>"
    )

