# File: app/routers/currencies.py
"""
API routes for managing currencies and exchange rates
"""
import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.currency_models import Currency, ExchangeRate
from app.schemas import currency_schemas
from app.services.currency_service import CurrencyService

router = APIRouter(
    prefix="/currencies",
    tags=["currencies"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=currency_schemas.CurrencyResponse, status_code=status.HTTP_201_CREATED)
def create_currency(currency: currency_schemas.CurrencyCreate, db: Session = Depends(get_db)):
    """Create a new currency"""
    # Check if currency with same code already exists
    existing_currency = db.query(Currency).filter(Currency.code == currency.code).first()
    if existing_currency:
        raise HTTPException(status_code=400, detail="Currency code already exists")
    
    # If this is set as base currency, update any existing base currencies
    if currency.is_base_currency:
        existing_base = db.query(Currency).filter(Currency.is_base_currency == True).first()
        if existing_base:
            existing_base.is_base_currency = False
    
    # Create new currency
    db_currency = Currency(**currency.dict())
    db.add(db_currency)
    
    try:
        db.commit()
        db.refresh(db_currency)
        return db_currency
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

@router.get("/", response_model=List[currency_schemas.CurrencyResponse])
def list_currencies(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get a list of all currencies with optional filtering"""
    query = db.query(Currency)
    
    if is_active is not None:
        query = query.filter(Currency.is_active == is_active)
        
    return query.all()

@router.get("/base", response_model=currency_schemas.CurrencyResponse)
def get_base_currency(db: Session = Depends(get_db)):
    """Get the system's base currency"""
    return CurrencyService.get_base_currency(db)

@router.post("/exchange-rates", response_model=currency_schemas.ExchangeRateResponse, status_code=status.HTTP_201_CREATED)
def create_exchange_rate(rate: currency_schemas.ExchangeRateCreate, db: Session = Depends(get_db)):
    """Create a new exchange rate"""
    # Validate currencies exist
    from_currency = db.query(Currency).filter(Currency.code == rate.from_currency).first()
    if not from_currency:
        raise HTTPException(status_code=404, detail=f"Currency {rate.from_currency} not found")
        
    to_currency = db.query(Currency).filter(Currency.code == rate.to_currency).first()
    if not to_currency:
        raise HTTPException(status_code=404, detail=f"Currency {rate.to_currency} not found")
    
    # Prevent setting rate for same currency
    if rate.from_currency == rate.to_currency:
        raise HTTPException(
            status_code=400, 
            detail="Cannot set exchange rate for the same currency"
        )
    
    # Check for existing rate on the same date
    existing_rate = db.query(ExchangeRate).filter(
        ExchangeRate.from_currency == rate.from_currency,
        ExchangeRate.to_currency == rate.to_currency,
        ExchangeRate.effective_date == rate.effective_date
    ).first()
    
    if existing_rate:
        raise HTTPException(
            status_code=400,
            detail=f"Exchange rate already exists for this currency pair on {rate.effective_date}"
        )
    
    # Create new exchange rate
    db_rate = ExchangeRate(**rate.dict())
    db.add(db_rate)
    
    try:
        db.commit()
        db.refresh(db_rate)
        return db_rate
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

@router.get("/exchange-rates", response_model=List[currency_schemas.ExchangeRateResponse])
def list_exchange_rates(
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get a list of exchange rates with optional filtering"""
    query = db.query(ExchangeRate)
    
    if from_currency:
        query = query.filter(ExchangeRate.from_currency == from_currency)
        
    if to_currency:
        query = query.filter(ExchangeRate.to_currency == to_currency)
        
    if from_date:
        query = query.filter(ExchangeRate.effective_date >= from_date)
        
    if to_date:
        query = query.filter(ExchangeRate.effective_date <= to_date)
        
    return query.order_by(ExchangeRate.effective_date.desc()).all()

@router.post("/convert", response_model=currency_schemas.ConversionResponse)
def convert_amount(
    conversion: currency_schemas.ConversionRequest,
    db: Session = Depends(get_db)
):
    """Convert an amount from one currency to another"""
    try:
        return CurrencyService.convert_amount(
            db,
            conversion.amount,
            conversion.from_currency,
            conversion.to_currency,
            conversion.conversion_date
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")