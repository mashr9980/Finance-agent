# File: app/services/auth_service.py
"""
Business logic for authentication and authorization
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.database import get_db
from app.models.auth_models import User, UserRole, Permission, UserSession, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, user_roles
from app.schemas import auth_schemas

# OAuth2 token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password"""
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.verify_password(password):
            return None
        return user
    
    @staticmethod
    def create_user_session(db: Session, user_id: uuid.UUID) -> UserSession:
        """Create a new session for a user"""
        expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Create token data
        token_data = {
            "sub": str(user_id),
            "type": "access"
        }
        
        # Generate token
        token = create_access_token(token_data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        
        # Create session record
        session = UserSession(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return session
    
    @staticmethod
    def get_current_user(
        db: Session = Depends(get_db),
        token: str = Depends(oauth2_scheme)
    ) -> User:
        """Get the current authenticated user based on the provided token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # Decode the token
            payload = decode_access_token(token)
            user_id_str = payload.get("sub")
            if user_id_str is None:
                raise credentials_exception
            
            # Convert user_id to UUID
            try:
                user_id = uuid.UUID(user_id_str)
            except ValueError:
                raise credentials_exception
                
        except JWTError:
            raise credentials_exception
            
        # Check if the session is valid and active
        session = db.query(UserSession).filter(
            UserSession.token == token,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            raise credentials_exception
            
        # Get the user
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            raise credentials_exception
            
        return user
    
    @staticmethod
    def get_user_roles(db: Session, user_id: uuid.UUID) -> List[str]:
        """Get roles for a user"""
        results = db.execute(
            user_roles.select().where(user_roles.c.user_id == user_id)
        ).fetchall()
        return [row.role for row in results]
    
    @staticmethod
    def check_permission(
        permission: Permission,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> bool:
        """Check if the current user has a specific permission"""
        if not current_user.has_permission(db, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return True