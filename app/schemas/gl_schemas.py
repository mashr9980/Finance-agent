# File: app/schemas/gl_schemas.py
"""
Pydantic models for request and response validation
"""
import uuid
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator

from app.models.gl_models import AccountType, JournalEntryStatus

# Account schemas
class AccountBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    account_type: AccountType
    parent_id: Optional[uuid.UUID] = None
    currency_code: str = "SAR"
    is_active: bool = True

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

class AccountResponse(AccountBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

# Journal Entry schemas
class JournalEntryLineBase(BaseModel):
    account_id: uuid.UUID
    description: Optional[str] = None
    debit_amount: Decimal = Decimal("0.00")
    credit_amount: Decimal = Decimal("0.00")
    
    @validator("debit_amount", "credit_amount")
    def validate_amounts(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"))
    
    @validator("debit_amount")
    def validate_debit(cls, v, values):
        if v > 0 and "credit_amount" in values and values["credit_amount"] > 0:
            raise ValueError("An entry cannot have both debit and credit amounts")
        return v
    
    @validator("credit_amount")
    def validate_credit(cls, v, values):
        if v > 0 and "debit_amount" in values and values["debit_amount"] > 0:
            raise ValueError("An entry cannot have both debit and credit amounts")
        return v

class JournalEntryLineCreate(JournalEntryLineBase):
    pass

class JournalEntryLineResponse(JournalEntryLineBase):
    id: uuid.UUID
    journal_entry_id: uuid.UUID
    
    class Config:
        orm_mode = True

class JournalEntryBase(BaseModel):
    entry_date: datetime
    description: Optional[str] = None
    reference: Optional[str] = None
    is_recurring: bool = False

class JournalEntryCreate(JournalEntryBase):
    lines: List[JournalEntryLineCreate]

class JournalEntryResponse(JournalEntryBase):
    id: uuid.UUID
    entry_number: str
    status: JournalEntryStatus
    created_by: str
    created_at: datetime
    posted_at: Optional[datetime] = None
    reversed_at: Optional[datetime] = None
    lines: List[JournalEntryLineResponse]
    
    class Config:
        orm_mode = True

# Fiscal Period schemas
class FiscalPeriodBase(BaseModel):
    name: str
    start_date: datetime
    end_date: datetime

class FiscalPeriodCreate(FiscalPeriodBase):
    pass

class FiscalPeriodResponse(FiscalPeriodBase):
    id: uuid.UUID
    is_closed: bool
    created_at: datetime
    closed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Trial Balance schemas
class TrialBalanceEntry(BaseModel):
    account_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: AccountType
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal

class TrialBalanceResponse(BaseModel):
    as_of_date: datetime
    entries: List[TrialBalanceEntry]
    total_debits: Decimal
    total_credits: Decimal