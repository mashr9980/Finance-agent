# File: app/services/currency_service.py
"""
Business logic for currency operations and conversions
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.currency_models import Currency, ExchangeRate
from app.schemas import currency_schemas

class CurrencyService:
    @staticmethod
    def get_base_currency(db: Session) -> Currency:
        """Get the system's base currency"""
        base_currency = db.query(Currency).filter(Currency.is_base_currency == True).first()
        if not base_currency:
            raise HTTPException(
                status_code=500, 
                detail="No base currency defined in the system. Please configure a base currency."
            )
        return base_currency
    
    @staticmethod
    def get_exchange_rate(
        db: Session,
        from_currency: str,
        to_currency: str,
        as_of_date: Optional[date] = None
    ) -> Decimal:
        """
        Get the exchange rate between two currencies as of a specific date.
        If no date is provided, the latest rate is used.
        """
        if from_currency == to_currency:
            return Decimal("1.00")
        
        # Default to today if no date specified
        if not as_of_date:
            as_of_date = date.today()
        
        # Try to find a direct exchange rate
        exchange_rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.effective_date <= as_of_date
        ).order_by(ExchangeRate.effective_date.desc()).first()
        
        if exchange_rate:
            return exchange_rate.rate
        
        # Try the inverse rate
        inverse_rate = db.query(ExchangeRate).filter(
            ExchangeRate.from_currency == to_currency,
            ExchangeRate.to_currency == from_currency,
            ExchangeRate.effective_date <= as_of_date
        ).order_by(ExchangeRate.effective_date.desc()).first()
        
        if inverse_rate:
            return Decimal("1") / inverse_rate.rate
        
        # If no direct rate, try to calculate via the base currency
        base_currency = CurrencyService.get_base_currency(db).code
        
        if from_currency == base_currency or to_currency == base_currency:
            raise HTTPException(
                status_code=404,
                detail=f"No exchange rate found for {from_currency} to {to_currency}"
            )
        
        # Get rates to convert both currencies to the base currency
        from_to_base_rate = CurrencyService.get_exchange_rate(db, from_currency, base_currency, as_of_date)
        base_to_to_rate = CurrencyService.get_exchange_rate(db, base_currency, to_currency, as_of_date)
        
        # Calculate cross rate
        return from_to_base_rate * base_to_to_rate
    
    @staticmethod
    def convert_amount(
        db: Session,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        conversion_date: Optional[date] = None
    ) -> currency_schemas.ConversionResponse:
        """
        Convert an amount from one currency to another.
        """
        if not conversion_date:
            conversion_date = date.today()
        
        # Same currency, no conversion needed
        if from_currency == to_currency:
            return currency_schemas.ConversionResponse(
                original_amount=amount,
                from_currency=from_currency,
                converted_amount=amount,
                to_currency=to_currency,
                exchange_rate=Decimal("1.00"),
                conversion_date=conversion_date
            )
        
        # Get exchange rate
        exchange_rate = CurrencyService.get_exchange_rate(
            db, from_currency, to_currency, conversion_date
        )
        
        # Apply conversion
        converted_amount = amount * exchange_rate
        
        # Get appropriate decimal places for the target currency
        to_currency_obj = db.query(Currency).filter(Currency.code == to_currency).first()
        if not to_currency_obj:
            raise HTTPException(status_code=404, detail=f"Currency {to_currency} not found")
        
        decimal_places = to_currency_obj.decimal_places
        converted_amount = converted_amount.quantize(Decimal(f'0.{"0" * decimal_places}'))
        
        return currency_schemas.ConversionResponse(
            original_amount=amount,
            from_currency=from_currency,
            converted_amount=converted_amount,
            to_currency=to_currency,
            exchange_rate=exchange_rate,
            conversion_date=conversion_date
        )