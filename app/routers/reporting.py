# File: app/routers/reporting.py
"""
API routes for financial reporting
"""
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import gl_schemas
from app.services.gl_service import GLService

from datetime import date
from app.schemas import ap_schemas, ar_schemas
from app.services.ap_service import APService
from app.services.ar_service import ARService

router = APIRouter(
    prefix="/reporting",
    tags=["reporting"],
    responses={404: {"description": "Not found"}},
)

@router.get("/trial-balance", response_model=gl_schemas.TrialBalanceResponse)
def get_trial_balance(
    as_of_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    return GLService.calculate_trial_balance(db, as_of_date)

# AP Aging Report
@router.get("/ap/aging", response_model=ap_schemas.APAgingReport)
def get_ap_aging_report(
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    return APService.generate_aging_report(db, as_of_date)

# AR Aging Report
@router.get("/ar/aging", response_model=ar_schemas.ARAgingReport)
def get_ar_aging_report(
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    return ARService.generate_aging_report(db, as_of_date)