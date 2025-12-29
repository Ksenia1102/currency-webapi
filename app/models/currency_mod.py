from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from datetime import datetime

from app.db.database import Base

class CurrencyRate(Base):
    """Модель курса валюты"""
    __tablename__ = "currency_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    currency_code = Column(String(3), nullable=False, index=True)
    currency_name = Column(String(100), nullable=False)
    rate = Column(Float, nullable=False)
    nominal = Column(Integer, default=1)
    unit_rate = Column(Float, nullable=False)
    previous_rate = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, server_default=func.now())
    is_user_defined = Column(Boolean, default=False)

    
    def to_dict(self):
        return {
            "id": self.id,
            "currency_code": self.currency_code,
            "currency_name": self.currency_name,
            "rate": self.rate,
            "nominal": self.nominal,
            "unit_rate": self.unit_rate,
            "previous_rate": self.previous_rate,
            "is_active": self.is_active,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_user_defined": self.is_user_defined
        }