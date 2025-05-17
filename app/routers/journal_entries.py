# File: app/routers/journal_entries.py
"""
API routes for managing journal entries
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.gl_models import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.schemas import gl_schemas
from app.services.gl_service import GLService

router = APIRouter(
    prefix="/journal-entries",
    tags=["journal entries"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=gl_schemas.JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    journal_entry: gl_schemas.JournalEntryCreate, 
    db: Session = Depends(get_db),
    current_user: str = "system"  # This will be replaced with actual auth
):
    # Validate the journal entry
    GLService.validate_journal_entry(journal_entry, db)
    
    # Generate entry number
    entry_number = GLService.generate_entry_number()
    
    # Create journal entry
    db_journal_entry = JournalEntry(
        entry_number=entry_number,
        entry_date=journal_entry.entry_date,
        description=journal_entry.description,
        reference=journal_entry.reference,
        is_recurring=journal_entry.is_recurring,
        created_by=current_user
    )
    
    db.add(db_journal_entry)
    db.flush()  # Get ID without committing
    
    # Create journal entry lines
    for line in journal_entry.lines:
        db_line = JournalEntryLine(
            journal_entry_id=db_journal_entry.id,
            account_id=line.account_id,
            description=line.description,
            debit_amount=line.debit_amount,
            credit_amount=line.credit_amount
        )
        db.add(db_line)
    
    db.commit()
    db.refresh(db_journal_entry)
    return db_journal_entry

@router.get("/", response_model=List[gl_schemas.JournalEntryResponse])
def list_journal_entries(
    skip: int = 0, 
    limit: int = 50, 
    status: Optional[JournalEntryStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(JournalEntry)
    
    if status:
        query = query.filter(JournalEntry.status == status)
    
    if start_date:
        query = query.filter(JournalEntry.entry_date >= start_date)
    
    if end_date:
        query = query.filter(JournalEntry.entry_date <= end_date)
        
    return query.order_by(JournalEntry.entry_date.desc()).offset(skip).limit(limit).all()

@router.get("/{entry_id}", response_model=gl_schemas.JournalEntryResponse)
def get_journal_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry

@router.post("/{entry_id}/post", response_model=gl_schemas.JournalEntryResponse)
def post_journal_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    
    if entry.status != JournalEntryStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Journal entry is already {entry.status}")
    
    # In a real system, this would update account balances
    entry.status = JournalEntryStatus.POSTED
    entry.posted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(entry)
    return entry

@router.post("/{entry_id}/reverse", response_model=gl_schemas.JournalEntryResponse)
def reverse_journal_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    
    if entry.status != JournalEntryStatus.POSTED:
        raise HTTPException(
            status_code=400, 
            detail="Only posted journal entries can be reversed"
        )
    
    # In a real system, this would create a reversing entry and update account balances
    entry.status = JournalEntryStatus.REVERSED
    entry.reversed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(entry)
    return entry