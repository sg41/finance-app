# finance-app-master/user_api.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import models
from database import get_db
from models import User
from schemas import UserResponse, UserListResponse, UserCreate, UserUpdateAdmin
from deps import get_current_user, get_current_admin_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UserListResponse, summary="Get Users (Admins only)")
def get_users(
    email: Optional[str] = Query(None, description="Filter users by email (exact match)"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    query = db.query(User)
    
    if email:
        query = query.filter(User.email == email)
    
    users = query.all()
    return UserListResponse(count=len(users), users=users)

@router.get("/me", response_model=UserResponse, summary="Get own user info")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse, summary="Update own user info")
def update_my_email(
    user_update_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if user_update_data.email != current_user.email:
        existing = db.query(User).filter(User.email == user_update_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = user_update_data.email
        db.commit()
        db.refresh(current_user)
    return current_user


@router.delete("/me", summary="Delete own account")
def delete_my_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from utils import revoke_bank_consent
    import asyncio
    connections = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == current_user.id).all()
    asyncio.run(asyncio.gather(*[revoke_bank_consent(conn, db) for conn in connections]))
    
    db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()
    return {"status": "deleted", "message": "Your account has been deleted"}

@router.put("/{user_id}", response_model=UserResponse, summary="Update a user by ID (Admins only)")
def update_user_by_admin(
    user_id: int,
    user_update_data: UserUpdateAdmin,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_update_data.email:
        if user_update_data.email != target_user.email:
            existing = db.query(User).filter(User.email == user_update_data.email).first()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
        target_user.email = user_update_data.email

    if user_update_data.is_admin is not None:
        target_user.is_admin = user_update_data.is_admin

    db.commit()
    db.refresh(target_user)
    return target_user


@router.delete("/{user_id}", summary="Delete a user by ID (Admins only)")
async def delete_user_by_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if target_user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Admins cannot delete their own account via this endpoint.")

    from utils import revoke_bank_consent
    import asyncio
    connections = db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == target_user.id).all()
    
    await asyncio.gather(*[revoke_bank_consent(conn, db) for conn in connections])
    
    db.query(models.ConnectedBank).filter(models.ConnectedBank.user_id == target_user.id).delete()
    db.delete(target_user)
    db.commit()
    return {"status": "deleted", "message": f"User {target_user.email} has been deleted."}