# File: app/models/currency_models.py
"""
SQLAlchemy models for multi-currency support
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, Boolean, Text, Enum, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

class Currency(Base):
    __tablename__ = "currencies"
    
    code = Column(String(3), primary_key=True)
    name = Column(String(50), nullable=False)
    symbol = Column(String(5), nullable=False)
    decimal_places = Column(Integer, default=2)
    is_base_currency = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_currency = Column(String(3), ForeignKey("currencies.code"), nullable=False)
    to_currency = Column(String(3), ForeignKey("currencies.code"), nullable=False)
    rate = Column(Numeric(precision=18, scale=6), nullable=False)
    effective_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Define a unique constraint for currency pair and date
    __table_args__ = (
        UniqueConstraint('from_currency', 'to_currency', 'effective_date', 
                         name='unique_exchange_rate'),
    )
    
    # Relationships
    from_currency_rel = relationship("Currency", foreign_keys=[from_currency])
    to_currency_rel = relationship("Currency", foreign_keys=[to_currency])