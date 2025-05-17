# File: app/schemas/currency_schemas.py
"""
Pydantic models for currency-related operations
"""
import uuid
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, validator

class CurrencyBase(BaseModel):
    code: str
    name: str
    symbol: str
    decimal_places: int = 2
    is_base_currency: bool = False
    is_active: bool = True

class CurrencyCreate(CurrencyBase):
    pass

class CurrencyUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    decimal_places: Optional[int] = None
    is_base_currency: Optional[bool] = None
    is_active: Optional[bool] = None

class CurrencyResponse(CurrencyBase):
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ExchangeRateBase(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: date
    
    @validator('rate')
    def validate_rate(cls, v):
        return v.quantize(Decimal('0.000001'))
    
    @validator('from_currency', 'to_currency')
    def validate_currency_codes(cls, v):
        if len(v) != 3:
            raise ValueError('Currency code must be 3 characters')
        return v.upper()

class ExchangeRateCreate(ExchangeRateBase):
    pass

class ExchangeRateResponse(ExchangeRateBase):
    id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class ConversionRequest(BaseModel):
    amount: Decimal
    from_currency: str
    to_currency: str
    conversion_date: Optional[date] = None
    
    @validator('from_currency', 'to_currency')
    def validate_currency_codes(cls, v):
        if len(v) != 3:
            raise ValueError('Currency code must be 3 characters')
        return v.upper()

class ConversionResponse(BaseModel):
    original_amount: Decimal
    from_currency: str
    converted_amount: Decimal
    to_currency: str
    exchange_rate: Decimal
    conversion_date: date