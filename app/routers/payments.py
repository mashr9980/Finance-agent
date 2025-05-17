# File: app/routers/payments.py
"""
API routes for managing payments (both AP and AR)
"""
import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ap_models import APInvoiceStatus, APPayment, APInvoicePayment, APPaymentStatus, APInvoice
from app.models.ar_models import ARInvoiceStatus, ARPayment, ARInvoicePayment, ARPaymentStatus, ARInvoice
from app.schemas import ap_schemas, ar_schemas
from app.services.ap_service import APService
from app.services.ar_service import ARService

router = APIRouter(
    tags=["payments"],
    responses={404: {"description": "Not found"}},
)

# AP Payment endpoints
@router.post("/ap/payments", response_model=ap_schemas.APPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_ap_payment(
    payment: ap_schemas.APPaymentCreate, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    # Check if vendor exists
    from app.models.ap_models import Vendor
    vendor = db.query(Vendor).filter(Vendor.id == payment.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Validate invoices and payment amounts
    total_applied = sum(p.amount_applied for p in payment.invoice_payments)
    if total_applied != payment.amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Sum of invoice payments ({total_applied}) does not match payment amount ({payment.amount})"
        )
    
    # Verify invoices exist and belong to the vendor
    invoice_ids = [p.invoice_id for p in payment.invoice_payments]
    invoices = db.query(APInvoice).filter(
        APInvoice.id.in_(invoice_ids),
        APInvoice.vendor_id == payment.vendor_id,
        APInvoice.status.in_([
            APInvoiceStatus.APPROVED, 
            APInvoiceStatus.PARTIALLY_PAID,
            APInvoiceStatus.OVERDUE
        ])
    ).all()
    
    if len(invoices) != len(invoice_ids):
        raise HTTPException(
            status_code=400, 
            detail="One or more invoices are invalid or do not belong to this vendor"
        )
    
    # Verify payment amounts don't exceed invoice balances
    for inv_payment in payment.invoice_payments:
        invoice = next((i for i in invoices if i.id == inv_payment.invoice_id), None)
        if invoice:
            outstanding = invoice.total_amount - invoice.paid_amount
            if inv_payment.amount_applied > outstanding:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Payment amount ({inv_payment.amount_applied}) exceeds invoice outstanding balance ({outstanding})"
                )
    
    # Generate payment number
    payment_number = APService.generate_payment_number()
    
    # Create payment
    db_payment = APPayment(
        payment_number=payment_number,
        vendor_id=payment.vendor_id,
        payment_date=payment.payment_date,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference=payment.reference,
        description=payment.description,
        status=APPaymentStatus.DRAFT,
        currency_code=payment.currency_code,
        bank_account_id=payment.bank_account_id,
        created_by=current_user
    )
    
    db.add(db_payment)
    db.flush()  # Get ID without committing
    
    # Create payment allocations
    for inv_payment in payment.invoice_payments:
        db_inv_payment = APInvoicePayment(
            payment_id=db_payment.id,
            invoice_id=inv_payment.invoice_id,
            amount_applied=inv_payment.amount_applied
        )
        db.add(db_inv_payment)
    
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.get("/ap/payments", response_model=List[ap_schemas.APPaymentResponse])
def list_ap_payments(
    skip: int = 0, 
    limit: int = 50,
    vendor_id: Optional[uuid.UUID] = None,
    status: Optional[APPaymentStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(APPayment)
    
    if vendor_id:
        query = query.filter(APPayment.vendor_id == vendor_id)
        
    if status:
        query = query.filter(APPayment.status == status)
        
    if from_date:
        query = query.filter(APPayment.payment_date >= from_date)
        
    if to_date:
        query = query.filter(APPayment.payment_date <= to_date)
        
    return query.order_by(APPayment.payment_date.desc()).offset(skip).limit(limit).all()

@router.get("/ap/payments/{payment_id}", response_model=ap_schemas.APPaymentResponse)
def get_ap_payment(payment_id: uuid.UUID, db: Session = Depends(get_db)):
    payment = db.query(APPayment).filter(APPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.post("/ap/payments/{payment_id}/process", response_model=ap_schemas.APPaymentResponse)
def process_ap_payment(
    payment_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    payment = db.query(APPayment).filter(APPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != APPaymentStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Payment is already {payment.status}")
    
    # Create journal entry
    journal_entry = APService.create_journal_entry_for_payment(db, payment, current_user)
    
    # Update payment status
    payment.status = APPaymentStatus.PROCESSED
    payment.journal_entry_id = journal_entry.id
    
    # Update invoice paid amounts and statuses
    for payment_line in payment.invoice_payments:
        APService.update_invoice_status(db, payment_line.invoice_id)
    
    db.commit()
    db.refresh(payment)
    return payment

@router.post("/ap/payments/{payment_id}/cancel", response_model=ap_schemas.APPaymentResponse)
def cancel_ap_payment(
    payment_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    payment = db.query(APPayment).filter(APPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status not in [APPaymentStatus.DRAFT, APPaymentStatus.APPROVED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel payment with status {payment.status}"
        )
    
    payment.status = APPaymentStatus.CANCELLED
    
    db.commit()
    db.refresh(payment)
    return payment

# AR Payment endpoints
@router.post("/ar/payments", response_model=ar_schemas.ARPaymentResponse, status_code=status.HTTP_201_CREATED)
def create_ar_payment(
    payment: ar_schemas.ARPaymentCreate, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    # Check if customer exists
    from app.models.ar_models import Customer
    customer = db.query(Customer).filter(Customer.id == payment.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Validate invoices and payment amounts
    total_applied = sum(p.amount_applied for p in payment.invoice_payments)
    if total_applied != payment.amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Sum of invoice payments ({total_applied}) does not match payment amount ({payment.amount})"
        )
    
    # Verify invoices exist and belong to the customer
    invoice_ids = [p.invoice_id for p in payment.invoice_payments]
    invoices = db.query(ARInvoice).filter(
        ARInvoice.id.in_(invoice_ids),
        ARInvoice.customer_id == payment.customer_id,
        ARInvoice.status.in_([
            ARInvoiceStatus.APPROVED, 
            ARInvoiceStatus.PARTIALLY_PAID,
            ARInvoiceStatus.OVERDUE
        ])
    ).all()
    
    if len(invoices) != len(invoice_ids):
        raise HTTPException(
            status_code=400, 
            detail="One or more invoices are invalid or do not belong to this customer"
        )
    
    # Verify payment amounts don't exceed invoice balances
    for inv_payment in payment.invoice_payments:
        invoice = next((i for i in invoices if i.id == inv_payment.invoice_id), None)
        if invoice:
            outstanding = invoice.total_amount - invoice.paid_amount
            if inv_payment.amount_applied > outstanding:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Payment amount ({inv_payment.amount_applied}) exceeds invoice outstanding balance ({outstanding})"
                )
    
    # Generate payment number
    payment_number = ARService.generate_payment_number()
    
    # Create payment
    db_payment = ARPayment(
        payment_number=payment_number,
        customer_id=payment.customer_id,
        payment_date=payment.payment_date,
        amount=payment.amount,
        payment_method=payment.payment_method,
        reference=payment.reference,
        description=payment.description,
        status=ARPaymentStatus.DRAFT,
        currency_code=payment.currency_code,
        bank_account_id=payment.bank_account_id,
        created_by=current_user
    )
    
    db.add(db_payment)
    db.flush()  # Get ID without committing
    
    # Create payment allocations
    for inv_payment in payment.invoice_payments:
        db_inv_payment = ARInvoicePayment(
            payment_id=db_payment.id,
            invoice_id=inv_payment.invoice_id,
            amount_applied=inv_payment.amount_applied
        )
        db.add(db_inv_payment)
    
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.get("/ar/payments", response_model=List[ar_schemas.ARPaymentResponse])
def list_ar_payments(
    skip: int = 0, 
    limit: int = 50,
    customer_id: Optional[uuid.UUID] = None,
    status: Optional[ARPaymentStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ARPayment)
    
    if customer_id:
        query = query.filter(ARPayment.customer_id == customer_id)
        
    if status:
        query = query.filter(ARPayment.status == status)
        
    if from_date:
        query = query.filter(ARPayment.payment_date >= from_date)
        
    if to_date:
        query = query.filter(ARPayment.payment_date <= to_date)
        
    return query.order_by(ARPayment.payment_date.desc()).offset(skip).limit(limit).all()

@router.get("/ar/payments/{payment_id}", response_model=ar_schemas.ARPaymentResponse)
def get_ar_payment(payment_id: uuid.UUID, db: Session = Depends(get_db)):
    payment = db.query(ARPayment).filter(ARPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.post("/ar/payments/{payment_id}/process", response_model=ar_schemas.ARPaymentResponse)
def process_ar_payment(
    payment_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    payment = db.query(ARPayment).filter(ARPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != ARPaymentStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Payment is already {payment.status}")
    
    # Create journal entry
    journal_entry = ARService.create_journal_entry_for_payment(db, payment, current_user)
    
    # Update payment status
    payment.status = ARPaymentStatus.PROCESSED
    payment.journal_entry_id = journal_entry.id
    
    # Update invoice paid amounts and statuses
    for payment_line in payment.invoice_payments:
        ARService.update_invoice_status(db, payment_line.invoice_id)
    
    db.commit()
    db.refresh(payment)
    return payment

@router.post("/ar/payments/{payment_id}/cancel", response_model=ar_schemas.ARPaymentResponse)
def cancel_ar_payment(
    payment_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    payment = db.query(ARPayment).filter(ARPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status not in [ARPaymentStatus.DRAFT, ARPaymentStatus.APPROVED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel payment with status {payment.status}"
        )
    
    payment.status = ARPaymentStatus.CANCELLED
    
    db.commit()
    db.refresh(payment)
    return payment