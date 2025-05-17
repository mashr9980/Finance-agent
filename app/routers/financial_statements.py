# File: app/routers/financial_statements.py
"""
API routes for financial statements
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.financial_statement_service import FinancialStatementService

router = APIRouter(
    prefix="/financial-statements",
    tags=["financial statements"],
    responses={404: {"description": "Not found"}},
)

@router.get("/balance-sheet")
def get_balance_sheet(
    as_of_date: date = Query(None, description="Date for the balance sheet (defaults to today)"),
    comparative: bool = Query(False, description="Include comparative figures"),
    previous_period_months: int = Query(12, description="Months to look back for comparative figures"),
    db: Session = Depends(get_db)
):
    """
    Generate a balance sheet as of a specific date.
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    return FinancialStatementService.get_balance_sheet(
        db=db, 
        as_of_date=as_of_date,
        comparative=comparative,
        previous_period_months=previous_period_months
    )

@router.get("/income-statement")
def get_income_statement(
    from_date: date = Query(..., description="Start date for the income statement"),
    to_date: date = Query(None, description="End date for the income statement (defaults to today)"),
    comparative: bool = Query(False, description="Include comparative figures"),
    include_details: bool = Query(True, description="Include detailed account breakdown"),
    previous_period_months: int = Query(12, description="Months to look back for comparative figures"),
    db: Session = Depends(get_db)
):
    """
    Generate an income statement for a specific period.
    """
    if to_date is None:
        to_date = date.today()
    
    return FinancialStatementService.get_income_statement(
        db=db, 
        from_date=from_date,
        to_date=to_date,
        comparative=comparative,
        include_details=include_details,
        previous_period_months=previous_period_months
    )

@router.get("/cash-flow-statement")
def get_cash_flow_statement(
    from_date: date = Query(..., description="Start date for the cash flow statement"),
    to_date: date = Query(None, description="End date for the cash flow statement (defaults to today)"),
    comparative: bool = Query(False, description="Include comparative figures"),
    previous_period_months: int = Query(12, description="Months to look back for comparative figures"),
    db: Session = Depends(get_db)
):
    """
    Generate a cash flow statement for a specific period.
    """
    if to_date is None:
        to_date = date.today()
    
    return FinancialStatementService.get_cash_flow_statement(
        db=db, 
        from_date=from_date,
        to_date=to_date,
        comparative=comparative,
        previous_period_months=previous_period_months
    )

@router.get("/financial-statements-package")
def get_financial_statements_package(
    as_of_date: date = Query(None, description="Date for the financial statements (defaults to today)"),
    from_date: date = Query(None, description="Start date for income and cash flow statements (defaults to start of year)"),
    comparative: bool = Query(True, description="Include comparative figures"),
    db: Session = Depends(get_db)
):
    """
    Generate a complete package of financial statements (Balance Sheet, Income Statement, Cash Flow).
    """
    if as_of_date is None:
        as_of_date = date.today()
    
    if from_date is None:
        from_date = date(as_of_date.year, 1, 1)  # Start of current year
    
    # Generate all statements
    balance_sheet = FinancialStatementService.get_balance_sheet(
        db=db, 
        as_of_date=as_of_date,
        comparative=comparative
    )
    
    income_statement = FinancialStatementService.get_income_statement(
        db=db, 
        from_date=from_date,
        to_date=as_of_date,
        comparative=comparative
    )
    
    cash_flow_statement = FinancialStatementService.get_cash_flow_statement(
        db=db, 
        from_date=from_date,
        to_date=as_of_date,
        comparative=comparative
    )
    
    # Return complete package
    return {
        "report_date": as_of_date,
        "period_start": from_date,
        "balance_sheet": balance_sheet,
        "income_statement": income_statement,
        "cash_flow_statement": cash_flow_statement
    }