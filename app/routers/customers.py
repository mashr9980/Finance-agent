# File: app/routers/customers.py
"""
API routes for managing customers
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ar_models import Customer, CustomerStatus
from app.schemas import ar_schemas
from app.services.ar_service import ARService

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=ar_schemas.CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer: ar_schemas.CustomerCreate, db: Session = Depends(get_db)):
    # Check if customer with same code already exists
    existing_customer = db.query(Customer).filter(Customer.code == customer.code).first()
    if existing_customer:
        raise HTTPException(status_code=400, detail="Customer code already exists")
    
    db_customer = Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get("/", response_model=List[ar_schemas.CustomerResponse])
def list_customers(
    skip: int = 0, 
    limit: int = 100,
    status: Optional[CustomerStatus] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Customer)
    
    if status:
        query = query.filter(Customer.status == status)
        
    return query.offset(skip).limit(limit).all()

@router.get("/{customer_id}", response_model=ar_schemas.CustomerResponse)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.get("/{customer_id}/credit", response_model=dict)
def check_customer_credit(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    """Check customer credit availability"""
    within_limit, available_credit = ARService.check_credit_limit(db, customer_id)
    
    return {
        "customer_id": customer_id,
        "within_limit": within_limit,
        "available_credit": available_credit
    }

@router.put("/{customer_id}", response_model=ar_schemas.CustomerResponse)
def update_customer(
    customer_id: uuid.UUID, 
    customer_update: ar_schemas.CustomerUpdate, 
    db: Session = Depends(get_db)
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    update_data = customer_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(customer, key, value)
    
    db.commit()
    db.refresh(customer)
    return customer