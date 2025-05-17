# File: app/main.py
"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.default_permissions import setup_default_permissions
from app.config import settings
from app.database import SessionLocal, engine, Base
from app.routers import (
    accounts, auth, bank_reconciliation, credit_notes, currencies, financial_statements, journal_entries, fiscal_periods, reporting, 
    vendors, customers, invoices, payments
)
# Create tables
Base.metadata.create_all(bind=engine)

# Set up default permissions on startup
setup_default_permissions(SessionLocal())

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

# Include routers
app.include_router(accounts.router)
app.include_router(journal_entries.router)
app.include_router(fiscal_periods.router)
app.include_router(reporting.router)

# Include Accounts Payable & Receivable routers
app.include_router(vendors.router)
app.include_router(customers.router)
app.include_router(invoices.router)
app.include_router(payments.router)

# Include Financial Statements router
app.include_router(financial_statements.router)
app.include_router(credit_notes.router)
app.include_router(currencies.router)
app.include_router(bank_reconciliation.router)

@app.get("/")
def root():
    return {
        "message": "Finance Agent API",
        "version": settings.PROJECT_VERSION,
        "modules": [
            "General Ledger", 
            "Accounts Payable", 
            "Accounts Receivable", 
            "Financial Statements"
        ]
    }

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)