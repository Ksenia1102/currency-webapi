from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class CurrencyBase(BaseModel):
    currency_code: str = Field(..., min_length=3, max_length=3)
    currency_name: str = Field(..., min_length=2, max_length=100)
    rate: float = Field(..., gt=0)
    nominal: int = Field(1, gt=0)
    is_active: bool = True

class CurrencyCreate(CurrencyBase):
    pass

class CurrencyUpdate(BaseModel):
    currency_name: Optional[str] = None
    rate: Optional[float] = None
    nominal: Optional[int] = None
    is_active: Optional[bool] = None

class CurrencyResponse(CurrencyBase):
    id: int
    unit_rate: float
    previous_rate: Optional[float] = None
    last_updated: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class WSMessage(BaseModel):
    type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.now)

class BackgroundTaskResponse(BaseModel):
    message: str
    currencies_updated: int
    status: str