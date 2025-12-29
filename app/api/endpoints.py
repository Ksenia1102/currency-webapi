# app/api/endpoints.py - ИСПРАВЛЕННЫЙ
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
from app.config import settings


from app.db.database import get_db
from app.db.crud import CurrencyCRUD
from app.schemas.currency import CurrencyCreate, CurrencyUpdate, CurrencyResponse, BackgroundTaskResponse
from app.ws.manager import manager
from app.tasks.background import background_task

router = APIRouter()

# REST API endpoints
@router.get("/currencies", response_model=List[CurrencyResponse])
async def get_currencies(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """GET /currencies - список валют"""
    return await CurrencyCRUD.get_all(db, skip, limit)

@router.get("/currencies/active", response_model=List[CurrencyResponse])
async def get_active_currencies(db: AsyncSession = Depends(get_db)):
    """GET /currencies/active - активные валюты"""
    return await CurrencyCRUD.get_active(db)

@router.get("/currencies/{currency_id}", response_model=CurrencyResponse)
async def get_currency(
    currency_id: int,
    db: AsyncSession = Depends(get_db)
):
    """GET /currencies/{id} - получить валюту по ID"""
    currency = await CurrencyCRUD.get_by_id(db, currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Валюта не найдена")
    return currency

@router.post("/currencies", response_model=CurrencyResponse)
async def create_currency(
    currency: CurrencyCreate,
    db: AsyncSession = Depends(get_db)
):
    """POST /currencies - создать валюту"""
    try:
        created = await CurrencyCRUD.create(db, currency)
        
        # WebSocket уведомление
        await manager.broadcast({
            "type": "currency_created",
            "data": CurrencyResponse.model_validate(created).model_dump(),
            "timestamp": datetime.now().isoformat()
        })
        
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/currencies/{currency_id}", response_model=CurrencyResponse)
async def update_currency(
    currency_id: int,
    currency_update: CurrencyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """PATCH /currencies/{id} - обновить валюту"""
    updated = await CurrencyCRUD.update(db, currency_id, currency_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Валюта не найдена")
    
    # WebSocket уведомление
    await manager.broadcast({
        "type": "currency_updated",
        "data": CurrencyResponse.model_validate(updated).model_dump(),
        "timestamp": datetime.now().isoformat()
    })
    
    return updated

@router.delete("/currencies/{currency_id}")
async def delete_currency(
    currency_id: int,
    db: AsyncSession = Depends(get_db)
):
    """DELETE /currencies/{id} - удалить валюту"""
    success = await CurrencyCRUD.delete(db, currency_id)
    if not success:
        raise HTTPException(status_code=404, detail="Валюта не найдена")
    
    # WebSocket уведомление
    await manager.broadcast({
        "type": "currency_deleted",
        "data": {"id": currency_id},
        "timestamp": datetime.now().isoformat()
    })
    
    return {"message": "Валюта удалена"}

# Фоновые задачи
@router.post("/tasks/run", response_model=BackgroundTaskResponse)
async def run_background_task(background_tasks: BackgroundTasks):
    """POST /tasks/run - запустить фоновую задачу"""
    
    async def run_and_notify():
        result = await background_task.run_once()
        
        # WebSocket уведомление
        await manager.broadcast({
            "type": "background_task_completed",
            "data": result,
            "timestamp": datetime.now().isoformat()
        })
    
    background_tasks.add_task(run_and_notify)
    
    return {
        "message": "Фоновая задача запущена",
        "currencies_updated": 0,
        "status": "processing"
    }

@router.get("/tasks/status")
async def get_task_status():
    """GET /tasks/status - статус фоновой задачи"""
    return {
        "running": background_task.is_running,
        "interval": background_task.interval,
        "last_run": background_task.last_run,
        "interval_seconds": settings.BACKGROUND_INTERVAL
    }
