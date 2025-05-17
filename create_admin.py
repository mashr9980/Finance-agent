# create_admin.py
"""
Script to create an initial admin user and set up permissions
"""
from sqlalchemy import text
from app.database import SessionLocal
from app.models.auth_models import User, UserRole
from app.default_permissions import setup_default_permissions
import uuid

def main():
    db = SessionLocal()
    
    # Set up default permissions
    setup_default_permissions(db)
    
    # Create admin user - use raw SQL to avoid ORM issues
    admin_username = "admin"
    admin_email = "admin@example.com"
    
    # Check if admin already exists
    existing_user = db.execute(
        text("SELECT id FROM users WHERE username = :username"),
        {"username": admin_username}
    ).first()
    
    if existing_user:
        print(f"Admin user already exists with ID: {existing_user[0]}")
        return
    
    # Generate a UUID for the user
    user_id = uuid.uuid4()
    
    # Create password hash
    hashed_password = User.get_password_hash("your_secure_password")
    
    # Insert the user directly with SQL
    db.execute(
        text("""
            INSERT INTO users 
            (id, username, email, full_name, hashed_password, is_active, created_at, updated_at) 
            VALUES 
            (:id, :username, :email, :full_name, :hashed_password, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": user_id,
            "username": admin_username,
            "email": admin_email,
            "full_name": "System Administrator",
            "hashed_password": hashed_password,
            "is_active": True
        }
    )
    
    # Add admin role
    db.execute(
        text("""
            INSERT INTO user_roles (user_id, role) 
            VALUES (:user_id, :role)
        """),
        {
            "user_id": user_id,
            "role": UserRole.ADMIN.value
        }
    )
    
    db.commit()
    print(f"Admin user created with ID: {user_id}")

if __name__ == "__main__":
    main()