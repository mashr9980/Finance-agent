# File: app/models/auth_models.py
"""
SQLAlchemy models for authentication and authorization
"""
import uuid
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Enum, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from passlib.context import CryptContext
from jose import jwt
from typing import Optional, List

from app.database import Base

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings - in production, these should be in environment variables
SECRET_KEY = "your-secret-key-should-be-in-env-variables"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class UserRole(str, PyEnum):
    ADMIN = "ADMIN"
    ACCOUNTANT = "ACCOUNTANT"
    AP_CLERK = "AP_CLERK"
    AR_CLERK = "AR_CLERK"
    MANAGER = "MANAGER"
    READONLY = "READONLY"

class Permission(str, PyEnum):
    # General Ledger permissions
    GL_VIEW = "GL_VIEW"
    GL_MANAGE = "GL_MANAGE"
    GL_POST = "GL_POST"
    GL_CLOSE = "GL_CLOSE"
    
    # Accounts Payable permissions
    AP_VIEW = "AP_VIEW"
    AP_MANAGE = "AP_MANAGE"
    AP_APPROVE = "AP_APPROVE"
    AP_PAY = "AP_PAY"
    
    # Accounts Receivable permissions
    AR_VIEW = "AR_VIEW"
    AR_MANAGE = "AR_MANAGE"
    AR_APPROVE = "AR_APPROVE"
    
    # Financial Statements permissions
    FS_VIEW = "FS_VIEW"
    FS_MANAGE = "FS_MANAGE"
    
    # System Admin permissions
    SYSTEM_CONFIG = "SYSTEM_CONFIG"
    USER_MANAGE = "USER_MANAGE"

# Many-to-many relationship table for users and roles
user_roles = Table('user_roles', Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('role', Enum(UserRole), primary_key=True)
)

# Many-to-many relationship table for roles and permissions
role_permissions = Table('role_permissions', Base.metadata,
    Column('role', Enum(UserRole), primary_key=True),
    Column('permission', Enum(Permission), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # IMPORTANT: Remove the roles relationship - we'll access roles directly through queries
    # roles = relationship("UserRole", secondary=user_roles, backref="users")
    
    def verify_password(self, plain_password: str) -> bool:
        """Verify a plain password against the hashed password"""
        return pwd_context.verify(plain_password, self.hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password for storing"""
        return pwd_context.hash(password)
    
    def get_roles(self, db) -> List[str]:
        """Get user roles through direct query"""
        result = db.execute(
            user_roles.select().where(user_roles.c.user_id == self.id)
        ).fetchall()
        return [row.role for row in result]
    
    def has_permission(self, db, permission: Permission) -> bool:
        """Check if the user has a specific permission through any of their roles"""
        user_role_list = self.get_roles(db)
        
        for role in user_role_list:
            perm = db.execute(
                role_permissions.select().where(
                    role_permissions.c.role == role,
                    role_permissions.c.permission == permission
                )
            ).first()
            
            if perm:
                return True
        return False

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

# Authentication helper functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decode a JWT access token"""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])