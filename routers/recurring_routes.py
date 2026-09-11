from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from decimal import Decimal

from models import User, Account, Transaction, RecurringTransaction
from dependencies import get_db, get_current_user

router = APIRouter()

class RecurringTransactionCreate(BaseModel):
    account_id: int
    amount: float
    category: str
    description: str = None
    frequency: str
    next_occurrence: datetime

@router.post("/recurring-transactions")
def create_recurring_transaction(rule: RecurringTransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.id == rule.account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if rule.frequency not in ["weekly", "biweekly", "monthly"]:
        raise HTTPException(status_code=400, detail="Frequency must be 'weekly', 'biweekly', or 'monthly'")

    new_rule = RecurringTransaction(
        account_id=rule.account_id,
        amount=rule.amount,
        category=rule.category,
        description=rule.description,
        frequency=rule.frequency,
        next_occurrence=rule.next_occurrence
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return {
        "id": new_rule.id,
        "account_id": new_rule.account_id,
        "amount": float(new_rule.amount),
        "category": new_rule.category,
        "frequency": new_rule.frequency,
        "next_occurrence": new_rule.next_occurrence
    }

@router.get("/recurring-transactions")
def list_recurring_transactions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rules = db.query(RecurringTransaction).join(Account).filter(Account.user_id == current_user.id).all()
    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "amount": float(r.amount),
            "category": r.category,
            "description": r.description,
            "frequency": r.frequency,
            "next_occurrence": r.next_occurrence
        }
        for r in rules
    ]

@router.post("/recurring-transactions/run-due")
def run_due_recurring_transactions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    due_rules = db.query(RecurringTransaction).join(Account).filter(
        Account.user_id == current_user.id,
        RecurringTransaction.next_occurrence <= now
    ).all()

    created_transactions = []
    for rule in due_rules:
        account = db.query(Account).filter(Account.id == rule.account_id).first()

        new_transaction = Transaction(
            account_id=rule.account_id,
            amount=rule.amount,
            category=rule.category,
            description=rule.description,
            transaction_date=rule.next_occurrence
        )
        db.add(new_transaction)
        account.balance = account.balance + Decimal(str(rule.amount))

        if rule.frequency == "weekly":
            rule.next_occurrence = rule.next_occurrence + timedelta(days=7)
        elif rule.frequency == "biweekly":
            rule.next_occurrence = rule.next_occurrence + timedelta(days=14)
        elif rule.frequency == "monthly":
            rule.next_occurrence = rule.next_occurrence + timedelta(days=30)

        created_transactions.append({
            "category": rule.category,
            "amount": float(rule.amount),
            "account_id": rule.account_id
        })

    db.commit()

    return {
        "transactions_created": len(created_transactions),
        "details": created_transactions
    }

def process_all_due_recurring_transactions(SessionLocal):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        due_rules = db.query(RecurringTransaction).filter(RecurringTransaction.next_occurrence <= now).all()

        for rule in due_rules:
            account = db.query(Account).filter(Account.id == rule.account_id).first()
            if not account:
                continue

            new_transaction = Transaction(
                account_id=rule.account_id,
                amount=rule.amount,
                category=rule.category,
                description=rule.description,
                transaction_date=rule.next_occurrence
            )
            db.add(new_transaction)
            account.balance = account.balance + Decimal(str(rule.amount))

            if rule.frequency == "weekly":
                rule.next_occurrence = rule.next_occurrence + timedelta(days=7)
            elif rule.frequency == "biweekly":
                rule.next_occurrence = rule.next_occurrence + timedelta(days=14)
            elif rule.frequency == "monthly":
                rule.next_occurrence = rule.next_occurrence + timedelta(days=30)

        db.commit()
        print(f"[Scheduler] Processed {len(due_rules)} due recurring transactions")
    finally:
        db.close()