# File: app/routers/bank_reconciliation.py
"""
API routes for bank reconciliation
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_db
from app.models.gl_models import Account, AccountType
from app.models.auth_models import User, Permission
from app.services.auth_service import AuthService
from app.integrations.bank_reconciliation import BankReconciliationService

router = APIRouter(
    prefix="/bank-reconciliation",
    tags=["bank reconciliation"],
    responses={404: {"description": "Not found"}},
)

@router.post("/reconcile")
async def reconcile_bank_statement(
    bank_account_id: uuid.UUID = Form(...),
    statement_date: date = Form(...),
    statement_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """
    Reconcile a bank account using a statement file
    
    Args:
        bank_account_id: ID of the bank account to reconcile
        statement_date: Date of the bank statement
        statement_file: CSV or Excel file with bank transactions
    
    Returns:
        Reconciliation results with matched and unmatched entries
    """
    # Check permissions
    AuthService.check_permission(Permission.GL_MANAGE, current_user, db)
    
    try:
        return await BankReconciliationService.reconcile_from_statement(
            db=db,
            bank_account_id=bank_account_id,
            statement_file=statement_file,
            statement_date=statement_date,
            created_by=current_user.username
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reconciliation failed: {str(e)}"
        )

@router.post("/create-missing-entries")
async def create_missing_journal_entries(
    bank_account_id: uuid.UUID,
    suspense_account_id: uuid.UUID,
    transactions: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """
    Create journal entries for unmatched bank statement transactions
    
    Args:
        bank_account_id: ID of the bank account
        suspense_account_id: ID of the suspense account to use for balancing entries
        transactions: List of transaction data (date, description, amount)
    
    Returns:
        List of created journal entry IDs
    """
    # Check permissions
    AuthService.check_permission(Permission.GL_MANAGE, current_user, db)
    
    try:
        return await BankReconciliationService.create_missing_entries(
            db=db,
            bank_account_id=bank_account_id,
            transactions=transactions,
            suspense_account_id=suspense_account_id,
            created_by=current_user.username
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create entries: {str(e)}"
        )

@router.get("/bank-accounts")
def get_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(AuthService.get_current_user)
):
    """
    Get list of bank accounts available for reconciliation
    """
    # Check permissions
    AuthService.check_permission(Permission.GL_VIEW, current_user, db)
    
    # Get bank accounts (assuming code starting with 110)
    bank_accounts = db.query(Account).filter(
        Account.account_type == AccountType.ASSET,
        Account.code.like('110%'),
        Account.is_active == True
    ).all()
    
    return [
        {
            "id": account.id,
            "code": account.code,
            "name": account.name
        }
        for account in bank_accounts
    ]