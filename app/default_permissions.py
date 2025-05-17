# File: app/default_permissions.py
"""
Default permissions setup for roles
"""
from app.models.auth_models import UserRole, Permission, role_permissions
from sqlalchemy.orm import Session

def setup_default_permissions(db: Session):
    """Setup default permissions for roles"""
    # Clear existing permissions - use raw SQL to avoid ORM issues
    db.execute(role_permissions.delete())
    
    # Define default permissions by role
    role_perms = {
        UserRole.ADMIN: [p for p in Permission],  # All permissions
        
        UserRole.ACCOUNTANT: [
            Permission.GL_VIEW, Permission.GL_MANAGE, Permission.GL_POST,
            Permission.AP_VIEW, Permission.AP_MANAGE,
            Permission.AR_VIEW, Permission.AR_MANAGE,
            Permission.FS_VIEW
        ],
        
        UserRole.AP_CLERK: [
            Permission.GL_VIEW,
            Permission.AP_VIEW, Permission.AP_MANAGE
        ],
        
        UserRole.AR_CLERK: [
            Permission.GL_VIEW,
            Permission.AR_VIEW, Permission.AR_MANAGE
        ],
        
        UserRole.MANAGER: [
            Permission.GL_VIEW, 
            Permission.AP_VIEW, Permission.AP_APPROVE,
            Permission.AR_VIEW, Permission.AR_APPROVE,
            Permission.FS_VIEW, Permission.FS_MANAGE
        ],
        
        UserRole.READONLY: [
            Permission.GL_VIEW,
            Permission.AP_VIEW,
            Permission.AR_VIEW,
            Permission.FS_VIEW
        ]
    }
    
    # Insert permissions using direct SQL execution to avoid ORM issues
    try:
        for role, permissions in role_perms.items():
            for permission in permissions:
                db.execute(
                    role_permissions.insert().values(
                        role=role,
                        permission=permission
                    )
                )
        
        db.commit()
        print(f"Successfully set up default permissions for {len(role_perms)} roles")
    except Exception as e:
        db.rollback()
        print(f"Error setting up permissions: {e}")