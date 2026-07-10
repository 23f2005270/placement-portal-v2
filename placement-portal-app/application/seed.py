from application import create_app, db
from application.models import User, Company, Student
from werkzeug.security import generate_password_hash

def seed_admin():
    """Create the database and seed an admin user."""
    app = create_app()
    
    with app.app_context():
        # Drop all tables and recreate (for fresh start)
        db.drop_all()
        db.create_all()
        
        # Create admin user
        admin_user = User(
            email='admin@placement.local',
            password=generate_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        
        db.session.add(admin_user)
        db.session.commit()
        
        print("✓ Database created successfully")
        print(f"✓ Admin user seeded: admin@placement.local / admin123")
        print(f"✓ Database location: {app.config['SQLALCHEMY_DATABASE_URI']}")

if __name__ == '__main__':
    seed_admin()