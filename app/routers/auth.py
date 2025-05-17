# File: app/routers/auth.py
"""
API routes for authentication and user management
"""
import uuid
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.auth_models import User, UserRole, Permission, role_permissions, user_roles, ACCESS_TOKEN_EXPIRE_MINUTES
from app.schemas import auth_schemas
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)

@router.post("/token", response_model=auth_schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Authenticate user and create access token"""
    user = AuthService.authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create session
    session = AuthService.create_user_session(db, user.id)
    
    return {
        "access_token": session.token,
        "token_type": "bearer",
        "expires_at": session.expires_at
    }

@router.post("/users", response_model=auth_schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: auth_schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """Create a new user (requires admin privileges)"""
    # Check permissions
    AuthService.check_permission(Permission.USER_MANAGE, current_user, db)
    
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    
    if existing_user:
        if existing_user.username == user.username:
            raise HTTPException(status_code=400, detail="Username already exists")
        else:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create user with hashed password
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=User.get_password_hash(user.password)
    )
    
    db.add(db_user)
    
    try:
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

@router.get("/users", response_model=List[auth_schemas.UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """Get list of users (requires admin privileges)"""
    # Check permissions
    AuthService.check_permission(Permission.USER_MANAGE, current_user, db)
    
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/users/me", response_model=auth_schemas.UserResponse)
def get_current_user_info(
    current_user: User = Depends(AuthService.get_current_user)
):
    """Get current user information"""
    return current_user

@router.post("/users/{user_id}/roles", response_model=auth_schemas.UserResponse)
def add_user_role(
    user_id: uuid.UUID,
    role_data: auth_schemas.AddUserRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """Add a role to a user (requires admin privileges)"""
    # Check permissions
    AuthService.check_permission(Permission.USER_MANAGE, current_user, db)
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Add role to user if they don't already have it
    existing_role = db.query(user_roles).filter(
        user_roles.c.user_id == user_id,
        user_roles.c.role == role_data.role
    ).first()
    
    if not existing_role:
        # Add the role
        db.execute(
            user_roles.insert().values(
                user_id=user_id,
                role=role_data.role
            )
        )
        db.commit()
    
    # Refresh user to get updated roles
    db.refresh(user)
    return user

@router.get("/roles/permissions", response_model=List[auth_schemas.RolePermissions])
def get_role_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """Get all role permissions (requires admin privileges)"""
    # Check permissions
    AuthService.check_permission(Permission.USER_MANAGE, current_user, db)
    
    # Gather role permissions
    result = []
    for role in UserRole:
        permissions = db.query(role_permissions).filter(
            role_permissions.c.role == role
        ).all()
        
        role_perms = auth_schemas.RolePermissions(
            role=role,
            permissions=[p.permission for p in permissions]
        )
        result.append(role_perms)
    
    return result