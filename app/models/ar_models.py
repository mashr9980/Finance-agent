# File: app/models/ar_models.py
"""
SQLAlchemy models for the Accounts Receivable module
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean, Text, Enum, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.gl_models import Account

class CustomerStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    HOLD = "HOLD"
    BLACKLISTED = "BLACKLISTED"

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    tax_id = Column(String(50), nullable=True)
    contact_name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    status = Column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE)
    payment_terms = Column(Integer, default=30)  # Days
    credit_limit = Column(Numeric(18, 2), default=0)
    currency_code = Column(String(3), default="SAR")
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    account = relationship("Account")
    invoices = relationship("ARInvoice", back_populates="customer")
    payments = relationship("ARPayment", back_populates="customer")

class ARInvoiceStatus(str, PyEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"
    DISPUTED = "DISPUTED"

class ARInvoice(Base):
    __tablename__ = "ar_invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    description = Column(Text, nullable=True)
    subtotal = Column(Numeric(18, 2), nullable=False)
    tax_amount = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), nullable=False)
    paid_amount = Column(Numeric(18, 2), default=0)
    status = Column(Enum(ARInvoiceStatus), default=ARInvoiceStatus.DRAFT)
    currency_code = Column(String(3), default="SAR")
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="invoices")
    journal_entry = relationship("JournalEntry")
    items = relationship("ARInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("ARInvoicePayment", back_populates="invoice")

class ARInvoiceItem(Base):
    __tablename__ = "ar_invoice_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False)
    description = Column(String(200), nullable=False)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(18, 2), nullable=False)
    tax_rate = Column(Numeric(6, 2), default=0)
    tax_amount = Column(Numeric(18, 2), default=0)
    total_amount = Column(Numeric(18, 2), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    
    # Relationships
    invoice = relationship("ARInvoice", back_populates="items")
    account = relationship("Account")

class ARPaymentMethod(str, PyEnum):
    BANK_TRANSFER = "BANK_TRANSFER"
    CHECK = "CHECK"
    CASH = "CASH"
    CREDIT_CARD = "CREDIT_CARD"
    OTHER = "OTHER"

class ARPaymentStatus(str, PyEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PROCESSED = "PROCESSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

class ARPayment(Base):
    __tablename__ = "ar_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_number = Column(String(50), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    payment_method = Column(Enum(ARPaymentMethod), nullable=False)
    reference = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(ARPaymentStatus), default=ARPaymentStatus.DRAFT)
    currency_code = Column(String(3), default="SAR")
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    bank_account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="payments")
    journal_entry = relationship("JournalEntry")
    bank_account = relationship("Account", foreign_keys=[bank_account_id])
    invoice_payments = relationship("ARInvoicePayment", back_populates="payment", cascade="all, delete-orphan")

class ARInvoicePayment(Base):
    __tablename__ = "ar_invoice_payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("ar_payments.id"), nullable=False)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("ar_invoices.id"), nullable=False)
    amount_applied = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    payment = relationship("ARPayment", back_populates="invoice_payments")
    invoice = relationship("ARInvoice", back_populates="payments")
    
    # Composite unique constraint to prevent duplicate payment applications
    __table_args__ = (
        UniqueConstraint('payment_id', 'invoice_id', name='unique_ar_payment_invoice'),
    )