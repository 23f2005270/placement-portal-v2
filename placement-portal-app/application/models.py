"""
Data models for Placement Portal Application V2.

User/Role follow the Flask-Security-Too required shape (fs_uniquifier,
roles relationship via a join table). Company/Student are 1:1 profile
tables hanging off User. Drive, Application, Placement carry the actual
placement-workflow data.
"""
import uuid
from datetime import datetime

from flask_security import RoleMixin, UserMixin

from application.database import db


# ---------------------------------------------------------------------
# Auth: Role / User (Flask-Security-Too standard shape)
# ---------------------------------------------------------------------

roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.Integer(), db.ForeignKey("user.id")),
    db.Column("role_id", db.Integer(), db.ForeignKey("role.id")),
)


class Role(db.Model, RoleMixin):
    __tablename__ = "role"

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)  # admin / company / student
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean(), default=True)
    fs_uniquifier = db.Column(
        db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    roles = db.relationship(
        "Role", secondary=roles_users, backref=db.backref("users", lazy="dynamic")
    )

    # 1:1 profile links (nullable — a User is exactly one of these, or neither for admin)
    company_profile = db.relationship(
        "Company", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    student_profile = db.relationship(
        "Student", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def has_role_name(self, name):
        return any(r.name == name for r in self.roles)


# ---------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------

class Company(db.Model):
    __tablename__ = "company"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)

    name = db.Column(db.String(150), nullable=False)
    industry = db.Column(db.String(100))
    location = db.Column(db.String(150))
    hr_contact_name = db.Column(db.String(150))
    hr_contact_phone = db.Column(db.String(20))
    website = db.Column(db.String(255))
    description = db.Column(db.Text)

    # pending / approved / rejected
    approval_status = db.Column(db.String(20), default="pending", nullable=False)
    is_blacklisted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    drives = db.relationship("Drive", backref="company", cascade="all, delete-orphan")


class Student(db.Model):
    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)

    full_name = db.Column(db.String(150), nullable=False)
    contact_number = db.Column(db.String(20))
    branch = db.Column(db.String(100))
    year = db.Column(db.Integer)  # current year of study
    cgpa = db.Column(db.Float)
    skills = db.Column(db.Text)  # comma-separated for simplicity
    experience = db.Column(db.Text)
    resume_path = db.Column(db.String(255))

    is_blacklisted = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship(
        "Application", backref="student", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------
# Placement workflow
# ---------------------------------------------------------------------

class Drive(db.Model):
    __tablename__ = "drive"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    # eligibility criteria
    eligible_branches = db.Column(db.String(255))  # comma-separated, empty = all branches
    min_cgpa = db.Column(db.Float, default=0.0)
    eligible_years = db.Column(db.String(50))  # comma-separated e.g. "3,4"

    skills_required = db.Column(db.Text)
    salary = db.Column(db.String(50))
    benefits = db.Column(db.Text)
    deadline = db.Column(db.DateTime)

    # pending (awaiting admin approval) / approved / rejected
    approval_status = db.Column(db.String(20), default="pending", nullable=False)
    # Active / Closed — only meaningful once approved
    status = db.Column(db.String(20), default="Active", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship(
        "Application", backref="drive", cascade="all, delete-orphan"
    )


class Application(db.Model):
    __tablename__ = "application"
    __table_args__ = (
        db.UniqueConstraint("student_id", "drive_id", name="uq_student_drive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey("drive.id"), nullable=False)

    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    # Applied / Shortlisted / Interview / Offer / Rejected / Placed
    status = db.Column(db.String(20), default="Applied", nullable=False)
    feedback = db.Column(db.Text)
    interview_datetime = db.Column(db.DateTime)


class Placement(db.Model):
    __tablename__ = "placement"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"))

    position = db.Column(db.String(150))
    salary = db.Column(db.String(50))
    joining_date = db.Column(db.DateTime)
    offer_letter_path = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("Student", backref="placements")
    company = db.relationship("Company", backref="placements")