# File: app/models/gl_models.py
"""
SQLAlchemy models for the General Ledger module
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

class AccountType(str, PyEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    account_type = Column(Enum(AccountType), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    children = relationship("Account", backref="parent", remote_side=[id])
    journal_entries = relationship("JournalEntryLine", back_populates="account")
    
    # For multi-currency support
    currency_code = Column(String(3), default="SAR")  # Default to Saudi Riyal

class JournalEntryStatus(str, PyEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_number = Column(String(20), unique=True, index=True, nullable=False)
    entry_date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)
    reference = Column(String(100), nullable=True)
    status = Column(Enum(JournalEntryStatus), default=JournalEntryStatus.DRAFT)
    is_recurring = Column(Boolean, default=False)
    created_by = Column(String(100), nullable=False)  # Will link to users table in future
    created_at = Column(DateTime, default=datetime.utcnow)
    posted_at = Column(DateTime, nullable=True)
    reversed_at = Column(DateTime, nullable=True)
    
    # Relationships
    lines = relationship("JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan")

class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    description = Column(Text, nullable=True)
    debit_amount = Column(Numeric(precision=18, scale=2), default=0)
    credit_amount = Column(Numeric(precision=18, scale=2), default=0)
    
    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account", back_populates="journal_entries")

class FiscalPeriod(Base):
    __tablename__ = "fiscal_periods"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

class AccountBalance(Base):
    __tablename__ = "account_balances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    fiscal_period_id = Column(UUID(as_uuid=True), ForeignKey("fiscal_periods.id"), nullable=False)
    opening_balance = Column(Numeric(precision=18, scale=2), default=0)
    current_balance = Column(Numeric(precision=18, scale=2), default=0)
    closing_balance = Column(Numeric(precision=18, scale=2), default=0)
    
    # For multi-currency support
    currency_code = Column(String(3), default="SAR")