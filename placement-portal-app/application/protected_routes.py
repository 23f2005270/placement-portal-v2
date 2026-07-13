"""
Throwaway ping routes, one per role, used only to verify RBAC works
end-to-end before real dashboards exist. Safe to delete once Milestones
3-5 build the real protected endpoints.
"""
from flask import Blueprint, jsonify
from flask_login import login_required
from flask_security import current_user

from application.permissions import admin_permission, company_permission, student_permission

protected_bp = Blueprint("protected_bp", __name__)


@protected_bp.route("/api/whoami")
@login_required
def whoami():
    return jsonify(
        {
            "email": current_user.email,
            "roles": [r.name for r in current_user.roles],
        }
    )


@protected_bp.route("/api/admin/ping")
@login_required
@admin_permission.require(http_exception=403)
def admin_ping():
    return jsonify({"message": "admin route OK"})


@protected_bp.route("/api/company/ping")
@login_required
@company_permission.require(http_exception=403)
def company_ping():
    return jsonify({"message": "company route OK"})


@protected_bp.route("/api/student/ping")
@login_required
@student_permission.require(http_exception=403)
def student_ping():
    return jsonify({"message": "student route OK"})

