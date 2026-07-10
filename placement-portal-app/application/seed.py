"""
Seed script: creates the three roles (admin/company/student) and the
single admin user. Admin has no registration route — this is the only
way an admin account ever gets created.

Run with:
    python3 -c "from application.seed import seed_admin; seed_admin()"
"""
from flask_security import hash_password

from app import app, db
from application.models import Role, User

ADMIN_EMAIL = "admin@placementportal.com"
ADMIN_PASSWORD = "AdminPass123!"


def seed_admin():
    with app.app_context():
        db.create_all()

        for role_name, desc in [
            ("admin", "Portal administrator"),
            ("company", "Company/recruiter account"),
            ("student", "Student account"),
        ]:
            if not Role.query.filter_by(name=role_name).first():
                db.session.add(Role(name=role_name, description=desc))
        db.session.commit()

        admin_role = Role.query.filter_by(name="admin").first()

        existing = User.query.filter_by(email=ADMIN_EMAIL).first()
        if existing:
            print(f"Admin already exists: {ADMIN_EMAIL}")
            return

        admin = User(
            email=ADMIN_EMAIL,
            password=hash_password(ADMIN_PASSWORD),
            active=True,
        )
        admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.commit()

        print(f"Admin created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    seed_admin()