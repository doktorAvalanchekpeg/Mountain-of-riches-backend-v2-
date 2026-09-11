from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session, sessionmaker
from database import engine
from models import User
from auth import get_current_user_email

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