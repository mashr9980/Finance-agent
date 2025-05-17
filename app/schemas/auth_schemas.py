# File: app/schemas/auth_schemas.py
"""
Pydantic models for authentication and authorization
"""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, validator

from app.models.auth_models import UserRole, Permission

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: List[UserRole] = []
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[uuid.UUID] = None

class RolePermissions(BaseModel):
    role: UserRole
    permissions: List[Permission]

class AddUserRole(BaseModel):
    role: UserRole