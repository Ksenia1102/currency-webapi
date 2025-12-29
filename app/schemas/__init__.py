# app/schemas/__init__.py - ИСПРАВЛЕННЫЙ
from app.schemas.currency import (
    CurrencyBase, 
    CurrencyCreate, 
    CurrencyUpdate, 
    CurrencyResponse,
    WSMessage,
    BackgroundTaskResponse
)

__all__ = [
    'CurrencyBase',
    'CurrencyCreate',
    'CurrencyUpdate',
    'CurrencyResponse',
    'WSMessage',
    'BackgroundTaskResponse'
]