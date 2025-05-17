# File: app/services/fiscal_service.py
"""
Business logic for fiscal periods and year-end closing
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any
from sqlalchemy import and_, func, literal_column, case, text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.gl_models import (
    Account, AccountType, JournalEntry, JournalEntryLine, 
    JournalEntryStatus, FiscalPeriod, AccountBalance
)
from app.schemas import gl_schemas
from app.services.gl_service import GLService

class FiscalService:
    @staticmethod
    def get_current_fiscal_period(db: Session) -> FiscalPeriod:
        """Get the current fiscal period based on today's date"""
        today = date.today()
        
        current_period = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date <= today,
            FiscalPeriod.end_date >= today
        ).first()
        
        if not current_period:
            raise HTTPException(
                status_code=404, 
                detail="No fiscal period defined for the current date. Please configure fiscal periods."
            )
        
        return current_period
    
    @staticmethod
    def get_fiscal_year_periods(db: Session, year: int) -> List[FiscalPeriod]:
        """Get all fiscal periods for a specific year"""
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        periods = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date >= year_start,
            FiscalPeriod.end_date <= year_end
        ).order_by(FiscalPeriod.start_date).all()
        
        return periods
    
    @staticmethod
    def validate_fiscal_year_closed(db: Session, year: int) -> bool:
        """Check if all periods in a fiscal year are closed"""
        periods = FiscalService.get_fiscal_year_periods(db, year)
        
        if not periods:
            raise HTTPException(
                status_code=404, 
                detail=f"No fiscal periods found for year {year}"
            )
        
        # Check if all periods are closed
        for period in periods:
            if not period.is_closed:
                return False
                
        return True
    
    @staticmethod
    def close_fiscal_period(
        db: Session, 
        period_id: uuid.UUID, 
        user_id: str
    ) -> FiscalPeriod:
        """Close a fiscal period and update account balances"""
        period = db.query(FiscalPeriod).filter(FiscalPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        
        if period.is_closed:
            raise HTTPException(status_code=400, detail="Fiscal period is already closed")
        
        # Check for unposted journal entries in this period
        unposted_entries = db.query(JournalEntry).filter(
            JournalEntry.entry_date >= period.start_date,
            JournalEntry.entry_date <= period.end_date,
            JournalEntry.status == JournalEntryStatus.DRAFT
        ).count()
        
        if unposted_entries > 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot close period with {unposted_entries} unposted journal entries"
            )
        
        # Calculate ending balances for all accounts for this period
        account_balances = FiscalService.calculate_period_ending_balances(db, period)
        
        # Store account balances
        for account_id, balance in account_balances.items():
            # Check if balance record exists
            balance_record = db.query(AccountBalance).filter(
                AccountBalance.account_id == account_id,
                AccountBalance.fiscal_period_id == period.id
            ).first()
            
            if balance_record:
                # Update existing record
                balance_record.closing_balance = balance
            else:
                # Create new record
                previous_period = FiscalService.get_previous_period(db, period)
                
                opening_balance = Decimal("0.00")
                if previous_period:
                    # Get the closing balance from the previous period
                    prev_balance = db.query(AccountBalance).filter(
                        AccountBalance.account_id == account_id,
                        AccountBalance.fiscal_period_id == previous_period.id
                    ).first()
                    
                    if prev_balance:
                        opening_balance = prev_balance.closing_balance
                
                # Create new balance record
                db_balance = AccountBalance(
                    account_id=account_id,
                    fiscal_period_id=period.id,
                    opening_balance=opening_balance,
                    current_balance=balance - opening_balance,
                    closing_balance=balance
                )
                db.add(db_balance)
        
        # Mark period as closed
        period.is_closed = True
        period.closed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(period)
        
        return period
    
    @staticmethod
    def close_fiscal_year(
        db: Session, 
        year: int, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        Close a fiscal year:
        1. Ensure all periods are closed
        2. Generate year-end closing entries
        3. Create opening balances for the new year
        """
        # Check if all periods are closed
        if not FiscalService.validate_fiscal_year_closed(db, year):
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot close fiscal year {year} - not all periods are closed"
            )
        
        # Get periods for the year
        periods = FiscalService.get_fiscal_year_periods(db, year)
        
        # Get the last period of the year
        last_period = max(periods, key=lambda p: p.end_date)
        
        # Get retained earnings account
        retained_earnings_account = db.query(Account).filter(
            Account.code.like("3100%"),  # Assuming 3100 is retained earnings
            Account.account_type == AccountType.EQUITY
        ).first()
        
        if not retained_earnings_account:
            raise HTTPException(
                status_code=400, 
                detail="Retained Earnings account not found. Please configure the Chart of Accounts."
            )
        
        # Get the account balances as of the end of the year
        account_balances = FiscalService.calculate_period_ending_balances(db, last_period)
        
        # Calculate the total net income/loss for the year
        total_revenue = Decimal("0.00")
        total_expense = Decimal("0.00")
        
        for account_id, balance in account_balances.items():
            account = db.query(Account).filter(Account.id == account_id).first()
            
            if account and account.account_type == AccountType.REVENUE:
                total_revenue += balance
            elif account and account.account_type == AccountType.EXPENSE:
                total_expense += balance
        
        # Net income (revenue - expense)
        net_income = total_revenue - total_expense
        
        # Create closing entry to zero out income and expense accounts
        closing_entry = JournalEntry(
            entry_number=f"YE-CLOSE-{year}",
            entry_date=last_period.end_date,
            description=f"Year-end closing entry for {year}",
            status=JournalEntryStatus.POSTED,
            created_by=user_id,
            posted_at=datetime.utcnow()
        )
        
        db.add(closing_entry)
        db.flush()  # Get ID without committing
        
        # Create journal entry lines to close revenue and expense accounts
        for account_id, balance in account_balances.items():
            account = db.query(Account).filter(Account.id == account_id).first()
            
            if not account:
                continue
                
            if account.account_type == AccountType.REVENUE and balance != 0:
                # Debit revenue accounts (to zero them out)
                db_line = JournalEntryLine(
                    journal_entry_id=closing_entry.id,
                    account_id=account_id,
                    description=f"Close {account.name} for year {year}",
                    debit_amount=balance,
                    credit_amount=Decimal("0.00")
                )
                db.add(db_line)
                
            elif account.account_type == AccountType.EXPENSE and balance != 0:
                # Credit expense accounts (to zero them out)
                db_line = JournalEntryLine(
                    journal_entry_id=closing_entry.id,
                    account_id=account_id,
                    description=f"Close {account.name} for year {year}",
                    debit_amount=Decimal("0.00"),
                    credit_amount=balance
                )
                db.add(db_line)
        
        # Balance the entry with retained earnings
        if net_income > 0:
            # Credit retained earnings for net income
            db_line = JournalEntryLine(
                journal_entry_id=closing_entry.id,
                account_id=retained_earnings_account.id,
                description=f"Net income for year {year}",
                debit_amount=Decimal("0.00"),
                credit_amount=net_income
            )
        else:
            # Debit retained earnings for net loss
            db_line = JournalEntryLine(
                journal_entry_id=closing_entry.id,
                account_id=retained_earnings_account.id,
                description=f"Net loss for year {year}",
                debit_amount=abs(net_income),
                credit_amount=Decimal("0.00")
            )
            
        db.add(db_line)
        
        # Create next year's opening balances
        next_year = year + 1
        next_year_start = date(next_year, 1, 1)
        
        # Check if next year's first period exists
        next_period = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date >= next_year_start
        ).order_by(FiscalPeriod.start_date).first()
        
        if next_period:
            # Calculate opening balances for next year
            # Only balance sheet accounts (assets, liabilities, equity) carry forward
            for account_id, balance in account_balances.items():
                account = db.query(Account).filter(Account.id == account_id).first()
                
                if not account:
                    continue
                    
                if account.account_type in [AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY]:
                    # Carry the balance forward
                    db_balance = AccountBalance(
                        account_id=account_id,
                        fiscal_period_id=next_period.id,
                        opening_balance=balance,
                        current_balance=Decimal("0.00"),
                        closing_balance=balance  # Initial closing = opening
                    )
                    db.add(db_balance)
                    
                elif account.account_type in [AccountType.REVENUE, AccountType.EXPENSE]:
                    # Zero out income statement accounts
                    db_balance = AccountBalance(
                        account_id=account_id,
                        fiscal_period_id=next_period.id,
                        opening_balance=Decimal("0.00"),
                        current_balance=Decimal("0.00"),
                        closing_balance=Decimal("0.00")
                    )
                    db.add(db_balance)
        
        # Commit all changes
        db.commit()
        
        return {
            "year": year,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_income": net_income,
            "closing_entry_id": closing_entry.id,
            "success": True
        }
    
    @staticmethod
    def calculate_period_ending_balances(db: Session, period: FiscalPeriod) -> Dict[uuid.UUID, Decimal]:
        """Calculate ending balances for all accounts for a specific period"""
        # Get all posted journal entries up to the end of the period
        entries = db.query(JournalEntry).filter(
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= period.end_date
        ).all()
        
        # Get all entry IDs
        entry_ids = [entry.id for entry in entries]
        
        if not entry_ids:
            return {}
        
        # Get all journal entry lines for these entries
        lines = db.query(JournalEntryLine).filter(
            JournalEntryLine.journal_entry_id.in_(entry_ids)
        ).all()
        
        # Calculate balances for each account
        balances = {}
        for line in lines:
            if line.account_id not in balances:
                balances[line.account_id] = Decimal('0.00')
            
            balances[line.account_id] += line.debit_amount - line.credit_amount
        
        return balances
    
    @staticmethod
    def get_previous_period(db: Session, period: FiscalPeriod) -> Optional[FiscalPeriod]:
        """Get the fiscal period immediately before the given period"""
        previous_period = db.query(FiscalPeriod).filter(
            FiscalPeriod.end_date < period.start_date
        ).order_by(FiscalPeriod.end_date.desc()).first()
        
        return previous_period
    
    @staticmethod
    def get_next_period(db: Session, period: FiscalPeriod) -> Optional[FiscalPeriod]:
        """Get the fiscal period immediately after the given period"""
        next_period = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date > period.end_date
        ).order_by(FiscalPeriod.start_date).first()
        
        return next_period
    
    @staticmethod
    def create_fiscal_year(db: Session, year: int, user_id: str) -> List[FiscalPeriod]:
        """Create monthly fiscal periods for a year"""
        # Check if any periods already exist for this year
        existing_periods = FiscalService.get_fiscal_year_periods(db, year)
        if existing_periods:
            raise HTTPException(
                status_code=400, 
                detail=f"Fiscal periods already exist for year {year}"
            )
        
        created_periods = []
        
        # Create 12 monthly periods
        for month in range(1, 13):
            # Calculate start and end dates
            if month < 12:
                start_date = date(year, month, 1)
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            else:
                start_date = date(year, 12, 1)
                end_date = date(year, 12, 31)
            
            # Create period
            period = FiscalPeriod(
                name=f"{year}-{month:02d}",
                start_date=start_date,
                end_date=end_date,
                is_closed=False
            )
            
            db.add(period)
            created_periods.append(period)
        
        db.commit()
        
        # Refresh periods to get IDs
        for period in created_periods:
            db.refresh(period)
        
        return created_periods