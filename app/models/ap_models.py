# File: app/models/ap_models.py
"""
SQLAlchemy models for the Accounts Payable module
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean, Text, Enum, Date
import sqlalchemy
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.gl_models import Account

class VendorStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    HOLD = "HOLD"
    BLACKLISTED = "BLACKLISTED"

class Vendor(Base):
    __tablename__ = "vendors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    tax_id = Column(String(50), nullable=True)
    contact_name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    status = Column(Enum(VendorStatus), default=VendorStatus.ACTIVE)
    payment_terms = Column(Integer, default=30)  # Days
    currency_code = Column(String(3), default="SAR")
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("Account")
    invoices = relationship("APInvoice", back_populates="vendor")
    payments = relationship("APPayment", back_populates="vendor")

class APInvoiceStatus(str, PyEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"
    DISPUTED = "DISPUTED"

class APInvoice(Base):
    __tablename__ = "ap_invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    vendor_invoice_number = Column(String(50), nullable=True)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    subtotal = Column(Numeric(18, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), nullable=False)
    paid_amount = Column(Numeric(18, 2), default=0)
    status = Column(Enum(APInvoiceStatus), default=APInvoiceStatus.DRAFT)
    currency_code = Column(String(3), default="SAR")
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    journal_entry = relationship("JournalEntry")
    items = relationship("APInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("APInvoicePayment", back_populates="invoice")

class APInvoiceItem(Base):
    __tablename__ = "ap_invoice_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ap_invoices.id"), nullable=False)
    description = Column(String(200), nullable=False)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(18, 2), nullable=False)
    tax_rate = Column(Numeric(6, 2), default=0)
    tax_amount = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    
    # Relationships
    invoice = relationship("APInvoice", back_populates="items")
    account = relationship("Account")

class APPaymentMethod(str, PyEnum):
    BANK_TRANSFER = "BANK_TRANSFER"
    CHECK = "CHECK"
    CASH = "CASH"
    CREDIT_CARD = "CREDIT_CARD"
    OTHER = "OTHER"

class APPaymentStatus(str, PyEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PROCESSED = "PROCESSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class APPayment(Base):
    __tablename__ = "ap_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_number = Column(String(50), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    payment_method = Column(Enum(APPaymentMethod), nullable=False)
    reference = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(APPaymentStatus), default=APPaymentStatus.DRAFT)
    currency_code = Column(String(3), default="SAR")
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="payments")
    journal_entry = relationship("JournalEntry")
    bank_account = relationship("Account", foreign_keys=[bank_account_id])
    invoice_payments = relationship("APInvoicePayment", back_populates="payment", cascade="all, delete-orphan")

class APInvoicePayment(Base):
    __tablename__ = "ap_invoice_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("ap_payments.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ap_invoices.id"), nullable=False)
    amount_applied = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    payment = relationship("APPayment", back_populates="invoice_payments")
    invoice = relationship("APInvoice", back_populates="payments")
    
    # Composite unique constraint to prevent duplicate payment applications
    __table_args__ = (
        sqlalchemy.UniqueConstraint('payment_id', 'invoice_id', name='unique_ap_payment_invoice'),
    )