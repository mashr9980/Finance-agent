# File: app/schemas/ap_schemas.py
"""
Pydantic models for Accounts Payable module
"""
import uuid
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, validator

from app.models.ap_models import VendorStatus, APInvoiceStatus, APPaymentMethod, APPaymentStatus

# Vendor schemas
class VendorBase(BaseModel):
    code: str
    name: str
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: VendorStatus = VendorStatus.ACTIVE
    payment_terms: int = 30
    currency_code: str = "SAR"
    account_id: Optional[uuid.UUID] = None

class VendorCreate(VendorBase):
    pass

class VendorUpdate(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    status: Optional[VendorStatus] = None
    payment_terms: Optional[int] = None
    currency_code: Optional[str] = None
    account_id: Optional[uuid.UUID] = None

class VendorResponse(VendorBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# AP Invoice schemas
class APInvoiceItemBase(BaseModel):
    description: str
    quantity: Decimal = Decimal("1.00")
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0.00")
    account_id: uuid.UUID
    
    @validator("quantity", "unit_price", "tax_rate")
    def validate_numeric(cls, v):
        return v.quantize(Decimal("0.01"))

class APInvoiceItemCreate(APInvoiceItemBase):
    pass

class APInvoiceItemResponse(APInvoiceItemBase):
    id: uuid.UUID
    invoice_id: uuid.UUID
    tax_amount: Decimal
    total_amount: Decimal
    
    class Config:
        from_attributes = True

class APInvoiceBase(BaseModel):
    vendor_id: uuid.UUID
    vendor_invoice_number: Optional[str] = None
    issue_date: date
    due_date: date
    description: Optional[str] = None
    currency_code: str = "SAR"

class APInvoiceCreate(APInvoiceBase):
    items: List[APInvoiceItemCreate]

class APInvoiceResponse(APInvoiceBase):
    id: uuid.UUID
    invoice_number: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    status: APInvoiceStatus
    journal_entry_id: Optional[uuid.UUID] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    items: List[APInvoiceItemResponse]
    
    class Config:
        from_attributes = True

# AP Payment schemas
class APInvoicePaymentBase(BaseModel):
    invoice_id: uuid.UUID
    amount_applied: Decimal
    
    @validator("amount_applied")
    def validate_amount(cls, v):
        return v.quantize(Decimal("0.01"))

class APInvoicePaymentCreate(APInvoicePaymentBase):
    pass

class APInvoicePaymentResponse(APInvoicePaymentBase):
    id: uuid.UUID
    payment_id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class APPaymentBase(BaseModel):
    vendor_id: uuid.UUID
    payment_date: date
    amount: Decimal
    payment_method: APPaymentMethod
    reference: Optional[str] = None
    description: Optional[str] = None
    currency_code: str = "SAR"
    bank_account_id: uuid.UUID
    
    @validator("amount")
    def validate_amount(cls, v):
        return v.quantize(Decimal("0.01"))

class APPaymentCreate(APPaymentBase):
    invoice_payments: List[APInvoicePaymentCreate]

class APPaymentResponse(APPaymentBase):
    id: uuid.UUID
    payment_number: str
    status: APPaymentStatus
    journal_entry_id: Optional[uuid.UUID] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    invoice_payments: List[APInvoicePaymentResponse]
    
    class Config:
        from_attributes = True

# Aging Report schema
class APAgingBucket(BaseModel):
    range_start: int
    range_end: Optional[int] = None
    amount: Decimal

class APVendorAging(BaseModel):
    vendor_id: uuid.UUID
    vendor_code: str
    vendor_name: str
    total_outstanding: Decimal
    buckets: List[APAgingBucket]

class APAgingReport(BaseModel):
    as_of_date: date
    vendors: List[APVendorAging]
    total_amount: Decimal
    bucket_totals: List[APAgingBucket]