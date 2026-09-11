from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from database import engine
from models import Base
from dependencies import SessionLocal
from routers import auth_routes, account_routes, transaction_routes, budget_routes, savings_goal_routes, recurring_routes, projection_routes

app = FastAPI()

app.include_router(auth_routes.router)
app.include_router(account_routes.router)
app.include_router(transaction_routes.router)
app.include_router(budget_routes.router)
app.include_router(savings_goal_routes.router)
app.include_router(recurring_routes.router)
app.include_router(projection_routes.router)

@app.get("/")
def read_root():
    return {"message": "Mountain of Riches backend is alive"}

scheduler = BackgroundScheduler()
scheduler.add_job(lambda: recurring_routes.process_all_due_recurring_transactions(SessionLocal), "interval", hours=24)
scheduler.start()