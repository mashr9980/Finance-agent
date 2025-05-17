# File: app/services/ar_service.py
"""
Business logic for the Accounts Receivable module
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
import sqlalchemy

from app.models.ar_models import (
    Customer, ARInvoice, ARInvoiceItem, ARPayment, 
    ARInvoicePayment, ARInvoiceStatus, ARPaymentStatus
)
from app.models.gl_models import JournalEntry, JournalEntryLine, JournalEntryStatus, AccountType, Account
from app.schemas import ar_schemas

class ARService:
    @staticmethod
    def generate_invoice_number() -> str:
        """Generate a unique AR invoice number"""
        return f"AR-INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    @staticmethod
    def generate_payment_number() -> str:
        """Generate a unique AR payment number"""
        return f"AR-PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    @staticmethod
    def calculate_invoice_totals(items: List[ar_schemas.ARInvoiceItemCreate]) -> tuple:
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
        invoice: ARInvoice,
        created_by: str
    ) -> JournalEntry:
        """Create a journal entry for an AR invoice"""
        from app.services.gl_service import GLService
        
        # Get the customer and its associated asset account
        customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        receivable_account_id = customer.account_id
        if not receivable_account_id:
            # Use default accounts receivable account if customer doesn't have specific one
            default_ar_account = db.query(Account).filter(
                Account.code.startswith("1200"),  # Assuming 1200 is the AR account code
                Account.account_type == AccountType.ASSET
            ).first()
            
            if not default_ar_account:
                raise HTTPException(
                    status_code=400, 
                    detail="No default Accounts Receivable account found. Please configure the system."
                )
            
            receivable_account_id = default_ar_account.id
        
        # Create journal entry
        je_description = f"AR Invoice {invoice.invoice_number} for {customer.name}"
        
        # Prepare journal entry lines
        lines = []
        
        # Debit the receivable account for the total amount
        lines.append({
            "account_id": receivable_account_id,
            "description": f"Invoice {invoice.invoice_number}",
            "debit_amount": invoice.total_amount,
            "credit_amount": Decimal("0.00")
        })
        
        # Credit the revenue/liability accounts from invoice items
        for item in invoice.items:
            lines.append({
                "account_id": item.account_id,
                "description": item.description,
                "credit_amount": item.total_amount,
                "debit_amount": Decimal("0.00")
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
        payment: ARPayment,
        created_by: str
    ) -> JournalEntry:
        """Create a journal entry for an AR payment"""
        from app.services.gl_service import GLService
        
        # Get the customer and its associated asset account
        customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        receivable_account_id = customer.account_id
        if not receivable_account_id:
            # Use default accounts receivable account if customer doesn't have specific one
            default_ar_account = db.query(Account).filter(
                Account.code.startswith("1200"),  # Assuming 1200 is the AR account code
                Account.account_type == AccountType.ASSET
            ).first()
            
            if not default_ar_account:
                raise HTTPException(
                    status_code=400, 
                    detail="No default Accounts Receivable account found. Please configure the system."
                )
            
            receivable_account_id = default_ar_account.id
        
        # Create journal entry
        je_description = f"AR Payment {payment.payment_number} from {customer.name}"
        
        # Prepare journal entry lines
        lines = []
        
        # Credit the receivable account for the payment amount
        lines.append({
            "account_id": receivable_account_id,
            "description": f"Payment {payment.payment_number}",
            "credit_amount": payment.amount,
            "debit_amount": Decimal("0.00")
        })
        
        # Debit the bank account
        lines.append({
            "account_id": payment.bank_account_id,
            "description": f"Payment {payment.payment_number} from {customer.name}",
            "debit_amount": payment.amount,
            "credit_amount": Decimal("0.00")
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
        invoice = db.query(ARInvoice).filter(ARInvoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        # Calculate total paid amount
        total_paid = db.query(ARInvoicePayment).filter(
            ARInvoicePayment.invoice_id == invoice_id
        ).with_entities(
            sqlalchemy.func.sum(ARInvoicePayment.amount_applied)
        ).scalar() or Decimal("0.00")
        
        # Update invoice paid amount
        invoice.paid_amount = total_paid
        
        # Update status based on paid amount
        if total_paid >= invoice.total_amount:
            invoice.status = ARInvoiceStatus.PAID
        elif total_paid > 0:
            invoice.status = ARInvoiceStatus.PARTIALLY_PAID
        elif invoice.due_date < date.today():
            invoice.status = ARInvoiceStatus.OVERDUE
        
        db.commit()
    
    @staticmethod
    def check_credit_limit(db: Session, customer_id: uuid.UUID, new_invoice_amount: Optional[Decimal] = None) -> tuple:
        """Check if a new invoice would exceed customer credit limit"""
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # If customer has no credit limit, always allow
        if customer.credit_limit <= 0:
            return True, Decimal("0.00")
        
        # Calculate total outstanding amount
        outstanding = db.query(ARInvoice).filter(
            ARInvoice.customer_id == customer_id,
            ARInvoice.status.in_([
                ARInvoiceStatus.APPROVED,
                ARInvoiceStatus.PARTIALLY_PAID,
                ARInvoiceStatus.OVERDUE
            ])
        ).with_entities(
            sqlalchemy.func.sum(ARInvoice.total_amount - ARInvoice.paid_amount)
        ).scalar() or Decimal("0.00")
        
        # Add new invoice amount if provided
        if new_invoice_amount:
            total_exposure = outstanding + new_invoice_amount
        else:
            total_exposure = outstanding
        
        # Check if within limit
        is_within_limit = total_exposure <= customer.credit_limit
        available_credit = customer.credit_limit - outstanding
        
        return is_within_limit, available_credit
    
    @staticmethod
    def generate_aging_report(db: Session, as_of_date: Optional[date] = None) -> ar_schemas.ARAgingReport:
        """Generate accounts receivable aging report"""
        if not as_of_date:
            as_of_date = date.today()
        
        # Define aging buckets (current, 1-30, 31-60, 61-90, 90+)
        bucket_ranges = [
            (0, 30),
            (31, 60),
            (61, 90),
            (91, None)  # 91+ days
        ]
        
        # Get all customers with outstanding invoices
        customers = db.query(Customer).filter(
            Customer.id.in_(
                db.query(ARInvoice.customer_id).filter(
                    ARInvoice.status.in_([
                        ARInvoiceStatus.APPROVED,
                        ARInvoiceStatus.PARTIALLY_PAID,
                        ARInvoiceStatus.OVERDUE
                    ])
                ).distinct()
            )
        ).all()
        
        # Initialize report
        customer_aging_list = []
        total_outstanding = Decimal("0.00")
        bucket_totals = [Decimal("0.00") for _ in range(len(bucket_ranges))]
        
        for customer in customers:
            # Get outstanding invoices for this customer
            invoices = db.query(ARInvoice).filter(
                ARInvoice.customer_id == customer.id,
                ARInvoice.status.in_([
                    ARInvoiceStatus.APPROVED,
                    ARInvoiceStatus.PARTIALLY_PAID,
                    ARInvoiceStatus.OVERDUE
                ])
            ).all()
            
            # Skip customer if no outstanding invoices
            if not invoices:
                continue
            
            # Initialize aging buckets for this customer
            customer_buckets = [Decimal("0.00") for _ in range(len(bucket_ranges))]
            customer_total = Decimal("0.00")
            
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
                
                customer_buckets[bucket_index] += outstanding_amount
                customer_total += outstanding_amount
                bucket_totals[bucket_index] += outstanding_amount
                total_outstanding += outstanding_amount
            
            # Create customer aging record
            customer_aging = ar_schemas.ARCustomerAging(
                customer_id=customer.id,
                customer_code=customer.code,
                customer_name=customer.name,
                total_outstanding=customer_total,
                buckets=[
                    ar_schemas.ARAgingBucket(
                        range_start=start,
                        range_end=end,
                        amount=customer_buckets[i]
                    )
                    for i, (start, end) in enumerate(bucket_ranges)
                ]
            )
            
            customer_aging_list.append(customer_aging)
        
        # Create final report
        return ar_schemas.ARAgingReport(
            as_of_date=as_of_date,
            customers=customer_aging_list,
            total_amount=total_outstanding,
            bucket_totals=[
                ar_schemas.ARAgingBucket(
                    range_start=start,
                    range_end=end,
                    amount=bucket_totals[i]
                )
                for i, (start, end) in enumerate(bucket_ranges)
            ]
        )