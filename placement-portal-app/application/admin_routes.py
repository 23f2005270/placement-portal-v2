"""
Admin API, built with Flask-RESTful Resource classes per the project's
API-layer convention. Every resource is gated by admin_required, which
stacks login_required (session check) with admin_permission.require()
(RBAC check via Flask-Principal).
"""
from flask import request
from flask_login import login_required
from flask_restful import Api, Resource

from application.database import db
from application.models import Application, Company, Drive, Student
from application.permissions import admin_permission
from flask_cache import cache, invalidate_cache


def admin_required(method):
    """Compose login_required + admin RoleNeed check into one decorator."""
    return login_required(admin_permission.require(http_exception=403)(method))


class AdminStats(Resource):
    method_decorators = [admin_required]

    def get(self):
        return {
            "students": Student.query.count(),
            "companies": Company.query.count(),
            "drives": Drive.query.count(),
            "applications": Application.query.count(),
        }


class AdminCompanyList(Resource):
    method_decorators = [admin_required]

    @cache.cached(timeout=60, query_string=True, key_prefix="admin_companies")
    def get(self):
        q = request.args.get("q", "").strip()
        status = request.args.get("status")  # pending / approved / rejected

        query = Company.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Company.name.ilike(like)) | (Company.industry.ilike(like))
            )
        if status:
            query = query.filter_by(approval_status=status)

        return [
            {
                "id": c.id,
                "name": c.name,
                "industry": c.industry,
                "location": c.location,
                "approval_status": c.approval_status,
                "is_blacklisted": c.is_blacklisted,
            }
            for c in query.order_by(Company.created_at.desc()).all()
        ]


class AdminCompanyDetail(Resource):
    method_decorators = [admin_required]

    def patch(self, company_id):
        company = Company.query.get_or_404(company_id)
        data = request.get_json(silent=True) or {}

        if "approval_status" in data:
            if data["approval_status"] not in ("pending", "approved", "rejected"):
                return {"error": "invalid approval_status"}, 400
            company.approval_status = data["approval_status"]

        if "is_blacklisted" in data:
            company.is_blacklisted = bool(data["is_blacklisted"])

        db.session.commit()
        invalidate_cache()
        return {
            "id": company.id,
            "name": company.name,
            "approval_status": company.approval_status,
            "is_blacklisted": company.is_blacklisted,
        }


class AdminDriveList(Resource):
    method_decorators = [admin_required]

    def get(self):
        status = request.args.get("status")
        query = Drive.query
        if status:
            query = query.filter_by(approval_status=status)

        return [
            {
                "id": d.id,
                "title": d.title,
                "company_id": d.company_id,
                "company_name": d.company.name if d.company else None,
                "approval_status": d.approval_status,
                "status": d.status,
                "deadline": d.deadline.isoformat() if d.deadline else None,
            }
            for d in query.order_by(Drive.created_at.desc()).all()
        ]


class AdminDriveDetail(Resource):
    method_decorators = [admin_required]

    def patch(self, drive_id):
        drive = Drive.query.get_or_404(drive_id)
        data = request.get_json(silent=True) or {}

        if "approval_status" in data:
            if data["approval_status"] not in ("pending", "approved", "rejected"):
                return {"error": "invalid approval_status"}, 400
            drive.approval_status = data["approval_status"]

        db.session.commit()
        invalidate_cache()
        return {
            "id": drive.id,
            "title": drive.title,
            "approval_status": drive.approval_status,
        }


class AdminStudentList(Resource):
    method_decorators = [admin_required]

    @cache.cached(timeout=60, query_string=True, key_prefix="admin_students")
    def get(self):
        q = request.args.get("q", "").strip()
        query = Student.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Student.full_name.ilike(like)) | (Student.contact_number.ilike(like))
            )

        return [
            {
                "id": s.id,
                "full_name": s.full_name,
                "branch": s.branch,
                "cgpa": s.cgpa,
                "is_blacklisted": s.is_blacklisted,
            }
            for s in query.order_by(Student.created_at.desc()).all()
        ]


class AdminStudentDetail(Resource):
    method_decorators = [admin_required]

    def patch(self, student_id):
        student = Student.query.get_or_404(student_id)
        data = request.get_json(silent=True) or {}

        if "is_blacklisted" in data:
            student.is_blacklisted = bool(data["is_blacklisted"])

        db.session.commit()
        invalidate_cache()
        return {
            "id": student.id,
            "full_name": student.full_name,
            "is_blacklisted": student.is_blacklisted,
        }


def register_admin_resources(app):
    api = Api(app)
    api.add_resource(AdminStats, "/api/admin/stats")
    api.add_resource(AdminCompanyList, "/api/admin/companies")
    api.add_resource(AdminCompanyDetail, "/api/admin/companies/<int:company_id>")
    api.add_resource(AdminDriveList, "/api/admin/drives")
    api.add_resource(AdminDriveDetail, "/api/admin/drives/<int:drive_id>")
    api.add_resource(AdminStudentList, "/api/admin/students")
    api.add_resource(AdminStudentDetail, "/api/admin/students/<int:student_id>")