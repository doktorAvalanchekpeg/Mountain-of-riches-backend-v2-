from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from models import User, Account, Transaction, Budget
from dependencies import get_db, get_current_user

router = APIRouter()

class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float

@router.post("/budgets")
def create_budget(budget: BudgetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_budget = Budget(
        user_id=current_user.id,
        category=budget.category,
        monthly_limit=budget.monthly_limit
    )
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)
    return {
        "id": new_budget.id,
        "category": new_budget.category,
        "monthly_limit": float(new_budget.monthly_limit)
    }

@router.get("/budgets")
def list_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    return [
        {
            "id": b.id,
            "category": b.category,
            "monthly_limit": float(b.monthly_limit)
        }
        for b in budgets
    ]

@router.put("/budgets/{budget_id}")
def update_budget(budget_id: int, budget: BudgetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == current_user.id).first()
    if not db_budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db_budget.category = budget.category
    db_budget.monthly_limit = budget.monthly_limit
    db.commit()
    db.refresh(db_budget)
    return {
        "id": db_budget.id,
        "category": db_budget.category,
        "monthly_limit": float(db_budget.monthly_limit)
    }

@router.delete("/budgets/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == current_user.id).first()
    if not db_budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db.delete(db_budget)
    db.commit()
    return {"message": "Budget deleted successfully"}

@router.get("/budgets/status")
def budget_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()

    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)

    results = []
    for b in budgets:
        spent = db.query(Transaction).join(Account).filter(
            Account.user_id == current_user.id,
            Transaction.category == b.category,
            Transaction.transaction_date >= start_of_month,
            Transaction.amount < 0
        ).all()

        total_spent = sum(abs(float(t.amount)) for t in spent)

        results.append({
            "category": b.category,
            "monthly_limit": float(b.monthly_limit),
            "spent_this_month": total_spent,
            "remaining": float(b.monthly_limit) - total_spent,
            "over_budget": total_spent > float(b.monthly_limit)
        })

    return results