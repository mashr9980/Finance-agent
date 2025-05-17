# File: app/schemas/ar_schemas.py
"""
Pydantic models for Accounts Receivable module
"""
import uuid
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, validator

from app.models.ar_models import CustomerStatus, ARInvoiceStatus, ARPaymentMethod, ARPaymentStatus

# Customer schemas
class CustomerBase(BaseModel):
    code: str
    name: str
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: CustomerStatus = CustomerStatus.ACTIVE
    payment_terms: int = 30
    credit_limit: Decimal = Decimal("0.00")
    currency_code: str = "SAR"
    account_id: Optional[uuid.UUID] = None
    
    @validator("credit_limit")
    def validate_credit_limit(cls, v):
        return v.quantize(Decimal("0.01"))

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[CustomerStatus] = None
    payment_terms: Optional[int] = None
    credit_limit: Optional[Decimal] = None
    currency_code: Optional[str] = None
    account_id: Optional[uuid.UUID] = None

class CustomerResponse(CustomerBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# AR Invoice schemas
class ARInvoiceItemBase(BaseModel):
    description: str
    quantity: Decimal = Decimal("1.00")
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0.00")
    account_id: uuid.UUID
    
    @validator("quantity", "unit_price", "tax_rate")
    def validate_numeric(cls, v):
        return v.quantize(Decimal("0.01"))

class ARInvoiceItemCreate(ARInvoiceItemBase):
    pass

class ARInvoiceItemResponse(ARInvoiceItemBase):
    id: uuid.UUID
    invoice_id: uuid.UUID
    tax_amount: Decimal
    total_amount: Decimal
    
    class Config:
        from_attributes = True

class ARInvoiceBase(BaseModel):
    customer_id: uuid.UUID
    issue_date: date
    due_date: date
    description: Optional[str] = None
    currency_code: str = "SAR"

class ARInvoiceCreate(ARInvoiceBase):
    items: List[ARInvoiceItemCreate]

class ARInvoiceResponse(ARInvoiceBase):
    id: uuid.UUID
    invoice_number: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    status: ARInvoiceStatus
    journal_entry_id: Optional[uuid.UUID] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    items: List[ARInvoiceItemResponse]
    
    class Config:
        from_attributes = True

# AR Payment schemas
class ARInvoicePaymentBase(BaseModel):
    invoice_id: uuid.UUID
    amount_applied: Decimal
    
    @validator("amount_applied")
    def validate_amount(cls, v):
        return v.quantize(Decimal("0.01"))

class ARInvoicePaymentCreate(ARInvoicePaymentBase):
    pass

class ARInvoicePaymentResponse(ARInvoicePaymentBase):
    id: uuid.UUID
    payment_id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class ARPaymentBase(BaseModel):
    customer_id: uuid.UUID
    payment_date: date
    amount: Decimal
    payment_method: ARPaymentMethod
    reference: Optional[str] = None
    description: Optional[str] = None
    currency_code: str = "SAR"
    bank_account_id: uuid.UUID
    
    @validator("amount")
    def validate_amount(cls, v):
        return v.quantize(Decimal("0.01"))

class ARPaymentCreate(ARPaymentBase):
    invoice_payments: List[ARInvoicePaymentCreate]

class ARPaymentResponse(ARPaymentBase):
    id: uuid.UUID
    payment_number: str
    status: ARPaymentStatus
    journal_entry_id: Optional[uuid.UUID] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    invoice_payments: List[ARInvoicePaymentResponse]
    
    class Config:
        from_attributes = True

# Aging Report schema
class ARAgingBucket(BaseModel):
    range_start: int
    range_end: Optional[int] = None
    amount: Decimal

class ARCustomerAging(BaseModel):
    customer_id: uuid.UUID
    customer_code: str
    customer_name: str
    total_outstanding: Decimal
    buckets: List[ARAgingBucket]

class ARAgingReport(BaseModel):
    as_of_date: date
    customers: List[ARCustomerAging]
    total_amount: Decimal
    bucket_totals: List[ARAgingBucket]