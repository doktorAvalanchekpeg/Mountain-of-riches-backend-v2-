from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal
from models import User, Account, Transaction
from dependencies import get_db, get_current_user

router = APIRouter()
class TransactionCreate(BaseModel):
    account_id: int
    amount: float = Field(...)
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(None, max_length=500)
    transaction_date: datetime

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v):
        if v == 0:
            raise ValueError("amount cannot be zero")
        return v

@router.post("/transactions")
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.id == transaction.account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    new_transaction = Transaction(
        account_id=transaction.account_id,
        amount=transaction.amount,
        category=transaction.category,
        description=transaction.description,
        transaction_date=transaction.transaction_date
    )
    db.add(new_transaction)

    account.balance = account.balance + Decimal(str(transaction.amount))
    db.commit()
    db.refresh(new_transaction)

    return {
        "id": new_transaction.id,
        "account_id": new_transaction.account_id,
        "amount": float(new_transaction.amount),
        "category": new_transaction.category,
        "description": new_transaction.description,
        "transaction_date": new_transaction.transaction_date
    }

@router.get("/accounts/{account_id}/transactions")
def list_transactions(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = db.query(Transaction).filter(Transaction.account_id == account_id).all()
    return [
        {
            "id": t.id,
            "amount": float(t.amount),
            "category": t.category,
            "description": t.description,
            "transaction_date": t.transaction_date
        }
        for t in transactions
    ]

@router.put("/transactions/{transaction_id}")
def update_transaction(transaction_id: int, transaction: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_transaction = db.query(Transaction).join(Account).filter(
        Transaction.id == transaction_id,
        Account.user_id == current_user.id
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    account = db.query(Account).filter(Account.id == db_transaction.account_id).first()
    account.balance = account.balance - db_transaction.amount

    db_transaction.amount = transaction.amount
    db_transaction.category = transaction.category
    db_transaction.description = transaction.description
    db_transaction.transaction_date = transaction.transaction_date

    account.balance = account.balance + Decimal(str(transaction.amount))

    db.commit()
    db.refresh(db_transaction)

    return {
        "id": db_transaction.id,
        "account_id": db_transaction.account_id,
        "amount": float(db_transaction.amount),
        "category": db_transaction.category,
        "description": db_transaction.description,
        "transaction_date": db_transaction.transaction_date
    }

@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_transaction = db.query(Transaction).join(Account).filter(
        Transaction.id == transaction_id,
        Account.user_id == current_user.id
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    account = db.query(Account).filter(Account.id == db_transaction.account_id).first()
    account.balance = account.balance - db_transaction.amount

    db.delete(db_transaction)
    db.commit()

    return {"message": "Transaction deleted successfully"}