"""
Custom registration routes. Flask-Security-Too's built-in registration
is turned off (SECURITY_REGISTERABLE = False) because admin must never
have a registration route, and student/company need different
post-registration behaviour (student is active immediately, company
stays pending until admin approval).
"""
from flask import Blueprint, jsonify, request
from flask_security import hash_password

from application.database import db
from application.models import Company, Role, Student, User

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or request.form

    email = (data.get("email") or "").strip().lower()
    password = data.get("password")
    role_name = data.get("role")

    if not email or not password or not role_name:
        return jsonify({"error": "email, password and role are required"}), 400

    if role_name not in ("student", "company"):
        return jsonify({"error": "role must be 'student' or 'company'"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    role = Role.query.filter_by(name=role_name).first()
    if role is None:
        return jsonify({"error": f"role '{role_name}' not seeded — run seed_admin() first"}), 500

    user = User(email=email, password=hash_password(password), active=True)
    user.roles.append(role)
    db.session.add(user)
    db.session.flush()  # assigns user.id before we create the profile row

    if role_name == "student":
        db.session.add(
            Student(user_id=user.id, full_name=data.get("full_name", email))
        )
        status_note = "active"
    else:
        db.session.add(
            Company(
                user_id=user.id,
                name=data.get("company_name", email),
                approval_status="pending",
            )
        )
        status_note = "pending approval"

    db.session.commit()

    return (
        jsonify(
            {
                "message": "registered",
                "email": user.email,
                "role": role_name,
                "status": status_note,
            }
        ),
        201,
    )

