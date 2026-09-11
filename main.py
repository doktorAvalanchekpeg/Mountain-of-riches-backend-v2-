from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from pydantic import BaseModel

from database import engine
from models import Base, User, Account
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
