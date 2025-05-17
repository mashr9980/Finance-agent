# File: app/integrations/bank_reconciliation.py
"""
Bank reconciliation functionality for matching bank statements with accounting records
"""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any, Tuple
from fastapi import HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import csv
import io
import re

from app.models.gl_models import Account, AccountType, JournalEntry, JournalEntryLine
from app.models.ap_models import APPayment, APPaymentStatus
from app.models.ar_models import ARPayment, ARPaymentStatus
from app.services.gl_service import GLService

class BankReconciliationService:
    @staticmethod
    async def reconcile_from_statement(
        db: Session,
        bank_account_id: uuid.UUID,
        statement_file: UploadFile,
        statement_date: date,
        created_by: str
    ) -> Dict[str, Any]:
        """
        Reconcile bank account from uploaded statement file
        
        Args:
            db: Database session
            bank_account_id: Bank account ID to reconcile
            statement_file: Uploaded CSV or Excel file with bank transactions
            statement_date: Date of the bank statement
            created_by: User performing the reconciliation
            
        Returns:
            Reconciliation summary
        """
        # Verify bank account exists and is of correct type
        bank_account = db.query(Account).filter(
            Account.id == bank_account_id,
            Account.account_type == AccountType.ASSET,
            Account.code.like('110%')  # Assuming 110x are cash/bank accounts
        ).first()
        
        if not bank_account:
            raise HTTPException(status_code=404, detail="Bank account not found")
        
        # Read the statement file
        transactions = await BankReconciliationService._read_statement_file(statement_file)
        
        # Get existing journal entries for this account
        journal_entries = db.query(JournalEntryLine).filter(
            JournalEntryLine.account_id == bank_account_id
        ).join(JournalEntry).filter(
            JournalEntry.status == 'POSTED',
            JournalEntry.entry_date <= statement_date
        ).all()
        
        # Reconciliation results
        matched_entries = []
        unmatched_entries = []
        unmatched_statement_items = []
        
        # Organize journal entries by amount for matching
        je_by_amount = {}
        for je_line in journal_entries:
            amount = je_line.debit_amount - je_line.credit_amount
            if amount not in je_by_amount:
                je_by_amount[amount] = []
            je_by_amount[amount].append(je_line)
        
        # Try to match each statement transaction with a journal entry
        for stmt_tx in transactions:
            amount = stmt_tx['amount']
            date_str = stmt_tx['date']
            description = stmt_tx['description']
            
            # Convert date string to date object based on common formats
            tx_date = BankReconciliationService._parse_date(date_str)
            if not tx_date:
                unmatched_statement_items.append({
                    'date': date_str,
                    'description': description,
                    'amount': amount,
                    'reason': 'Invalid date format'
                })
                continue
            
            # Look for matching journal entry by amount
            matching_entries = je_by_amount.get(-amount, [])  # Negate amount because bank statements show opposite sign
            
            # If multiple matches, try to filter by date proximity and description
            best_match = None
            min_days_diff = 10  # Max 10 days difference
            
            for je_line in matching_entries:
                je_date = je_line.journal_entry.entry_date
                days_diff = abs((tx_date - je_date.date()).days)
                
                # If date is close and transaction is not already matched
                if days_diff <= min_days_diff and je_line.id not in [m['journal_entry_id'] for m in matched_entries]:
                    # Check if descriptions have any similarity
                    je_desc = je_line.journal_entry.description or ''
                    similarity = BankReconciliationService._description_similarity(description, je_desc)
                    
                    if similarity > 0.3 or days_diff <= 2:  # Accept if similarity or very close date
                        best_match = je_line
                        min_days_diff = days_diff
            
            if best_match:
                matched_entries.append({
                    'journal_entry_id': best_match.journal_entry_id,
                    'line_id': best_match.id,
                    'statement_date': tx_date,
                    'journal_date': best_match.journal_entry.entry_date,
                    'description': description,
                    'journal_description': best_match.journal_entry.description,
                    'amount': amount
                })
            else:
                unmatched_statement_items.append({
                    'date': tx_date,
                    'description': description,
                    'amount': amount,
                    'reason': 'No matching journal entry found'
                })
        
        # Find journal entries without matches
        for je_line in journal_entries:
            if je_line.id not in [m['line_id'] for m in matched_entries]:
                amount = je_line.debit_amount - je_line.credit_amount
                unmatched_entries.append({
                    'journal_entry_id': je_line.journal_entry_id,
                    'line_id': je_line.id,
                    'date': je_line.journal_entry.entry_date,
                    'description': je_line.journal_entry.description,
                    'amount': amount
                })
        
        # Calculate totals
        matched_total = sum(m['amount'] for m in matched_entries)
        unmatched_stmt_total = sum(u['amount'] for u in unmatched_statement_items)
        unmatched_je_total = sum(u['amount'] for u in unmatched_entries)
        
        # Calculate statement ending balance
        statement_balance = matched_total + unmatched_stmt_total
        
        # Calculate book balance (including unmatched items)
        book_balance = statement_balance - unmatched_stmt_total + unmatched_je_total
        
        return {
            'account_id': bank_account_id,
            'account_code': bank_account.code,
            'account_name': bank_account.name,
            'statement_date': statement_date,
            'statement_balance': statement_balance,
            'book_balance': book_balance,
            'reconciliation_difference': statement_balance - book_balance,
            'matched_entries': matched_entries,
            'matched_count': len(matched_entries),
            'matched_total': matched_total,
            'unmatched_statement_items': unmatched_statement_items,
            'unmatched_statement_count': len(unmatched_statement_items),
            'unmatched_statement_total': unmatched_stmt_total,
            'unmatched_journal_entries': unmatched_entries,
            'unmatched_journal_count': len(unmatched_entries),
            'unmatched_journal_total': unmatched_je_total
        }
    
    @staticmethod
    async def create_missing_entries(
        db: Session,
        bank_account_id: uuid.UUID,
        transactions: List[Dict[str, Any]],
        suspense_account_id: uuid.UUID,
        created_by: str
    ) -> List[uuid.UUID]:
        """
        Create journal entries for unmatched statement items
        
        Args:
            db: Database session
            bank_account_id: Bank account ID
            transactions: List of transactions to create entries for
            suspense_account_id: Account to use for balancing entries
            created_by: User creating the entries
            
        Returns:
            List of created journal entry IDs
        """
        # Verify accounts exist
        bank_account = db.query(Account).filter(Account.id == bank_account_id).first()
        suspense_account = db.query(Account).filter(Account.id == suspense_account_id).first()
        
        if not bank_account:
            raise HTTPException(status_code=404, detail="Bank account not found")
            
        if not suspense_account:
            raise HTTPException(status_code=404, detail="Suspense account not found")
        
        created_entries = []
        
        # Create journal entries for each transaction
        for tx in transactions:
            # Parse date if it's a string
            tx_date = tx['date']
            if isinstance(tx_date, str):
                tx_date = BankReconciliationService._parse_date(tx_date)
                if not tx_date:
                    continue  # Skip if date can't be parsed
            
            amount = Decimal(str(tx['amount']))
            description = tx['description']
            
            # Create journal entry
            entry = {
                'entry_date': datetime.combine(tx_date, datetime.min.time()),
                'description': f"Bank statement: {description}",
                'reference': 'Bank Reconciliation',
                'lines': []
            }
            
            # Add bank account line
            if amount > 0:
                # Deposit
                entry['lines'].append({
                    'account_id': bank_account_id,
                    'description': description,
                    'debit_amount': amount,
                    'credit_amount': Decimal('0.00')
                })
                
                # Credit suspense account
                entry['lines'].append({
                    'account_id': suspense_account_id,
                    'description': f"Bank deposit: {description}",
                    'debit_amount': Decimal('0.00'),
                    'credit_amount': amount
                })
            else:
                # Withdrawal (negative amount)
                entry['lines'].append({
                    'account_id': bank_account_id,
                    'description': description,
                    'debit_amount': Decimal('0.00'),
                    'credit_amount': abs(amount)
                })
                
                # Debit suspense account
                entry['lines'].append({
                    'account_id': suspense_account_id,
                    'description': f"Bank withdrawal: {description}",
                    'debit_amount': abs(amount),
                    'credit_amount': Decimal('0.00')
                })
            
            # Create the journal entry
            journal_entry = GLService.create_journal_entry(
                db=db,
                description=entry['description'],
                entry_date=entry['entry_date'],
                lines=entry['lines'],
                created_by=created_by
            )
            
            created_entries.append(journal_entry.id)
        
        return created_entries
    
    @staticmethod
    async def _read_statement_file(file: UploadFile) -> List[Dict[str, Any]]:
        """Read a bank statement file (CSV or Excel)"""
        content = await file.read()
        
        # Determine file type by extension
        filename = file.filename.lower()
        
        if filename.endswith('.csv'):
            # Process CSV
            text = content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(text))
            
            # Try to identify columns
            transactions = []
            for row in csv_reader:
                # Find date, description, and amount columns
                date_col = BankReconciliationService._find_column(row, ['date', 'transaction date', 'posted date'])
                desc_col = BankReconciliationService._find_column(row, ['description', 'narration', 'details', 'transaction'])
                amount_col = BankReconciliationService._find_column(row, ['amount', 'transaction amount', 'value'])
                
                if not all([date_col, desc_col, amount_col]):
                    # Try debit/credit columns if amount not found
                    debit_col = BankReconciliationService._find_column(row, ['debit', 'withdrawal', 'money out'])
                    credit_col = BankReconciliationService._find_column(row, ['credit', 'deposit', 'money in'])
                    
                    if debit_col and credit_col:
                        debit_amount = BankReconciliationService._parse_amount(row[debit_col])
                        credit_amount = BankReconciliationService._parse_amount(row[credit_col])
                        
                        # Use only the non-zero value with appropriate sign
                        if debit_amount != 0:
                            amount = -debit_amount  # Debit is negative (money out)
                        else:
                            amount = credit_amount  # Credit is positive (money in)
                    else:
                        # Can't find amount columns
                        continue
                else:
                    # Parse amount from single column
                    amount = BankReconciliationService._parse_amount(row[amount_col])
                
                transactions.append({
                    'date': row[date_col] if date_col else None,
                    'description': row[desc_col] if desc_col else 'Unknown',
                    'amount': amount
                })
            
            return transactions
        
        elif filename.endswith(('.xls', '.xlsx')):
            # For Excel files, we'd use openpyxl or xlrd
            # This is a placeholder - in a real implementation, you'd parse Excel files here
            raise HTTPException(status_code=400, detail="Excel file parsing not implemented")
        
        else:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Please upload a CSV or Excel file."
            )
    
    @staticmethod
    def _find_column(row: Dict[str, str], possible_names: List[str]) -> Optional[str]:
        """Find a column in a CSV row by checking possible names"""
        for col in row.keys():
            if col and any(name in col.lower() for name in possible_names):
                return col
        return None
    
    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal:
        """Parse a monetary amount from string to Decimal"""
        if not amount_str or amount_str.strip() == '':
            return Decimal('0.00')
        
        # Remove currency symbols and thousands separators
        clean_amount = re.sub(r'[^\d.-]', '', amount_str)
        
        try:
            return Decimal(clean_amount)
        except:
            return Decimal('0.00')
    
    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Parse a date string in various formats"""
        formats = [
            '%Y-%m-%d',      # 2023-01-31
            '%d/%m/%Y',      # 31/01/2023
            '%m/%d/%Y',      # 01/31/2023
            '%d-%m-%Y',      # 31-01-2023
            '%d %b %Y',      # 31 Jan 2023
            '%d %B %Y',      # 31 January 2023
            '%b %d, %Y'      # Jan 31, 2023
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def _description_similarity(desc1: str, desc2: str) -> float:
        """
        Calculate simple similarity between two descriptions
        Returns a value between 0 (no similarity) and 1 (identical)
        """
        # Convert to lowercase and remove common non-word characters
        d1 = re.sub(r'[^\w\s]', '', desc1.lower())
        d2 = re.sub(r'[^\w\s]', '', desc2.lower())
        
        # Split into words
        words1 = set(d1.split())
        words2 = set(d2.split())
        
        # Check for empty sets
        if not words1 or not words2:
            return 0.0
        
        # Count common words
        common_words = words1.intersection(words2)
        
        # Calculate Jaccard similarity
        return len(common_words) / len(words1.union(words2))