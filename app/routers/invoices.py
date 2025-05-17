# File: app/routers/invoices.py (continued)
"""
API routes for managing invoices (both AP and AR)
"""
import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ap_models import APInvoice, APInvoiceItem, APInvoiceStatus
from app.models.ar_models import ARInvoice, ARInvoiceItem, ARInvoiceStatus
from app.schemas import ap_schemas, ar_schemas
from app.services.ap_service import APService
from app.services.ar_service import ARService

router = APIRouter(
    tags=["invoices"],
    responses={404: {"description": "Not found"}},
)

# AP Invoice endpoints
@router.post("/ap/invoices", response_model=ap_schemas.APInvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_ap_invoice(
    invoice: ap_schemas.APInvoiceCreate, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    # Check if vendor exists
    from app.models.ap_models import Vendor
    vendor = db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Calculate totals
    subtotal, tax_amount, total_amount = APService.calculate_invoice_totals(invoice.items)
    
    # Generate invoice number
    invoice_number = APService.generate_invoice_number()
    
    # Create invoice
    db_invoice = APInvoice(
        invoice_number=invoice_number,
        vendor_id=invoice.vendor_id,
        vendor_invoice_number=invoice.vendor_invoice_number,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        description=invoice.description,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=APInvoiceStatus.DRAFT,
        currency_code=invoice.currency_code,
        created_by=current_user
    )
    
    db.add(db_invoice)
    db.flush()  # Get ID without committing
    
    # Create invoice items
    for item in invoice.items:
        item_subtotal = item.quantity * item.unit_price
        item_tax = item_subtotal * (item.tax_rate / 100)
        item_total = item_subtotal + item_tax
        
        db_item = APInvoiceItem(
            invoice_id=db_invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            tax_amount=item_tax,
            total_amount=item_total,
            account_id=item.account_id
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

@router.get("/ap/invoices", response_model=List[ap_schemas.APInvoiceResponse])
def list_ap_invoices(
    skip: int = 0, 
    limit: int = 50,
    vendor_id: Optional[uuid.UUID] = None,
    status: Optional[APInvoiceStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(APInvoice)
    
    if vendor_id:
        query = query.filter(APInvoice.vendor_id == vendor_id)
        
    if status:
        query = query.filter(APInvoice.status == status)
        
    if from_date:
        query = query.filter(APInvoice.issue_date >= from_date)
        
    if to_date:
        query = query.filter(APInvoice.issue_date <= to_date)
        
    return query.order_by(APInvoice.issue_date.desc()).offset(skip).limit(limit).all()

@router.get("/ap/invoices/{invoice_id}", response_model=ap_schemas.APInvoiceResponse)
def get_ap_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.query(APInvoice).filter(APInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.post("/ap/invoices/{invoice_id}/approve", response_model=ap_schemas.APInvoiceResponse)
def approve_ap_invoice(
    invoice_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    invoice = db.query(APInvoice).filter(APInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status != APInvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Invoice is already {invoice.status}")
    
    # Create journal entry
    journal_entry = APService.create_journal_entry_for_invoice(db, invoice, current_user)
    
    # Update invoice status
    invoice.status = APInvoiceStatus.APPROVED
    invoice.journal_entry_id = journal_entry.id
    
    db.commit()
    db.refresh(invoice)
    return invoice

@router.post("/ap/invoices/{invoice_id}/void", response_model=ap_schemas.APInvoiceResponse)
def void_ap_invoice(
    invoice_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    invoice = db.query(APInvoice).filter(APInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status not in [APInvoiceStatus.DRAFT, APInvoiceStatus.APPROVED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot void invoice with status {invoice.status}"
        )
    
    if invoice.journal_entry_id:
        # TODO: Create reversing journal entry
        pass
    
    invoice.status = APInvoiceStatus.VOID
    
    db.commit()
    db.refresh(invoice)
    return invoice

# AR Invoice endpoints
@router.post("/ar/invoices", response_model=ar_schemas.ARInvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_ar_invoice(
    invoice: ar_schemas.ARInvoiceCreate, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    # Check if customer exists
    from app.models.ar_models import Customer
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Calculate totals
    subtotal, tax_amount, total_amount = ARService.calculate_invoice_totals(invoice.items)
    
    # Check credit limit if customer has one
    if customer.credit_limit > 0:
        within_limit, available_credit = ARService.check_credit_limit(
            db, invoice.customer_id, total_amount
        )
        if not within_limit:
            raise HTTPException(
                status_code=400, 
                detail=f"Invoice exceeds customer credit limit. Available credit: {available_credit}"
            )
    
    # Generate invoice number
    invoice_number = ARService.generate_invoice_number()
    
    # Create invoice
    db_invoice = ARInvoice(
        invoice_number=invoice_number,
        customer_id=invoice.customer_id,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        description=invoice.description,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=ARInvoiceStatus.DRAFT,
        currency_code=invoice.currency_code,
        created_by=current_user
    )
    
    db.add(db_invoice)
    db.flush()  # Get ID without committing
    
    # Create invoice items
    for item in invoice.items:
        item_subtotal = item.quantity * item.unit_price
        item_tax = item_subtotal * (item.tax_rate / 100)
        item_total = item_subtotal + item_tax
        
        db_item = ARInvoiceItem(
            invoice_id=db_invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            tax_amount=item_tax,
            total_amount=item_total,
            account_id=item.account_id
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

@router.get("/ar/invoices", response_model=List[ar_schemas.ARInvoiceResponse])
def list_ar_invoices(
    skip: int = 0, 
    limit: int = 50,
    customer_id: Optional[uuid.UUID] = None,
    status: Optional[ARInvoiceStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ARInvoice)
    
    if customer_id:
        query = query.filter(ARInvoice.customer_id == customer_id)
        
    if status:
        query = query.filter(ARInvoice.status == status)
        
    if from_date:
        query = query.filter(ARInvoice.issue_date >= from_date)
        
    if to_date:
        query = query.filter(ARInvoice.issue_date <= to_date)
        
    return query.order_by(ARInvoice.issue_date.desc()).offset(skip).limit(limit).all()

@router.get("/ar/invoices/{invoice_id}", response_model=ar_schemas.ARInvoiceResponse)
def get_ar_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)):
    invoice = db.query(ARInvoice).filter(ARInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.post("/ar/invoices/{invoice_id}/approve", response_model=ar_schemas.ARInvoiceResponse)
def approve_ar_invoice(
    invoice_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    invoice = db.query(ARInvoice).filter(ARInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status != ARInvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Invoice is already {invoice.status}")
    
    # Create journal entry
    journal_entry = ARService.create_journal_entry_for_invoice(db, invoice, current_user)
    
    # Update invoice status
    invoice.status = ARInvoiceStatus.APPROVED
    invoice.journal_entry_id = journal_entry.id
    
    db.commit()
    db.refresh(invoice)
    return invoice

@router.post("/ar/invoices/{invoice_id}/void", response_model=ar_schemas.ARInvoiceResponse)
def void_ar_invoice(
    invoice_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    invoice = db.query(ARInvoice).filter(ARInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if invoice.status not in [ARInvoiceStatus.DRAFT, ARInvoiceStatus.APPROVED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot void invoice with status {invoice.status}"
        )
    
    if invoice.journal_entry_id:
        # TODO: Create reversing journal entry
        pass
    
    invoice.status = ARInvoiceStatus.VOID
    
    db.commit()
    db.refresh(invoice)
    return invoice