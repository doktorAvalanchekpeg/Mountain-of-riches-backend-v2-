from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import User, Account
from dependencies import get_db, get_current_user

router = APIRouter()

class AccountCreate(BaseModel):
    name: str
    account_type: str
    balance: float = 0

@router.post("/accounts")
def create_account(account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_account = Account(
        user_id=current_user.id,
        name=account.name,
        account_type=account.account_type,
        balance=account.balance
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return {
        "id": new_account.id,
        "name": new_account.name,
        "account_type": new_account.account_type,
        "balance": float(new_account.balance)
    }

@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "account_type": a.account_type,
            "balance": float(a.balance)
        }
        for a in accounts
    ]

@router.put("/accounts/{account_id}")
def update_account(account_id: int, account: AccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")

    db_account.name = account.name
    db_account.account_type = account.account_type
    db_account.balance = account.balance
    db.commit()
    db.refresh(db_account)
    return {
        "id": db_account.id,
        "name": db_account.name,
        "account_type": db_account.account_type,
        "balance": float(db_account.balance)
    }

@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(db_account)
    db.commit()
    return {"message": "Account deleted successfully"}                              