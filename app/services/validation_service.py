# File: app/services/validation_service.py
"""
Business logic for financial data validation
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any, Tuple, Union
import uuid
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gl_models import Account, AccountType, JournalEntry, FiscalPeriod, JournalEntryStatus
from app.models.ap_models import Vendor, APInvoice, APInvoiceStatus
from app.models.ar_models import Customer, ARInvoice, ARInvoiceStatus
from app.schemas import gl_schemas, ap_schemas, ar_schemas
from app.services.fiscal_service import FiscalService

class ValidationService:
    @staticmethod
    def validate_journal_entry(
        db: Session, 
        entry: Union[gl_schemas.JournalEntryCreate, JournalEntry],
        is_model: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a journal entry with comprehensive business rules
        
        Args:
            db: Database session
            entry: Journal entry to validate (schema or model)
            is_model: Whether entry is a database model (True) or schema (False)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get the lines depending on whether entry is a model or schema
        if is_model:
            lines = entry.lines
            entry_date = entry.entry_date
        else:
            lines = entry.lines
            entry_date = entry.entry_date
        
        # 1. Check for empty lines
        if not lines or len(lines) < 2:
            return False, "Journal entry must have at least two lines"
        
        # 2. Verify all accounts exist and are active
        account_ids = [line.account_id for line in lines]
        accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
        
        if len(accounts) != len(set(account_ids)):
            return False, "One or more accounts not found"
        
        # Check if all accounts are active
        inactive_accounts = [acc.code for acc in accounts if not acc.is_active]
        if inactive_accounts:
            return False, f"Cannot use inactive accounts: {', '.join(inactive_accounts)}"
        
        # 3. Verify debits = credits
        total_debits = sum(line.debit_amount for line in lines)
        total_credits = sum(line.credit_amount for line in lines)
        
        if abs(total_debits - total_credits) > Decimal('0.01'):
            return False, f"Journal entry not balanced. Debits: {total_debits}, Credits: {total_credits}"
        
        # 4. Check if the entry date is within an open fiscal period
        period = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date <= entry_date,
            FiscalPeriod.end_date >= entry_date
        ).first()
        
        if not period:
            return False, f"No fiscal period found for date {entry_date}"
        
        if period.is_closed:
            return False, f"Cannot post to closed fiscal period: {period.name}"
        
        # 5. Verify each line has either a debit or credit amount, but not both
        for i, line in enumerate(lines):
            if is_model:
                debit = line.debit_amount
                credit = line.credit_amount
            else:
                debit = line.debit_amount
                credit = line.credit_amount
                
            if debit > 0 and credit > 0:
                return False, f"Line {i+1} cannot have both debit and credit amounts"
            
            if debit == 0 and credit == 0:
                return False, f"Line {i+1} must have either a debit or credit amount"
        
        # All validations passed
        return True, None
    
    @staticmethod
    def validate_ap_invoice(
        db: Session, 
        invoice: ap_schemas.APInvoiceCreate,
        vendor_id: uuid.UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an AP invoice with comprehensive business rules
        
        Args:
            db: Database session
            invoice: Invoice to validate
            vendor_id: Vendor ID for additional validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # 1. Check vendor exists and is active
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if not vendor:
            return False, "Vendor not found"
        
        if vendor.status != "ACTIVE":
            return False, f"Vendor is not active. Current status: {vendor.status}"
        
        # 2. Validate invoice dates
        today = date.today()
        
        # Don't allow invoice dates in the future
        if invoice.issue_date > today:
            return False, "Invoice issue date cannot be in the future"
        
        # Due date should be after or equal to issue date
        if invoice.due_date < invoice.issue_date:
            return False, "Due date cannot be before issue date"
        
        # 3. Check fiscal period
        period = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date <= invoice.issue_date,
            FiscalPeriod.end_date >= invoice.issue_date
        ).first()
        
        if not period:
            return False, f"No fiscal period found for date {invoice.issue_date}"
        
        if period.is_closed:
            return False, f"Cannot post to closed fiscal period: {period.name}"
        
        # 4. Validate invoice items
        if not invoice.items or len(invoice.items) == 0:
            return False, "Invoice must have at least one item"
        
        for i, item in enumerate(invoice.items):
            # Verify account exists and is an expense or asset
            account = db.query(Account).filter(Account.id == item.account_id).first()
            if not account:
                return False, f"Account not found for item {i+1}"
            
            if account.account_type not in [AccountType.EXPENSE, AccountType.ASSET]:
                return False, f"Item {i+1} must use an expense or asset account"
            
            # Check quantities and amounts
            if item.quantity <= 0:
                return False, f"Item {i+1} quantity must be positive"
                
            if item.unit_price <= 0:
                return False, f"Item {i+1} unit price must be positive"
                
            if item.tax_rate < 0:
                return False, f"Item {i+1} tax rate cannot be negative"
        
        # 5. Check for duplicate vendor invoice number if provided
        if invoice.vendor_invoice_number:
            existing = db.query(APInvoice).filter(
                APInvoice.vendor_id == vendor_id,
                APInvoice.vendor_invoice_number == invoice.vendor_invoice_number,
                APInvoice.status != APInvoiceStatus.VOID
            ).first()
            
            if existing:
                return False, f"Invoice with vendor invoice number {invoice.vendor_invoice_number} already exists"
        
        # All validations passed
        return True, None
    
    @staticmethod
    def validate_ar_invoice(
        db: Session, 
        invoice: ar_schemas.ARInvoiceCreate,
        customer_id: uuid.UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an AR invoice with comprehensive business rules
        
        Args:
            db: Database session
            invoice: Invoice to validate
            customer_id: Customer ID for additional validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # 1. Check customer exists and is active
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return False, "Customer not found"
        
        if customer.status != "ACTIVE":
            return False, f"Customer is not active. Current status: {customer.status}"
        
        # 2. Validate invoice dates
        today = date.today()
        
        # Allow issue dates up to 7 days in the future for AR (for dated invoices)
        if invoice.issue_date > today + timedelta(days=7):
            return False, "Invoice issue date cannot be more than 7 days in the future"
        
        # Due date should be after or equal to issue date
        if invoice.due_date < invoice.issue_date:
            return False, "Due date cannot be before issue date"
        
        # 3. Check fiscal period
        period = db.query(FiscalPeriod).filter(
            FiscalPeriod.start_date <= invoice.issue_date,
            FiscalPeriod.end_date >= invoice.issue_date
        ).first()
        
        if not period:
            return False, f"No fiscal period found for date {invoice.issue_date}"
        
        if period.is_closed:
            return False, f"Cannot post to closed fiscal period: {period.name}"
        
        # 4. Validate invoice items
        if not invoice.items or len(invoice.items) == 0:
            return False, "Invoice must have at least one item"
        
        for i, item in enumerate(invoice.items):
            # Verify account exists and is a revenue
            account = db.query(Account).filter(Account.id == item.account_id).first()
            if not account:
                return False, f"Account not found for item {i+1}"
            
            if account.account_type != AccountType.REVENUE:
                return False, f"Item {i+1} must use a revenue account"
            
            # Check quantities and amounts
            if item.quantity <= 0:
                return False, f"Item {i+1} quantity must be positive"
                
            if item.unit_price <= 0:
                return False, f"Item {i+1} unit price must be positive"
                
            if item.tax_rate < 0:
                return False, f"Item {i+1} tax rate cannot be negative"
        
        # 5. Check credit limit
        if customer.credit_limit > 0:
            # Calculate this invoice amount
            subtotal, tax_amount, total_amount = ValidationService._calculate_invoice_total(invoice.items)
            
            # Get total outstanding
            outstanding = db.query(ARInvoice).filter(
                ARInvoice.customer_id == customer_id,
                ARInvoice.status.in_([
                    ARInvoiceStatus.APPROVED,
                    ARInvoiceStatus.PARTIALLY_PAID,
                    ARInvoiceStatus.OVERDUE
                ])
            ).with_entities(
                func.sum(ARInvoice.total_amount - ARInvoice.paid_amount)
            ).scalar() or Decimal("0.00")
            
            # Calculate total exposure
            total_exposure = outstanding + total_amount
            
            # Check if within limit
            if total_exposure > customer.credit_limit:
                available_credit = customer.credit_limit - outstanding
                return False, f"Invoice would exceed credit limit. Available credit: {available_credit}"
        
        # All validations passed
        return True, None
    
    @staticmethod
    def _calculate_invoice_total(items: List[Union[ar_schemas.ARInvoiceItemCreate, ap_schemas.APInvoiceItemCreate]]) -> Tuple[Decimal, Decimal, Decimal]:
        """Helper method to calculate invoice totals"""
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")
        
        for item in items:
            item_subtotal = item.quantity * item.unit_price
            item_tax = item_subtotal * item.tax_rate / Decimal("100.00")
            
            subtotal += item_subtotal
            tax_amount += item_tax
        
        total_amount = subtotal + tax_amount
        
        return subtotal.quantize(Decimal("0.01")), tax_amount.quantize(Decimal("0.01")), total_amount.quantize(Decimal("0.01"))