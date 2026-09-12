from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel,Field
from datetime import datetime

from models import User, SavingsGoal
from dependencies import get_db, get_current_user

router = APIRouter()

class SavingsGoalCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    target_amount: float = Field(..., gt=0)
    current_amount: float = Field(0, ge=0)
    target_date: datetime = None

@router.post("/savings-goals")
def create_savings_goal(goal: SavingsGoalCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_goal = SavingsGoal(
        user_id=current_user.id,
        name=goal.name,
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        target_date=goal.target_date
    )
    db.add(new_goal)
    db.commit()
    db.refresh(new_goal)
    return {
        "id": new_goal.id,
        "name": new_goal.name,
        "target_amount": float(new_goal.target_amount),
        "current_amount": float(new_goal.current_amount),
        "target_date": new_goal.target_date
    }

@router.get("/savings-goals")
def list_savings_goals(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    goals = db.query(SavingsGoal).filter(SavingsGoal.user_id == current_user.id).all()
    results = []
    for g in goals:
        progress_percent = (float(g.current_amount) / float(g.target_amount) * 100) if float(g.target_amount) > 0 else 0
        results.append({
            "id": g.id,
            "name": g.name,
            "target_amount": float(g.target_amount),
            "current_amount": float(g.current_amount),
            "target_date": g.target_date,
            "progress_percent": round(progress_percent, 1)
        })
    return results

@router.put("/savings-goals/{goal_id}")
def update_savings_goal(goal_id: int, goal: SavingsGoalCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id, SavingsGoal.user_id == current_user.id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")

    db_goal.name = goal.name
    db_goal.target_amount = goal.target_amount
    db_goal.current_amount = goal.current_amount
    db_goal.target_date = goal.target_date
    db.commit()
    db.refresh(db_goal)
    return {
        "id": db_goal.id,
        "name": db_goal.name,
        "target_amount": float(db_goal.target_amount),
        "current_amount": float(db_goal.current_amount),
        "target_date": db_goal.target_date
    }

@router.delete("/savings-goals/{goal_id}")
def delete_savings_goal(goal_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id, SavingsGoal.user_id == current_user.id).first()
    if not db_goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")

    db.delete(db_goal)
    db.commit()
    return {"message": "Savings goal deleted successfully"}