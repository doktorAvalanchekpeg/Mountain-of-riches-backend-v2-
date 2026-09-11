from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
import csv
import io

from models import User, Account, Transaction
from dependencies import get_db, get_current_user

router = APIRouter()

@router.get("/projections/balance")
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

@router.get("/projections/affordability")
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

@router.get("/accounts/{account_id}/payoff")
def debt_payoff_timeline(account_id: int, monthly_payment: float, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    balance = abs(float(account.balance))
    annual_rate = float(account.interest_rate)
    monthly_rate = annual_rate / 100 / 12

    if balance == 0:
        return {"message": "This account has no balance to pay off"}

    if monthly_rate == 0:
        months_to_payoff = balance / monthly_payment
        total_interest = 0
    else:
        min_payment_needed = balance * monthly_rate
        if monthly_payment <= min_payment_needed:
            raise HTTPException(status_code=400, detail="Monthly payment is too low to ever pay off this balance at the current interest rate")

        n = 0
        remaining = balance
        total_paid = 0
        while remaining > 0 and n < 600:
            interest_charge = remaining * monthly_rate
            remaining = remaining + interest_charge - monthly_payment
            total_paid += monthly_payment
            n += 1
        months_to_payoff = n
        total_interest = total_paid - balance

    return {
        "account_name": account.name,
        "current_balance": balance,
        "interest_rate": annual_rate,
        "monthly_payment": monthly_payment,
        "months_to_payoff": months_to_payoff,
        "years_to_payoff": round(months_to_payoff / 12, 1),
        "total_interest_paid": round(total_interest, 2)
    }

@router.post("/accounts/{account_id}/transactions/import")
async def import_transactions_csv(account_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    content = await file.read()
    decoded = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    imported_count = 0
    for row in reader:
        try:
            amount = float(row["amount"])
            category = row["category"]
            description = row.get("description", "")
            transaction_date = datetime.fromisoformat(row["transaction_date"])
        except (KeyError, ValueError):
            continue

        new_transaction = Transaction(
            account_id=account_id,
            amount=amount,
            category=category,
            description=description,
            transaction_date=transaction_date
        )
        db.add(new_transaction)
        account.balance = account.balance + Decimal(str(amount))
        imported_count += 1

    db.commit()
    return {"message": f"Imported {imported_count} transactions successfully"}

@router.get("/accounts/{account_id}/transactions/export")
def export_transactions_csv(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = db.query(Transaction).filter(Transaction.account_id == account_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["amount", "category", "description", "transaction_date"])
    for t in transactions:
        writer.writerow([float(t.amount), t.category, t.description or "", t.transaction_date.isoformat()])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=transactions_account_{account_id}.csv"}
    )wc -l routers/projection_routes.p