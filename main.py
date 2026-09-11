from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

from database import engine
from models import Base, User, Account, Transaction, Budget
from auth import hash_password, verify_password, create_access_token, get_current_user_email
from sqlalchemy.orm import sessionmaker

app = FastAPI()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), current_user_email: str = Depends(get_current_user_email)):
    user = db.query(User).filter(User.email == current_user_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

class UserCreate(BaseModel):
    email: str
    password: str

@app.get("/")
def read_root():
    return {"message": "Mountain of Riches backend is alive"}

@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(email=user.email, hashed_password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully", "user_id": new_user.id}

@app.post("/login")
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def read_current_user(current_user_email: str = Depends(get_current_user_email)):
    return {"email": current_user_email}

class AccountCreate(BaseModel):
    name: str
    account_type: str
    balance: float = 0

@app.post("/accounts")
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

@app.get("/accounts")
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

@app.put("/accounts/{account_id}")
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

@app.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(db_account)
    db.commit()
    return {"message": "Account deleted successfully"}

class TransactionCreate(BaseModel):
    account_id: int
    amount: float
    category: str
    description: str = None
    transaction_date: datetime

@app.post("/transactions")
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

@app.get("/accounts/{account_id}/transactions")
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

@app.put("/transactions/{transaction_id}")
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

@app.delete("/transactions/{transaction_id}")
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

class BudgetCreate(BaseModel):
    category: str
    monthly_limit: float

@app.post("/budgets")
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

@app.get("/budgets")
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

@app.put("/budgets/{budget_id}")
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

@app.delete("/budgets/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_budget = db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == current_user.id).first()
    if not db_budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db.delete(db_budget)
    db.commit()
    return {"message": "Budget deleted successfully"}

@app.get("/budgets/status")
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

@app.get("/projections/balance")
def project_balance(days: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="No accounts found")

    current_total_balance = sum(float(a.balance) for a in accounts)

    account_ids = [a.id for a in accounts]
    all_transactions = db.query(Transaction).filter(Transaction.account_id.in_(account_ids)).all()

    if not all_transactions:
        return {
            "current_balance": current_total_balance,
            "projected_balance": current_total_balance,
            "days_projected": days,
            "note": "No transaction history yet, projection assumes no change"
        }

    earliest_date = min(t.transaction_date for t in all_transactions)
    days_of_history = max((datetime.utcnow() - earliest_date).days, 1)

    net_total = sum(float(t.amount) for t in all_transactions)
    average_daily_net = net_total / days_of_history

    projected_change = average_daily_net * days
    projected_balance = current_total_balance + projected_change

    return {
        "current_balance": current_total_balance,
        "average_daily_net": round(average_daily_net, 2),
        "days_projected": days,
        "projected_balance": round(projected_balance, 2)
    }

@app.get("/projections/affordability")
def check_affordability(amount: float, days_from_now: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    if not accounts:
        raise HTTPException(status_code=404, detail="No accounts found")

    current_total_balance = sum(float(a.balance) for a in accounts)

    account_ids = [a.id for a in accounts]
    all_transactions = db.query(Transaction).filter(Transaction.account_id.in_(account_ids)).all()

    if not all_transactions:
        average_daily_net = 0
    else:
        earliest_date = min(t.transaction_date for t in all_transactions)
        days_of_history = max((datetime.utcnow() - earliest_date).days, 1)
        net_total = sum(float(t.amount) for t in all_transactions)
        average_daily_net = net_total / days_of_history

    projected_balance_before_purchase = current_total_balance + (average_daily_net * days_from_now)
    projected_balance_after_purchase = projected_balance_before_purchase - amount

    return {
        "purchase_amount": amount,
        "days_from_now": days_from_now,
        "projected_balance_before_purchase": round(projected_balance_before_purchase, 2),
        "projected_balance_after_purchase": round(projected_balance_after_purchase, 2),
        "can_afford": projected_balance_after_purchase >= 0
    }
