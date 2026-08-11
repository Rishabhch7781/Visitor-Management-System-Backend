from typing import Optional

from pydantic import BaseModel

# Ye hamara Pydantic schema hai (Data check karne ke liye)
class VisitorData(BaseModel):
    name: str
    phone: str
    host_name: str
    purpose: str
    email: Optional[str] = None


    class Config:
        orm_mode = True 
        
        
# Naya User create karne ka form
class UserCreate(BaseModel):
    username: str
    password: str
    
# Login karne ka form
class UserLogin(BaseModel):
    username: str
    password: str