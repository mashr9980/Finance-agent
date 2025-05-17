# File: app/services/gl_service.py
"""
Business logic for the General Ledger module
"""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.gl_models import Account, JournalEntry, JournalEntryLine, FiscalPeriod, JournalEntryStatus, AccountType
from app.schemas import gl_schemas

class GLService:
    @staticmethod
    def generate_entry_number():
        """Generate a unique journal entry number"""
        return f"JE-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    @staticmethod
    def validate_journal_entry(entry: gl_schemas.JournalEntryCreate, db: Session):
        """Validate a journal entry"""
        # Verify all accounts exist
        account_ids = [line.account_id for line in entry.lines]
        accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
        if len(accounts) != len(account_ids):
            raise HTTPException(status_code=400, detail="One or more accounts not found")
        
        # Verify debits = credits
        total_debits = sum(line.debit_amount for line in entry.lines)
        total_credits = sum(line.credit_amount for line in entry.lines)
        
        if total_debits != total_credits:
            raise HTTPException(
                status_code=400, 
                detail=f"Journal entry not balanced. Debits: {total_debits}, Credits: {total_credits}"
            )
            
        return True
    
    @staticmethod
    def calculate_trial_balance(db: Session, as_of_date: datetime = None):
        """Calculate trial balance as of a specific date"""
        if not as_of_date:
            as_of_date = datetime.utcnow()
        
        # Get all posted journal entries up to the as_of_date
        entries = db.query(JournalEntry).filter(
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= as_of_date
        ).all()
        
        # Get all entry IDs
        entry_ids = [entry.id for entry in entries]
        
        # Get all journal entry lines for these entries
        if not entry_ids:
            # Return empty trial balance if no entries
            return gl_schemas.TrialBalanceResponse(
                as_of_date=as_of_date,
                entries=[],
                total_debits=Decimal("0.00"),
                total_credits=Decimal("0.00")
            )
        
        lines = db.query(JournalEntryLine).filter(
            JournalEntryLine.journal_entry_id.in_(entry_ids)
        ).all()
        
        # Calculate balances by account
        account_totals = {}
        for line in lines:
            if line.account_id not in account_totals:
                account = db.query(Account).filter(Account.id == line.account_id).first()
                account_totals[line.account_id] = {
                    "account_code": account.code,
                    "account_name": account.name,
                    "account_type": account.account_type,
                    "debit_total": Decimal("0.00"),
                    "credit_total": Decimal("0.00")
                }
            
            account_totals[line.account_id]["debit_total"] += line.debit_amount
            account_totals[line.account_id]["credit_total"] += line.credit_amount
        
        # Create trial balance entries
        entries = []
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")
        
        for account_id, totals in account_totals.items():
            debit_total = totals["debit_total"]
            credit_total = totals["credit_total"]
            
            # Calculate balance based on account type
            account_type = totals["account_type"]
            if account_type in [AccountType.ASSET, AccountType.EXPENSE]:
                balance = debit_total - credit_total
            else:
                balance = credit_total - debit_total
            
            entry = gl_schemas.TrialBalanceEntry(
                account_id=account_id,
                account_code=totals["account_code"],
                account_name=totals["account_name"],
                account_type=account_type,
                debit_total=debit_total,
                credit_total=credit_total,
                balance=balance
            )
            
            entries.append(entry)
            total_debits += debit_total
            total_credits += credit_total
        
        return gl_schemas.TrialBalanceResponse(
            as_of_date=as_of_date,
            entries=entries,
            total_debits=total_debits,
            total_credits=total_credits
        )