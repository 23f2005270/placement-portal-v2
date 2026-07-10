from application import db
from datetime import datetime
from enum import Enum

class UserRole(Enum):
    ADMIN = 'admin'
    COMPANY = 'company'
    STUDENT = 'student'

class ApprovalStatus(Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class DriveStatus(Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    CLOSED = 'closed'

class ApplicationStatus(Enum):
    APPLIED = 'applied'
    SHORTLISTED = 'shortlisted'
    INTERVIEW = 'interview'
    OFFER = 'offer'
    REJECTED = 'rejected'
    PLACED = 'placed'

# ============ USER MODEL ============
class User(db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'company', 'student'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    company = db.relationship('Company', uselist=False, back_populates='user', cascade='all, delete-orphan')
    student = db.relationship('Student', uselist=False, back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

# ============ COMPANY MODEL ============
class Company(db.Model):
    __tablename__ = 'company'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    industry = db.Column(db.String(255))
    location = db.Column(db.String(255))
    website = db.Column(db.String(255))
    hr_contact_name = db.Column(db.String(255))
    hr_contact_email = db.Column(db.String(255))
    hr_contact_phone = db.Column(db.String(20))
    description = db.Column(db.Text)
    approval_status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    is_blacklisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='company')
    job_positions = db.relationship('JobPosition', back_populates='company', cascade='all, delete-orphan')
    placements = db.relationship('Placement', back_populates='company', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Company {self.name} ({self.approval_status})>'

# ============ STUDENT MODEL ============
class Student(db.Model):
    __tablename__ = 'student'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    student_id = db.Column(db.String(50), unique=True, index=True)  # Roll number or ID
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    branch = db.Column(db.String(100))  # CSE, ECE, ME, etc.
    batch_year = db.Column(db.Integer)  # 2022, 2023, etc.
    cgpa = db.Column(db.Float, default=0.0)
    resume_path = db.Column(db.String(255))  # path to uploaded resume
    is_blacklisted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='student')
    applications = db.relationship('Application', back_populates='student', cascade='all, delete-orphan')
    placements = db.relationship('Placement', back_populates='student', cascade='all, delete-orphan')
    experiences = db.relationship('Experience', back_populates='student', cascade='all, delete-orphan')
    skills = db.relationship('Skill', secondary='student_skill', back_populates='students')
    
    def __repr__(self):
        return f'<Student {self.student_id} ({self.first_name} {self.last_name})>'

# ============ EXPERIENCE MODEL ============
class Experience(db.Model):
    __tablename__ = 'experience'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    company_name = db.Column(db.String(255))
    position = db.Column(db.String(255))
    duration_months = db.Column(db.Integer)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('Student', back_populates='experiences')
    
    def __repr__(self):
        return f'<Experience {self.position} at {self.company_name}>'

# ============ SKILL MODEL ============
class Skill(db.Model):
    __tablename__ = 'skill'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    students = db.relationship('Student', secondary='student_skill', back_populates='skills')
    job_positions = db.relationship('JobPosition', secondary='position_skill', back_populates='skills')
    
    def __repr__(self):
        return f'<Skill {self.name}>'

# ============ STUDENT-SKILL ASSOCIATION ============
student_skill = db.Table(
    'student_skill',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skill.id'), primary_key=True)
)

# ============ JOB POSITION / DRIVE MODEL ============
class JobPosition(db.Model):
    __tablename__ = 'job_position'
    
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    salary = db.Column(db.Float)
    benefits = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, active, closed
    approval_status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    
    # Eligibility Criteria
    min_cgpa = db.Column(db.Float, default=0.0)
    eligible_branches = db.Column(db.String(255))  # comma-separated: 'CSE,ECE,ME'
    eligible_batch_years = db.Column(db.String(255))  # comma-separated: '2022,2023'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = db.relationship('Company', back_populates='job_positions')
    applications = db.relationship('Application', back_populates='job_position', cascade='all, delete-orphan')
    placements = db.relationship('Placement', back_populates='job_position', cascade='all, delete-orphan')
    skills = db.relationship('Skill', secondary='position_skill', back_populates='job_positions')
    interviews = db.relationship('Interview', back_populates='job_position', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<JobPosition {self.title} at {self.company.name}>'

# ============ POSITION-SKILL ASSOCIATION ============
position_skill = db.Table(
    'position_skill',
    db.Column('position_id', db.Integer, db.ForeignKey('job_position.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('skill.id'), primary_key=True)
)

# ============ APPLICATION MODEL ============
class Application(db.Model):
    __tablename__ = 'application'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    job_position_id = db.Column(db.Integer, db.ForeignKey('job_position.id'), nullable=False)
    status = db.Column(db.String(20), default='applied')  # applied, shortlisted, interview, offer, rejected, placed
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    feedback = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', back_populates='applications')
    job_position = db.relationship('JobPosition', back_populates='applications')
    
    # Unique constraint: one student can't apply twice to same position
    __table_args__ = (db.UniqueConstraint('student_id', 'job_position_id', name='uq_student_position'),)
    
    def __repr__(self):
        return f'<Application {self.student_id} → {self.job_position_id} ({self.status})>'

# ============ INTERVIEW MODEL ============
class Interview(db.Model):
    __tablename__ = 'interview'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    job_position_id = db.Column(db.Integer, db.ForeignKey('job_position.id'), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    interview_type = db.Column(db.String(100))  # phone, video, in-person, etc.
    location = db.Column(db.String(255))  # for in-person
    interviewer_name = db.Column(db.String(255))
    interviewer_email = db.Column(db.String(255))
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    application = db.relationship('Application')
    job_position = db.relationship('JobPosition', back_populates='interviews')
    
    def __repr__(self):
        return f'<Interview for Application {self.application_id}>'

# ============ PLACEMENT MODEL ============
class Placement(db.Model):
    __tablename__ = 'placement'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    job_position_id = db.Column(db.Integer, db.ForeignKey('job_position.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), unique=True)
    position_title = db.Column(db.String(255))
    salary = db.Column(db.Float)
    joining_date = db.Column(db.Date)
    offer_letter_path = db.Column(db.String(255))
    placement_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', back_populates='placements')
    company = db.relationship('Company', back_populates='placements')
    job_position = db.relationship('JobPosition', back_populates='placements')
    
    def __repr__(self):
        return f'<Placement {self.student_id} → {self.company_id}>'