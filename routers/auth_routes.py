from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import User
from auth import hash_password, verify_password, create_access_token, get_current_user_email
from dependencies import get_db

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    password: str

@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(email=user.email, hashed_password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully", "user_id": new_user.id}

@router.post("/login")
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
def read_current_user(current_user_email: str = Depends(get_current_user_email)):
    return {"email": current_user_email}                            