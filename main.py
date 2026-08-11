from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import models, schemas  
from database import engine, SessionLocal
from typing import Optional
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import File, UploadFile
import shutil
import os
from fastapi import BackgroundTasks
import time
from sqlalchemy import func

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

# 1. Password check karne ka function
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 2. Token banane ke liye ek Secret Key (Isko chupa kar rakhte hain)
SECRET_KEY = "mera_super_secret_key"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid Authentication!")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expire ho gaya hai, wapas login karein!")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Galat Token!")

app = FastAPI()

# Database session function
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to Visitor Management System!"}

# Yahan visitor: schemas.VisitorData kar diya hai
@app.post("/add-visitor/")
def add_new_visitor(
    visitor: schemas.VisitorData, 
    background_tasks: BackgroundTasks, # 👈 NAYA: Background task ka engine
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    new_visitor = models.Visitor(
        name=visitor.name, phone=visitor.phone, host_name=visitor.host_name, 
        purpose=visitor.purpose, email=visitor.email
    )
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)
    
    # 👈 NAYA: System ko bolo ki email background mein bhej do
    background_tasks.add_task(send_email_notification, visitor.host_name, visitor.name)
    
    # API turant response de degi (bina 5 second wait kiye)
    return {"message": f"Welcome {visitor.name}! Guard {current_user} ne aapki entry kar di hai.", "data": new_visitor}

@app.get("/visitors/")
def get_all_visitors(db: Session = Depends(get_db)):
    visitors = db.query(models.Visitor).all()
    return {"total_visitors": len(visitors), "data": visitors}



# UPDATE API: Visitor ko check-out karne ke liye
@app.put("/checkout/{visitor_id}")
def checkout_visitor(visitor_id: int, db: Session = Depends(get_db)):
    # 1. Database mein visitor dhoondo jiski ID 'visitor_id' hai
    visitor = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    
    # 2. Agar visitor nahi mila toh error dikhao
    if not visitor:
        return {"error": "Visitor nahi mila!"}
    
    # 3. Agar visitor mil gaya, toh usme current time daal do aur save kar do
    visitor.check_out_time = datetime.now()
    db.commit()
    db.refresh(visitor)
    
    return {"message": "Visitor checked out successfully!", "data": visitor}

# USER REGISTRATION API
@app.post("/register/")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Pehle check karo ki is username se koi aur user toh nahi hai
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        return {"error": "Ye username pehle se kisi ke paas hai!"}
    
    # Password ko encrypt (hash) karo
    hashed_password = get_password_hash(user.password)
    
    # Naya user database mein save karo
    new_user = models.User(username=user.username, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "Naya guard/user successfully register ho gaya!", "username": new_user.username}


# Ye function email bhejne mein 5 second lagayega
def send_email_notification(host_name: str, visitor_name: str):
    print(f"📧 Sending email to {host_name}...")
    time.sleep(5)  # 5 second ka wait (Jaise asli internet pe lagta hai)
    print(f"✅ Email sent successfully! Message: {visitor_name} is waiting for you.")
    
   
# LOGIN API 
@app.post("/login/")
# Yahan schemas.UserLogin hata kar OAuth2PasswordRequestForm laga diya hai
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    
    db_user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    if not db_user or not verify_password(form_data.password, db_user.password):
        # Professional way to send error
        raise HTTPException(status_code=400, detail="Galat Username ya Password!")
    
    expire_time = datetime.utcnow() + timedelta(minutes=30)
    token_data = {"sub": db_user.username, "exp": expire_time}
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    
    # Swagger ko specifically isi format mein response chahiye hota hai
    return {"access_token": token, "token_type": "bearer"}


# FILE UPLOAD API: Visitor ki photo save karne ke liye
@app.post("/upload-photo/{visitor_id}")
def upload_visitor_photo(
    visitor_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user) # Ye API bhi lock rahegi
):
    # 1. Check karo ki visitor database mein hai ya nahi
    visitor = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor nahi mila!")

    # 2. File ka naam aur path set karo (e.g., visitor_photos/1_photo.jpg)
    file_location = f"visitor_photos/{visitor_id}_{file.filename}"
    
    # 3. File ko folder mein save (copy) karo
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 4. Database mein photo ka rasta (path) save kar do
    visitor.photo_path = file_location
    db.commit()
    db.refresh(visitor)
    
    return {"message": "Photo successfully upload ho gayi!", "file_path": file_location}

# DASHBOARD API: Admin ko statistics dikhane ke liye
@app.get("/dashboard/")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user) # Ye dashboard sirf guard/admin dekh sakta hai
):
    # 1. Total visitors ginna (count)
    total_visitors = db.query(models.Visitor).count()
    
    # 2. Building mein abhi kitne log hain? (Jinka check_out_time null/None hai)
    active_visitors = db.query(models.Visitor).filter(models.Visitor.check_out_time == None).count()
    
    # 3. Aaj check-out ho chuke logo ka count
    checked_out_visitors = total_visitors - active_visitors

    return {
        "message": f"Hello {current_user}, Here is today's summary:",
        "total_visitors_ever": total_visitors,
        "currently_in_building": active_visitors,
        "already_left": checked_out_visitors
    }