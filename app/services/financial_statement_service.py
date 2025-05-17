# File: app/services/financial_statement_service.py
"""
Service for generating financial statements (Balance Sheet, Income Statement, Cash Flow Statement)
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy import and_, func, literal_column, case, text
from sqlalchemy.orm import Session

from app.models.gl_models import Account, AccountType, JournalEntry, JournalEntryLine, JournalEntryStatus, FiscalPeriod
from app.models.ap_models import APInvoice, APInvoiceStatus, APPayment, APPaymentStatus
from app.models.ar_models import ARInvoice, ARInvoiceStatus, ARPayment, ARPaymentStatus

class FinancialStatementService:
    @staticmethod
    def get_balance_sheet(
        db: Session, 
        as_of_date: date, 
        comparative: bool = False,
        previous_period_months: int = 12
    ) -> Dict[str, Any]:
        """
        Generate a balance sheet as of a specific date.
        
        Args:
            db: Database session
            as_of_date: Date of the balance sheet
            comparative: Whether to include comparative figures
            previous_period_months: Number of months to look back for comparative
            
        Returns:
            Dictionary containing balance sheet data
        """
        # Get account balances as of the specified date
        current_balances = FinancialStatementService._get_account_balances(db, as_of_date)
        
        # Organize data for assets
        assets = FinancialStatementService._organize_balance_sheet_section(
            current_balances, 
            AccountType.ASSET
        )
        
        # Organize data for liabilities
        liabilities = FinancialStatementService._organize_balance_sheet_section(
            current_balances, 
            AccountType.LIABILITY
        )
        
        # Organize data for equity
        equity = FinancialStatementService._organize_balance_sheet_section(
            current_balances, 
            AccountType.EQUITY
        )
        
        # Get net income for current period and add to equity
        income_statement = FinancialStatementService.get_income_statement(
            db, 
            from_date=date(as_of_date.year, 1, 1),  # Start of year
            to_date=as_of_date,
            include_details=False
        )
        
        net_income = income_statement.get('net_income', Decimal('0.00'))
        equity['sections'].append({
            'title': 'Net Income (Current Period)',
            'accounts': [],
            'total': net_income
        })
        equity['total'] += net_income
        
        # If comparative is requested, get previous period data
        comparative_data = None
        if comparative:
            previous_date = as_of_date - timedelta(days=previous_period_months*30)  # Approximate
            comparative_data = FinancialStatementService.get_balance_sheet(
                db, 
                as_of_date=previous_date,
                comparative=False
            )
        
        # Compile the complete balance sheet
        balance_sheet = {
            'as_of_date': as_of_date,
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': assets['total'],
            'total_liabilities_equity': liabilities['total'] + equity['total'],
            'comparative': comparative_data
        }
        
        return balance_sheet
    
    @staticmethod
    def get_income_statement(
        db: Session, 
        from_date: date,
        to_date: date,
        comparative: bool = False,
        include_details: bool = True,
        previous_period_months: int = 12
    ) -> Dict[str, Any]:
        """
        Generate an income statement for a specific period.
        
        Args:
            db: Database session
            from_date: Start date of the period
            to_date: End date of the period
            comparative: Whether to include comparative figures
            include_details: Whether to include detailed account breakdown
            previous_period_months: Number of months to look back for comparative
            
        Returns:
            Dictionary containing income statement data
        """
        # Get revenue and expense transactions for the period
        transactions = FinancialStatementService._get_period_transactions(
            db, from_date, to_date
        )
        
        # Organize revenue data
        revenue = FinancialStatementService._organize_income_statement_section(
            transactions, 
            AccountType.REVENUE,
            include_details
        )
        
        # Organize expense data
        expenses = FinancialStatementService._organize_income_statement_section(
            transactions, 
            AccountType.EXPENSE,
            include_details
        )
        
        # Calculate net income
        net_income = revenue['total'] - expenses['total']
        
        # If comparative is requested, get previous period data
        comparative_data = None
        if comparative:
            previous_from_date = from_date - timedelta(days=previous_period_months*30)  # Approximate
            previous_to_date = to_date - timedelta(days=previous_period_months*30)      # Approximate
            comparative_data = FinancialStatementService.get_income_statement(
                db, 
                from_date=previous_from_date,
                to_date=previous_to_date,
                comparative=False,
                include_details=include_details
            )
        
        # Compile the complete income statement
        income_statement = {
            'from_date': from_date,
            'to_date': to_date,
            'revenue': revenue,
            'expenses': expenses,
            'gross_profit': revenue['total'],
            'total_expenses': expenses['total'],
            'net_income': net_income,
            'comparative': comparative_data
        }
        
        return income_statement
    
    @staticmethod
    def get_cash_flow_statement(
        db: Session, 
        from_date: date,
        to_date: date,
        comparative: bool = False,
        previous_period_months: int = 12
    ) -> Dict[str, Any]:
        """
        Generate a cash flow statement for a specific period.
        
        Args:
            db: Database session
            from_date: Start date of the period
            to_date: End date of the period
            comparative: Whether to include comparative figures
            previous_period_months: Number of months to look back for comparative
            
        Returns:
            Dictionary containing cash flow statement data
        """
        # Get net income for the period
        income_statement = FinancialStatementService.get_income_statement(
            db, from_date, to_date, include_details=False
        )
        net_income = income_statement['net_income']
        
        # Get operating activities cash flow
        operating_activities = FinancialStatementService._get_operating_cash_flows(
            db, from_date, to_date
        )
        
        # Get investing activities cash flow
        investing_activities = FinancialStatementService._get_investing_cash_flows(
            db, from_date, to_date
        )
        
        # Get financing activities cash flow
        financing_activities = FinancialStatementService._get_financing_cash_flows(
            db, from_date, to_date
        )
        
        # Get cash account balances
        start_cash = FinancialStatementService._get_cash_balance(db, from_date)
        end_cash = FinancialStatementService._get_cash_balance(db, to_date)
        
        # Calculate net change in cash
        net_cash_change = sum(item['amount'] for item in operating_activities['items'])
        net_cash_change += sum(item['amount'] for item in investing_activities['items'])
        net_cash_change += sum(item['amount'] for item in financing_activities['items'])
        
        # Verify calculated change matches actual change
        calculated_end_cash = start_cash + net_cash_change
        if abs(calculated_end_cash - end_cash) > Decimal('0.01'):
            # There's a discrepancy - add reconciliation item
            discrepancy = end_cash - calculated_end_cash
            operating_activities['items'].append({
                'description': 'Reconciliation adjustment',
                'amount': discrepancy
            })
            operating_activities['total'] += discrepancy
            net_cash_change += discrepancy
        
        # If comparative is requested, get previous period data
        comparative_data = None
        if comparative:
            previous_from_date = from_date - timedelta(days=previous_period_months*30)  # Approximate
            previous_to_date = to_date - timedelta(days=previous_period_months*30)      # Approximate
            comparative_data = FinancialStatementService.get_cash_flow_statement(
                db, 
                from_date=previous_from_date,
                to_date=previous_to_date,
                comparative=False
            )
        
        # Compile the complete cash flow statement
        cash_flow_statement = {
            'from_date': from_date,
            'to_date': to_date,
            'net_income': net_income,
            'operating_activities': operating_activities,
            'investing_activities': investing_activities,
            'financing_activities': financing_activities,
            'net_cash_change': net_cash_change,
            'beginning_cash': start_cash,
            'ending_cash': end_cash,
            'comparative': comparative_data
        }
        
        return cash_flow_statement
    
    @staticmethod
    def _get_account_balances(db: Session, as_of_date: date) -> Dict[uuid.UUID, Decimal]:
        """Get account balances as of a specific date"""
        balances = {}
        
        # Get all posted journal entries up to the as_of_date
        entries = db.query(JournalEntry).filter(
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= as_of_date
        ).all()
        
        # Get all entry IDs
        entry_ids = [entry.id for entry in entries]
        
        if not entry_ids:
            return balances
        
        # Get all journal entry lines for these entries
        lines = db.query(JournalEntryLine).filter(
            JournalEntryLine.journal_entry_id.in_(entry_ids)
        ).all()
        
        # Calculate balances for each account
        for line in lines:
            if line.account_id not in balances:
                balances[line.account_id] = Decimal('0.00')
            
            balances[line.account_id] += line.debit_amount - line.credit_amount
        
        return balances
    
    @staticmethod
    def _organize_balance_sheet_section(
        balances: Dict[uuid.UUID, Decimal], 
        account_type: AccountType
    ) -> Dict[str, Any]:
        """Organize balance sheet section (assets, liabilities, or equity)"""
        # This would be better done with SQL directly in a real implementation
        # For demonstration, we'll simulate with a separate query
        
        # For demo purposes, we'll return a structured format
        # In a real implementation, this would use the balances and query the database
        if account_type == AccountType.ASSET:
            return {
                'total': sum(balance for acct_id, balance in balances.items() 
                            if Account.query.get(acct_id).account_type == AccountType.ASSET),
                'sections': [
                    {
                        'title': 'Current Assets',
                        'accounts': [],  # Would be filled with account details
                        'total': Decimal('0.00')  # Would be calculated
                    },
                    {
                        'title': 'Fixed Assets',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Other Assets',
                        'accounts': [],
                        'total': Decimal('0.00')
                    }
                ]
            }
        elif account_type == AccountType.LIABILITY:
            return {
                'total': sum(balance * -1 for acct_id, balance in balances.items() 
                            if Account.query.get(acct_id).account_type == AccountType.LIABILITY),
                'sections': [
                    {
                        'title': 'Current Liabilities',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Long-Term Liabilities',
                        'accounts': [],
                        'total': Decimal('0.00')
                    }
                ]
            }
        elif account_type == AccountType.EQUITY:
            return {
                'total': sum(balance * -1 for acct_id, balance in balances.items() 
                            if Account.query.get(acct_id).account_type == AccountType.EQUITY),
                'sections': [
                    {
                        'title': 'Share Capital',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Retained Earnings',
                        'accounts': [],
                        'total': Decimal('0.00')
                    }
                ]
            }
        
        return {'total': Decimal('0.00'), 'sections': []}
    
    @staticmethod
    def _get_period_transactions(
        db: Session, 
        from_date: date,
        to_date: date
    ) -> Dict[uuid.UUID, Decimal]:
        """Get transactions for a specific period"""
        transactions = {}
        
        # Get all posted journal entries for the period
        entries = db.query(JournalEntry).filter(
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date >= from_date,
            JournalEntry.entry_date <= to_date
        ).all()
        
        # Get all entry IDs
        entry_ids = [entry.id for entry in entries]
        
        if not entry_ids:
            return transactions
        
        # Get all journal entry lines for these entries
        lines = db.query(JournalEntryLine).filter(
            JournalEntryLine.journal_entry_id.in_(entry_ids)
        ).all()
        
        # Calculate transaction amounts for each account
        for line in lines:
            if line.account_id not in transactions:
                transactions[line.account_id] = Decimal('0.00')
            
            transactions[line.account_id] += line.debit_amount - line.credit_amount
        
        return transactions
    
    @staticmethod
    def _organize_income_statement_section(
        transactions: Dict[uuid.UUID, Decimal],
        account_type: AccountType,
        include_details: bool
    ) -> Dict[str, Any]:
        """Organize income statement section (revenue or expenses)"""
        # This would be better done with SQL directly in a real implementation
        
        # For demo purposes, we'll return a structured format
        if account_type == AccountType.REVENUE:
            return {
                'total': sum(amount * -1 for acct_id, amount in transactions.items() 
                             if Account.query.get(acct_id).account_type == AccountType.REVENUE),
                'sections': [
                    {
                        'title': 'Operating Revenue',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Other Revenue',
                        'accounts': [],
                        'total': Decimal('0.00')
                    }
                ] if include_details else []
            }
        elif account_type == AccountType.EXPENSE:
            return {
                'total': sum(amount for acct_id, amount in transactions.items() 
                             if Account.query.get(acct_id).account_type == AccountType.EXPENSE),
                'sections': [
                    {
                        'title': 'Cost of Goods Sold',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Operating Expenses',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Financial Expenses',
                        'accounts': [],
                        'total': Decimal('0.00')
                    },
                    {
                        'title': 'Tax Expenses',
                        'accounts': [],
                        'total': Decimal('0.00')
                    }
                ] if include_details else []
            }
        
        return {'total': Decimal('0.00'), 'sections': []}
    
    @staticmethod
    def _get_operating_cash_flows(db: Session, from_date: date, to_date: date) -> Dict[str, Any]:
        """Get cash flows from operating activities"""
        # In a real implementation, this would be much more sophisticated
        # For demo purposes, we'll return a simplified structure
        
        # Get accounts receivable changes
        ar_start = db.query(func.sum(ARInvoice.total_amount - ARInvoice.paid_amount)).filter(
            ARInvoice.issue_date < from_date,
            ARInvoice.status.in_([
                ARInvoiceStatus.APPROVED, 
                ARInvoiceStatus.PARTIALLY_PAID,
                ARInvoiceStatus.OVERDUE
            ])
        ).scalar() or Decimal('0.00')
        
        ar_end = db.query(func.sum(ARInvoice.total_amount - ARInvoice.paid_amount)).filter(
            ARInvoice.issue_date <= to_date,
            ARInvoice.status.in_([
                ARInvoiceStatus.APPROVED, 
                ARInvoiceStatus.PARTIALLY_PAID,
                ARInvoiceStatus.OVERDUE
            ])
        ).scalar() or Decimal('0.00')
        
        ar_change = ar_start - ar_end  # Positive means decrease in AR (cash inflow)
        
        # Get accounts payable changes
        ap_start = db.query(func.sum(APInvoice.total_amount - APInvoice.paid_amount)).filter(
            APInvoice.issue_date < from_date,
            APInvoice.status.in_([
                APInvoiceStatus.APPROVED, 
                APInvoiceStatus.PARTIALLY_PAID,
                APInvoiceStatus.OVERDUE
            ])
        ).scalar() or Decimal('0.00')
        
        ap_end = db.query(func.sum(APInvoice.total_amount - APInvoice.paid_amount)).filter(
            APInvoice.issue_date <= to_date,
            APInvoice.status.in_([
                APInvoiceStatus.APPROVED, 
                APInvoiceStatus.PARTIALLY_PAID,
                APInvoiceStatus.OVERDUE
            ])
        ).scalar() or Decimal('0.00')
        
        ap_change = ap_end - ap_start  # Positive means increase in AP (cash inflow)
        
        # Get income statement data (for net income and non-cash expenses)
        income_statement = FinancialStatementService.get_income_statement(
            db, from_date, to_date, include_details=False
        )
        
        net_income = income_statement['net_income']
        
        # Simplified: Get depreciation (in a real system, this would be more sophisticated)
        depreciation = Decimal('0.00')  # Would calculate from actual accounts
        
        return {
            'total': net_income + depreciation + ar_change + ap_change,
            'items': [
                {'description': 'Net Income', 'amount': net_income},
                {'description': 'Depreciation and Amortization', 'amount': depreciation},
                {'description': 'Decrease (Increase) in Accounts Receivable', 'amount': ar_change},
                {'description': 'Increase (Decrease) in Accounts Payable', 'amount': ap_change}
            ]
        }
    
    @staticmethod
    def _get_investing_cash_flows(db: Session, from_date: date, to_date: date) -> Dict[str, Any]:
        """Get cash flows from investing activities"""
        # This is a placeholder with demo data
        # In a real implementation, this would analyze fixed asset accounts and related transactions
        
        # For demonstration, we'll return placeholder data
        return {
            'total': Decimal('-25000.00'),  # Negative for cash outflows
            'items': [
                {'description': 'Purchase of Equipment', 'amount': Decimal('-15000.00')},
                {'description': 'Purchase of Software', 'amount': Decimal('-10000.00')}
            ]
        }
    
    @staticmethod
    def _get_financing_cash_flows(db: Session, from_date: date, to_date: date) -> Dict[str, Any]:
        """Get cash flows from financing activities"""
        # This is a placeholder with demo data
        # In a real implementation, this would analyze equity and loan accounts
        
        # For demonstration, we'll return placeholder data
        return {
            'total': Decimal('50000.00'),
            'items': [
                {'description': 'Proceeds from Bank Loan', 'amount': Decimal('50000.00')}
            ]
        }
    
    @staticmethod
    def _get_cash_balance(db: Session, as_of_date: date) -> Decimal:
        """Get cash account balance as of a specific date"""
        # Get all cash accounts
        cash_accounts = db.query(Account).filter(
            Account.code.like('110%'),  # Assuming 110x are cash accounts
            Account.account_type == AccountType.ASSET
        ).all()
        
        if not cash_accounts:
            return Decimal('0.00')
        
        cash_account_ids = [account.id for account in cash_accounts]
        
        # Get all posted journal entries up to the as_of_date
        entries = db.query(JournalEntry).filter(
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= as_of_date
        ).all()
        
        if not entries:
            return Decimal('0.00')
        
        entry_ids = [entry.id for entry in entries]
        
        # Get sum of journal entry lines for cash accounts
        total_cash = db.query(
            func.sum(JournalEntryLine.debit_amount - JournalEntryLine.credit_amount)
        ).filter(
            JournalEntryLine.journal_entry_id.in_(entry_ids),
            JournalEntryLine.account_id.in_(cash_account_ids)
        ).scalar() or Decimal('0.00')
        
        return total_cash