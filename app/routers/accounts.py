# File: app/routers/accounts.py
"""
API routes for managing chart of accounts
"""
from datetime import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.gl_models import Account, AccountType
from app.schemas import gl_schemas

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=gl_schemas.AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(account: gl_schemas.AccountCreate, db: Session = Depends(get_db)):
    # Check if account with same code already exists
    existing_account = db.query(Account).filter(Account.code == account.code).first()
    if existing_account:
        raise HTTPException(status_code=400, detail="Account code already exists")
    
    # Check if parent exists if parent_id is provided
    if account.parent_id:
        parent = db.query(Account).filter(Account.id == account.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
    
    db_account = Account(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

@router.get("/", response_model=List[gl_schemas.AccountResponse])
def list_accounts(
    skip: int = 0, 
    limit: int = 100, 
    account_type: Optional[AccountType] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Account)
    
    if account_type:
        query = query.filter(Account.account_type == account_type)
    
    if is_active is not None:
        query = query.filter(Account.is_active == is_active)
        
    return query.offset(skip).limit(limit).all()

@router.get("/{account_id}", response_model=gl_schemas.AccountResponse)
def get_account(account_id: uuid.UUID, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.put("/{account_id}", response_model=gl_schemas.AccountResponse)
def update_account(
    account_id: uuid.UUID, 
    account_update: gl_schemas.AccountUpdate, 
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    update_data = account_update.dict(exclude_unset=True)
    
    if "parent_id" in update_data and update_data["parent_id"]:
        parent = db.query(Account).filter(Account.id == update_data["parent_id"]).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
        # Prevent circular reference
        if account_id == update_data["parent_id"]:
            raise HTTPException(status_code=400, detail="Account cannot be its own parent")
    
    for key, value in update_data.items():
        setattr(account, key, value)
    
    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return account