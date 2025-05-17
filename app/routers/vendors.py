# File: app/routers/vendors.py
"""
API routes for managing vendors
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ap_models import Vendor, VendorStatus
from app.schemas import ap_schemas

router = APIRouter(
    prefix="/vendors",
    tags=["vendors"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=ap_schemas.VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(vendor: ap_schemas.VendorCreate, db: Session = Depends(get_db)):
    # Check if vendor with same code already exists
    existing_vendor = db.query(Vendor).filter(Vendor.code == vendor.code).first()
    if existing_vendor:
        raise HTTPException(status_code=400, detail="Vendor code already exists")
    
    db_vendor = Vendor(**vendor.dict())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

@router.get("/", response_model=List[ap_schemas.VendorResponse])
def list_vendors(
    skip: int = 0, 
    limit: int = 100,
    status: Optional[VendorStatus] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Vendor)
    
    if status:
        query = query.filter(Vendor.status == status)
        
    return query.offset(skip).limit(limit).all()

@router.get("/{vendor_id}", response_model=ap_schemas.VendorResponse)
def get_vendor(vendor_id: uuid.UUID, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor

@router.put("/{vendor_id}", response_model=ap_schemas.VendorResponse)
def update_vendor(
    vendor_id: uuid.UUID, 
    vendor_update: ap_schemas.VendorUpdate, 
    db: Session = Depends(get_db)
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    update_data = vendor_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(vendor, key, value)
    
    db.commit()
    db.refresh(vendor)
    return vendor
