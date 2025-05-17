# File: app/services/ap_service.py
"""
Business logic for the Accounts Payable module
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
import sqlalchemy
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.ap_models import (
    Vendor, APInvoice, APInvoiceItem, APPayment, 
    APInvoicePayment, APInvoiceStatus, APPaymentStatus
)
from app.models.gl_models import Account, JournalEntry, JournalEntryLine, JournalEntryStatus, AccountType
from app.schemas import ap_schemas

class APService:
    @staticmethod
    def generate_invoice_number() -> str:
        """Generate a unique AP invoice number"""
        return f"AP-INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    @staticmethod
    def generate_payment_number() -> str:
        """Generate a unique AP payment number"""
        return f"AP-PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    @staticmethod
    def calculate_invoice_totals(items: List[ap_schemas.APInvoiceItemCreate]) -> tuple:
        """Calculate subtotal, tax amount and total for an invoice"""
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")
        
        for item in items:
            item_subtotal = item.quantity * item.unit_price
            item_tax = item_subtotal * item.tax_rate / Decimal("100.00")
            
            subtotal += item_subtotal
            tax_amount += item_tax
        
        total_amount = subtotal + tax_amount
        
        return subtotal.quantize(Decimal("0.01")), tax_amount.quantize(Decimal("0.01")), total_amount.quantize(Decimal("0.01"))
    
    @staticmethod
    def create_journal_entry_for_invoice(
        db: Session, 
        invoice: APInvoice,
        created_by: str
    ) -> JournalEntry:
        """Create a journal entry for an AP invoice"""
        from app.services.gl_service import GLService
        
        # Get the vendor and its associated liability account
        vendor = db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        
        liability_account_id = vendor.account_id
        if not liability_account_id:
            # Use default accounts payable account if vendor doesn't have specific one
            # This should be fetched from configuration in a real system
            default_ap_account = db.query(Account).filter(
                Account.code.startswith("2100"),  # Assuming 2100 is the AP account code
                Account.account_type == AccountType.LIABILITY
            ).first()
            
            if not default_ap_account:
                raise HTTPException(
                    status_code=400, 
                    detail="No default Accounts Payable account found. Please configure the system."
                )
            
            liability_account_id = default_ap_account.id
        
        # Create journal entry
        je_description = f"AP Invoice {invoice.invoice_number} for {vendor.name}"
        
        # Prepare journal entry lines
        lines = []
        
        # Credit the liability account for the total amount
        lines.append({
            "account_id": liability_account_id,
            "description": f"Invoice {invoice.invoice_number}",
            "credit_amount": invoice.total_amount,
            "debit_amount": Decimal("0.00")
        })
        
        # Debit the expense/asset accounts from invoice items
        for item in invoice.items:
            lines.append({
                "account_id": item.account_id,
                "description": item.description,
                "debit_amount": item.total_amount,
                "credit_amount": Decimal("0.00")
            })
        
        # Create journal entry using GLService
        journal_entry = GLService.create_journal_entry(
            db=db,
            description=je_description,
            entry_date=invoice.issue_date,
            lines=lines,
            created_by=created_by
        )
        
        return journal_entry
    
    @staticmethod
    def create_journal_entry_for_payment(
        db: Session, 
        payment: APPayment,
        created_by: str
    ) -> JournalEntry:
        """Create a journal entry for an AP payment"""
        from app.services.gl_service import GLService
        
        # Get the vendor and its associated liability account
        vendor = db.query(Vendor).filter(Vendor.id == payment.vendor_id).first()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
        
        liability_account_id = vendor.account_id
        if not liability_account_id:
            # Use default accounts payable account if vendor doesn't have specific one
            default_ap_account = db.query(Account).filter(
                Account.code.startswith("2100"),  # Assuming 2100 is the AP account code
                Account.account_type == AccountType.LIABILITY
            ).first()
            
            if not default_ap_account:
                raise HTTPException(
                    status_code=400, 
                    detail="No default Accounts Payable account found. Please configure the system."
                )
            
            liability_account_id = default_ap_account.id
        
        # Create journal entry
        je_description = f"AP Payment {payment.payment_number} to {vendor.name}"
        
        # Prepare journal entry lines
        lines = []
        
        # Debit the liability account for the payment amount
        lines.append({
            "account_id": liability_account_id,
            "description": f"Payment {payment.payment_number}",
            "debit_amount": payment.amount,
            "credit_amount": Decimal("0.00")
        })
        
        # Credit the bank account
        lines.append({
            "account_id": payment.bank_account_id,
            "description": f"Payment {payment.payment_number} to {vendor.name}",
            "credit_amount": payment.amount,
            "debit_amount": Decimal("0.00")
        })
        
        # Create journal entry using GLService
        journal_entry = GLService.create_journal_entry(
            db=db,
            description=je_description,
            entry_date=payment.payment_date,
            lines=lines,
            created_by=created_by
        )
        
        return journal_entry
    
    @staticmethod
    def update_invoice_status(db: Session, invoice_id: uuid.UUID) -> None:
        """Update invoice status based on payment status"""
        invoice = db.query(APInvoice).filter(APInvoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        # Calculate total paid amount
        total_paid = db.query(APInvoicePayment).filter(
            APInvoicePayment.invoice_id == invoice_id
        ).with_entities(
            sqlalchemy.func.sum(APInvoicePayment.amount_applied)
        ).scalar() or Decimal("0.00")
        
        # Update invoice paid amount
        invoice.paid_amount = total_paid
        
        # Update status based on paid amount
        if total_paid >= invoice.total_amount:
            invoice.status = APInvoiceStatus.PAID
        elif total_paid > 0:
            invoice.status = APInvoiceStatus.PARTIALLY_PAID
        elif invoice.due_date < date.today():
            invoice.status = APInvoiceStatus.OVERDUE
        
        db.commit()
    
    @staticmethod
    def generate_aging_report(db: Session, as_of_date: Optional[date] = None) -> ap_schemas.APAgingReport:
        """Generate accounts payable aging report"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Define aging buckets (current, 1-30, 31-60, 61-90, 90+)
        bucket_ranges = [
            (0, 30),
            (31, 60),
            (61, 90),
            (91, None)  # 91+ days
        ]
        
        # Get all vendors with outstanding invoices
        vendors = db.query(Vendor).filter(
            Vendor.id.in_(
                db.query(APInvoice.vendor_id).filter(
                    APInvoice.status.in_([
                        APInvoiceStatus.APPROVED,
                        APInvoiceStatus.PARTIALLY_PAID,
                        APInvoiceStatus.OVERDUE
                    ])
                ).distinct()
            )
        ).all()
        
        # Initialize report
        vendor_aging_list = []
        total_outstanding = Decimal("0.00")
        bucket_totals = [Decimal("0.00") for _ in range(len(bucket_ranges))]
        
        for vendor in vendors:
            # Get outstanding invoices for this vendor
            invoices = db.query(APInvoice).filter(
                APInvoice.vendor_id == vendor.id,
                APInvoice.status.in_([
                    APInvoiceStatus.APPROVED,
                    APInvoiceStatus.PARTIALLY_PAID,
                    APInvoiceStatus.OVERDUE
                ])
            ).all()
            
            # Skip vendor if no outstanding invoices
            if not invoices:
                continue
            
            # Initialize aging buckets for this vendor
            vendor_buckets = [Decimal("0.00") for _ in range(len(bucket_ranges))]
            vendor_total = Decimal("0.00")
            
            for invoice in invoices:
                outstanding_amount = invoice.total_amount - invoice.paid_amount
                days_outstanding = (as_of_date - invoice.due_date).days
                
                # Add to appropriate bucket
                bucket_index = 0
                for i, (start, end) in enumerate(bucket_ranges):
                    if end is None and days_outstanding >= start:
                        bucket_index = i
                        break
                    elif start <= days_outstanding <= end:
                        bucket_index = i
                        break
                
                vendor_buckets[bucket_index] += outstanding_amount
                vendor_total += outstanding_amount
                bucket_totals[bucket_index] += outstanding_amount
                total_outstanding += outstanding_amount
            
            # Create vendor aging record
            vendor_aging = ap_schemas.APVendorAging(
                vendor_id=vendor.id,
                vendor_code=vendor.code,
                vendor_name=vendor.name,
                total_outstanding=vendor_total,
                buckets=[
                    ap_schemas.APAgingBucket(
                        range_start=start,
                        range_end=end,
                        amount=vendor_buckets[i]
                    )
                    for i, (start, end) in enumerate(bucket_ranges)
                ]
            )
            
            vendor_aging_list.append(vendor_aging)
        
        # Create final report
        return ap_schemas.APAgingReport(
            as_of_date=as_of_date,
            vendors=vendor_aging_list,
            total_amount=total_outstanding,
            bucket_totals=[
                ap_schemas.APAgingBucket(
                    range_start=start,
                    range_end=end,
                    amount=bucket_totals[i]
                )
                for i, (start, end) in enumerate(bucket_ranges)
            ]
        )