# File: app/routers/fiscal_periods.py
"""
API routes for managing fiscal periods
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_db
from app.models.auth_models import Permission, User
from app.models.gl_models import FiscalPeriod
from app.schemas import gl_schemas
from app.services.auth_service import AuthService
from app.services.fiscal_service import FiscalService

router = APIRouter(
    prefix="/fiscal-periods",
    tags=["fiscal periods"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=gl_schemas.FiscalPeriodResponse, status_code=status.HTTP_201_CREATED)
def create_fiscal_period(
    fiscal_period: gl_schemas.FiscalPeriodCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    # Check permissions
    AuthService.check_permission(Permission.GL_MANAGE, current_user, db)
    
    if fiscal_period.start_date >= fiscal_period.end_date:
        raise HTTPException(
            status_code=400, 
            detail="Start date must be before end date"
        )
    
    # Check for overlapping periods
    overlapping = db.query(FiscalPeriod).filter(
        FiscalPeriod.start_date <= fiscal_period.end_date,
        FiscalPeriod.end_date >= fiscal_period.start_date
    ).first()
    
    if overlapping:
        raise HTTPException(
            status_code=400,
            detail=f"Overlapping fiscal period exists: {overlapping.name}"
        )
    
    db_fiscal_period = FiscalPeriod(**fiscal_period.dict())
    db.add(db_fiscal_period)
    db.commit()
    db.refresh(db_fiscal_period)
    return db_fiscal_period

@router.get("/", response_model=List[gl_schemas.FiscalPeriodResponse])
def list_fiscal_periods(
    skip: int = 0, 
    limit: int = 100,
    year: int = None, 
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    # Check permissions
    AuthService.check_permission(Permission.GL_VIEW, current_user, db)
    
    query = db.query(FiscalPeriod)
    
    if year:
        query = query.filter(
            FiscalPeriod.start_date >= date(year, 1, 1),
            FiscalPeriod.end_date <= date(year, 12, 31)
        )
    
    return query.order_by(FiscalPeriod.start_date).offset(skip).limit(limit).all()

@router.get("/current", response_model=gl_schemas.FiscalPeriodResponse)
def get_current_fiscal_period(
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    # Check permissions
    AuthService.check_permission(Permission.GL_VIEW, current_user, db)
    
    return FiscalService.get_current_fiscal_period(db)

@router.post("/{period_id}/close", response_model=gl_schemas.FiscalPeriodResponse)
def close_fiscal_period(
    period_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    # Check permissions
    AuthService.check_permission(Permission.GL_CLOSE, current_user, db)
    
    return FiscalService.close_fiscal_period(db, period_id, current_user.username)

@router.post("/year/{year}/create", response_model=List[gl_schemas.FiscalPeriodResponse])
def create_fiscal_year(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    # Check permissions
    AuthService.check_permission(Permission.GL_MANAGE, current_user, db)
    
    # Validate year
    current_year = datetime.now().year
    if year < 2000 or year > current_year + 5:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between 2000 and {current_year + 5}"
        )
    
    return FiscalService.create_fiscal_year(db, year, current_user.username)

@router.post("/year/{year}/close", status_code=status.HTTP_200_OK)
def close_fiscal_year(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    # Check permissions
    AuthService.check_permission(Permission.GL_CLOSE, current_user, db)
    
    # Validate year
    current_year = datetime.now().year
    if year < 2000 or year > current_year:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid year for closing: {year}"
        )
    
    return FiscalService.close_fiscal_year(db, year, current_user.username)