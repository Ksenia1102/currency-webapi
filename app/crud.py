from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from typing import List, Optional
from datetime import datetime

from app.models import CurrencyRate
from app.schemas import CurrencyCreate, CurrencyUpdate

from app.nats.client import nats_client


class CurrencyCRUD:
    """CRUD операции для валют"""
    
    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[CurrencyRate]:
        """Получить все валюты"""
        result = await db.execute(
            select(CurrencyRate)
            .order_by(CurrencyRate.currency_code)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_by_id(db: AsyncSession, currency_id: int) -> Optional[CurrencyRate]:
        """Получить валюту по ID"""
        result = await db.execute(
            select(CurrencyRate).where(CurrencyRate.id == currency_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_code(db: AsyncSession, currency_code: str) -> Optional[CurrencyRate]:
        """Получить валюту по коду"""
        result = await db.execute(
            select(CurrencyRate).where(CurrencyRate.currency_code == currency_code.upper())
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create(db: AsyncSession, currency: CurrencyCreate) -> CurrencyRate:
        """Создать новую валюту"""
        # Проверяем существование
        existing = await CurrencyCRUD.get_by_code(db, currency.currency_code)
        if existing:
            raise ValueError(f"Валюта с кодом {currency.currency_code} уже существует")
        
        # Вычисляем курс за 1 единицу
        unit_rate = currency.rate / currency.nominal if currency.nominal > 0 else currency.rate
        
        db_currency = CurrencyRate(
            currency_code=currency.currency_code.upper(),
            currency_name=currency.currency_name,
            rate=currency.rate,
            nominal=currency.nominal,
            unit_rate=unit_rate,
            previous_rate=None,
            is_active=currency.is_active
        )
        
        db.add(db_currency)
        await db.commit()
        await db.refresh(db_currency)
        await nats_client.publish_currency_update(db_currency, currency.rate)
        return db_currency
    
    @staticmethod
    async def update(db: AsyncSession, currency_id: int, currency_update: CurrencyUpdate) -> Optional[CurrencyRate]:
        """Обновить валюту"""
        # Получаем текущую валюту
        currency = await CurrencyCRUD.get_by_id(db, currency_id)
        if not currency:
            return None
        
        # Сохраняем старый курс
        old_rate = currency.rate
        
        # Обновляем только переданные поля
        update_data = currency_update.model_dump(exclude_unset=True)
        
        if "rate" in update_data:
            update_data["previous_rate"] = old_rate
            new_nominal = update_data.get("nominal", currency.nominal)
            update_data["unit_rate"] = update_data["rate"] / new_nominal
            update_data["last_updated"] = datetime.utcnow()

            # Публикуем в NATS
            if abs(old_rate - update_data["rate"]) > 0.0001:
                await nats_client.publish_currency_update(currency, update_data["rate"])
        
        
        elif "nominal" in update_data:
            update_data["unit_rate"] = currency.rate / update_data["nominal"]
        
        if update_data:
            stmt = (
                update(CurrencyRate)
                .where(CurrencyRate.id == currency_id)
                .values(**update_data)
                .execution_options(synchronize_session="fetch")
            )
            await db.execute(stmt)
            await db.commit()
        
        return await CurrencyCRUD.get_by_id(db, currency_id)
    
    @staticmethod
    async def delete(db: AsyncSession, currency_id: int) -> bool:
        """Удалить валюту"""
        currency = await CurrencyCRUD.get_by_id(db, currency_id)
        if not currency:
            return False
        
        await db.delete(currency)
        await db.commit()
        return True
    
    @staticmethod
    async def get_active(db: AsyncSession) -> List[CurrencyRate]:
        """Получить активные валюты"""
        result = await db.execute(
            select(CurrencyRate)
            .where(CurrencyRate.is_active == True)
            .order_by(CurrencyRate.currency_code)
        )
        return result.scalars().all()