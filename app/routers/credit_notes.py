# File: app/routers/credit_notes.py
"""
API routes for managing credit notes (both AP and AR)
"""
import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ap_models import APInvoice, APInvoiceItem, APInvoiceStatus, Vendor
from app.models.ar_models import ARInvoice, ARInvoiceItem, ARInvoiceStatus, Customer
from app.schemas import ap_schemas, ar_schemas
from app.services.ap_service import APService
from app.services.ar_service import ARService

router = APIRouter(
    tags=["credit_notes"],
    responses={404: {"description": "Not found"}},
)

# AP Credit Note endpoints
@router.post("/ap/credit-notes", response_model=ap_schemas.APInvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_ap_credit_note(
    credit_note: ap_schemas.APInvoiceCreate, 
    referenced_invoice_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    """
    Create a new Accounts Payable credit note.
    A credit note can be created with or without a reference to an existing invoice.
    """
    # Check if vendor exists
    vendor = db.query(Vendor).filter(Vendor.id == credit_note.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # If this credit note references an invoice, validate it
    referenced_invoice = None
    if referenced_invoice_id:
        referenced_invoice = db.query(APInvoice).filter(
            APInvoice.id == referenced_invoice_id,
            APInvoice.vendor_id == credit_note.vendor_id,
            APInvoice.status.in_([
                APInvoiceStatus.APPROVED, 
                APInvoiceStatus.PARTIALLY_PAID,
                APInvoiceStatus.OVERDUE,
                APInvoiceStatus.PAID
            ])
        ).first()
        
        if not referenced_invoice:
            raise HTTPException(
                status_code=404, 
                detail="Referenced invoice not found or not eligible for credit note"
            )
    
    # Calculate totals - for credit notes, the amounts will be negative
    subtotal, tax_amount, total_amount = APService.calculate_invoice_totals(credit_note.items)
    
    # Make amounts negative for credit notes
    subtotal = -abs(subtotal)
    tax_amount = -abs(tax_amount)
    total_amount = -abs(total_amount)
    
    # Generate credit note number
    credit_note_number = APService.generate_invoice_number().replace("AP-INV", "AP-CN")
    
    # Create credit note as a special type of invoice
    db_credit_note = APInvoice(
        invoice_number=credit_note_number,
        vendor_id=credit_note.vendor_id,
        vendor_invoice_number=credit_note.vendor_invoice_number,
        issue_date=credit_note.issue_date,
        due_date=credit_note.due_date,
        description=f"Credit Note: {credit_note.description or ''}",
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=APInvoiceStatus.DRAFT,
        currency_code=credit_note.currency_code,
        created_by=current_user,
        # Store reference to original invoice if provided
        reference=str(referenced_invoice_id) if referenced_invoice_id else None
    )
    
    db.add(db_credit_note)
    db.flush()  # Get ID without committing
    
    # Create credit note items with negative amounts
    for item in credit_note.items:
        item_subtotal = -(item.quantity * item.unit_price)
        item_tax = -(item_subtotal * (item.tax_rate / 100))
        item_total = item_subtotal + item_tax
        
        db_item = APInvoiceItem(
            invoice_id=db_credit_note.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=-abs(item.unit_price),  # Store as negative
            tax_rate=item.tax_rate,
            tax_amount=item_tax,
            total_amount=item_total,
            account_id=item.account_id
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_credit_note)
    return db_credit_note

@router.post("/ap/credit-notes/{credit_note_id}/approve", response_model=ap_schemas.APInvoiceResponse)
def approve_ap_credit_note(
    credit_note_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    """
    Approve an AP credit note and create the corresponding journal entry.
    Journal entry will have debits and credits reversed compared to normal invoices.
    """
    credit_note = db.query(APInvoice).filter(APInvoice.id == credit_note_id).first()
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    
    if credit_note.status != APInvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Credit note is already {credit_note.status}")
    
    # Create journal entry - credit note has opposite accounting effect of invoice
    journal_entry = APService.create_journal_entry_for_invoice(db, credit_note, current_user)
    
    # Update credit note status
    credit_note.status = APInvoiceStatus.APPROVED
    credit_note.journal_entry_id = journal_entry.id
    
    db.commit()
    db.refresh(credit_note)
    return credit_note

# AR Credit Note endpoints
@router.post("/ar/credit-notes", response_model=ar_schemas.ARInvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_ar_credit_note(
    credit_note: ar_schemas.ARInvoiceCreate, 
    referenced_invoice_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    """
    Create a new Accounts Receivable credit note.
    A credit note can be created with or without a reference to an existing invoice.
    """
    # Check if customer exists
    customer = db.query(Customer).filter(Customer.id == credit_note.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # If this credit note references an invoice, validate it
    referenced_invoice = None
    if referenced_invoice_id:
        referenced_invoice = db.query(ARInvoice).filter(
            ARInvoice.id == referenced_invoice_id,
            ARInvoice.customer_id == credit_note.customer_id,
            ARInvoice.status.in_([
                ARInvoiceStatus.APPROVED, 
                ARInvoiceStatus.PARTIALLY_PAID,
                ARInvoiceStatus.OVERDUE,
                ARInvoiceStatus.PAID
            ])
        ).first()
        
        if not referenced_invoice:
            raise HTTPException(
                status_code=404, 
                detail="Referenced invoice not found or not eligible for credit note"
            )
    
    # Calculate totals - for credit notes, the amounts will be negative
    subtotal, tax_amount, total_amount = ARService.calculate_invoice_totals(credit_note.items)
    
    # Make amounts negative for credit notes
    subtotal = -abs(subtotal)
    tax_amount = -abs(tax_amount)
    total_amount = -abs(total_amount)
    
    # Generate credit note number
    credit_note_number = ARService.generate_invoice_number().replace("AR-INV", "AR-CN")
    
    # Create credit note as a special type of invoice
    db_credit_note = ARInvoice(
        invoice_number=credit_note_number,
        customer_id=credit_note.customer_id,
        issue_date=credit_note.issue_date,
        due_date=credit_note.due_date,
        description=f"Credit Note: {credit_note.description or ''}",
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=ARInvoiceStatus.DRAFT,
        currency_code=credit_note.currency_code,
        created_by=current_user,
        # Store reference to original invoice if provided
        reference=str(referenced_invoice_id) if referenced_invoice_id else None
    )
    
    db.add(db_credit_note)
    db.flush()  # Get ID without committing
    
    # Create credit note items with negative amounts
    for item in credit_note.items:
        item_subtotal = -(item.quantity * item.unit_price)
        item_tax = -(item_subtotal * (item.tax_rate / 100))
        item_total = item_subtotal + item_tax
        
        db_item = ARInvoiceItem(
            invoice_id=db_credit_note.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=-abs(item.unit_price),  # Store as negative
            tax_rate=item.tax_rate,
            tax_amount=item_tax,
            total_amount=item_total,
            account_id=item.account_id
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_credit_note)
    return db_credit_note

@router.post("/ar/credit-notes/{credit_note_id}/approve", response_model=ar_schemas.ARInvoiceResponse)
def approve_ar_credit_note(
    credit_note_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    """
    Approve an AR credit note and create the corresponding journal entry.
    Journal entry will have debits and credits reversed compared to normal invoices.
    """
    credit_note = db.query(ARInvoice).filter(ARInvoice.id == credit_note_id).first()
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    
    if credit_note.status != ARInvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Credit note is already {credit_note.status}")
    
    # Create journal entry - credit note has opposite accounting effect of invoice
    journal_entry = ARService.create_journal_entry_for_invoice(db, credit_note, current_user)
    
    # Update credit note status
    credit_note.status = ARInvoiceStatus.APPROVED
    credit_note.journal_entry_id = journal_entry.id
    
    db.commit()
    db.refresh(credit_note)
    return credit_note

# Retrieve Credit Notes
@router.get("/ap/credit-notes", response_model=List[ap_schemas.APInvoiceResponse])
def list_ap_credit_notes(
    skip: int = 0, 
    limit: int = 50,
    vendor_id: Optional[uuid.UUID] = None,
    status: Optional[APInvoiceStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get a list of AP credit notes with optional filtering"""
    query = db.query(APInvoice).filter(APInvoice.invoice_number.like("AP-CN%"))
    
    if vendor_id:
        query = query.filter(APInvoice.vendor_id == vendor_id)
        
    if status:
        query = query.filter(APInvoice.status == status)
        
    if from_date:
        query = query.filter(APInvoice.issue_date >= from_date)
        
    if to_date:
        query = query.filter(APInvoice.issue_date <= to_date)
        
    return query.order_by(APInvoice.issue_date.desc()).offset(skip).limit(limit).all()

@router.get("/ar/credit-notes", response_model=List[ar_schemas.ARInvoiceResponse])
def list_ar_credit_notes(
    skip: int = 0, 
    limit: int = 50,
    customer_id: Optional[uuid.UUID] = None,
    status: Optional[ARInvoiceStatus] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get a list of AR credit notes with optional filtering"""
    query = db.query(ARInvoice).filter(ARInvoice.invoice_number.like("AR-CN%"))
    
    if customer_id:
        query = query.filter(ARInvoice.customer_id == customer_id)
        
    if status:
        query = query.filter(ARInvoice.status == status)
        
    if from_date:
        query = query.filter(ARInvoice.issue_date >= from_date)
        
    if to_date:
        query = query.filter(ARInvoice.issue_date <= to_date)
        
    return query.order_by(ARInvoice.issue_date.desc()).offset(skip).limit(limit).all()