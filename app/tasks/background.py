import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any
import httpx
from sqlalchemy import select

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.db.crud import CurrencyCRUD
from app.models.currency_mod import CurrencyRate
from app.nats.client import nats_client
from app.ws.manager import manager
from app.schemas.currency import CurrencyCreate

logger = logging.getLogger(__name__)

class BackgroundTask:
    """Фоновая задача для получения курсов валют"""
    
    def __init__(self):
        self.is_running = False
        self.task = None
        self.last_run = None
        self.interval = settings.BACKGROUND_INTERVAL
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def fetch_cbr_rates(self) -> Dict[str, Any]:
        """Получение курсов валют с ЦБ РФ"""
        if not settings.ENABLE_TRADITIONAL:
            return {}
            
        try:
            response = await self.client.get(settings.CBR_API_URL)
            response.raise_for_status()
            data = response.json()
            
            # Проверяем структуру данных
            if 'Valute' not in data:
                logger.warning("Нет поля 'Valute' в ответе ЦБ РФ")
                logger.debug(f"Ответ ЦБ: {data}")
                return {}
            
            valutes = data['Valute']
            logger.info(f"Получено {len(valutes)} валют от ЦБ РФ")
            
            # Логируем первые 5 валют для проверки
            sample = list(valutes.keys())[:10]
            logger.debug(f"Пример валют: {sample}")
            
            return data
        except Exception as e:
            logger.error(f"Ошибка при получении курсов ЦБ: {e}")
            return {}
    
    async def fetch_crypto_rates(self) -> Dict[str, float]:
        """Получение курсов криптовалют"""
        if not settings.ENABLE_CRYPTO:
            return {}
        
        try:
            params = {
                'ids': ','.join(settings.CRYPTO_CURRENCIES),
                'vs_currencies': settings.CRYPTO_VS_CURRENCY
            }
            
            response = await self.client.get(settings.CRYPTO_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            crypto_rates = {}
            
            # Маппинг для преобразования названий
            crypto_mapping = {
                'bitcoin': 'BTC',
                'ethereum': 'ETH',
                'ripple': 'XRP',
                'litecoin': 'LTC',
                'cardano': 'ADA',
                'polkadot': 'DOT',
                'dogecoin': 'DOGE',
                'solana': 'SOL'
            }
            
            for crypto_id, rates in data.items():
                # Получаем нормализованный код
                normalized_code = crypto_mapping.get(crypto_id.lower(), crypto_id.upper()[:3])
                price = rates.get(settings.CRYPTO_VS_CURRENCY, 0)
                
                if price > 0:
                    crypto_rates[normalized_code] = price
            
            logger.info(f"Получено {len(crypto_rates)} криптовалют")
            return crypto_rates
            
        except Exception as e:
            logger.error(f"Ошибка при получении курсов криптовалют: {e}")
            return {}
    
    async def process_traditional_rates(self, rates_data: Dict[str, Any]) -> int:
        """Обработка и сохранение традиционных валют"""
        if not rates_data or 'Valute' not in rates_data:
            return 0
        
        updated_count = 0
        
        async with AsyncSessionLocal() as session:
            try:
                valutes = rates_data['Valute']
                
                for currency_code, currency_data in valutes.items():
                    # Ищем существующую запись
                    # Используем first() чтобы получить первую запись
                    result = await session.execute(
                        select(CurrencyRate)
                        .where(CurrencyRate.currency_code == currency_code)
                        .where(CurrencyRate.is_user_defined == False)  # Только не пользовательские
                        .order_by(CurrencyRate.created_at.desc())
                        .limit(1)
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        try:
                            # Обновляем существующую запись
                            await CurrencyCRUD.update(
                                session, 
                                existing.id,
                                {
                                    "rate": currency_data['Value'],
                                    "nominal": currency_data['Nominal'],
                                    "currency_name": currency_data['Name']
                                }
                            )
                            updated_count += 1
                        except Exception as e:
                            logger.error(f"Ошибка обновления {currency_code}: {e}")
                            continue
                    else:
                        try:
                            # Создаем новую запись
                            currency_obj = CurrencyCreate(
                                currency_code=currency_code,
                                currency_name=currency_data['Name'],
                                rate=currency_data['Value'],
                                nominal=currency_data['Nominal'],
                                is_active=True,
                                is_user_defined=False
                            )
                            await CurrencyCRUD.create(session, currency_obj)
                            updated_count += 1
                        except Exception as e:
                            # Если валюта уже существует (например, пользовательская)
                            logger.warning(f"Валюта {currency_code} уже существует: {e}")
                            continue
                
                await session.commit()
                logger.info(f"Обработано {updated_count} традиционных валют")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке традиционных валют: {e}")
                await session.rollback()
        
        return updated_count
    
    async def process_crypto_rates(self, crypto_rates: Dict[str, float]) -> int:
        """Обработка и сохранение криптовалют"""
        if not crypto_rates:
            return 0
        
        updated_count = 0
        
        async with AsyncSessionLocal() as session:
            try:
                for crypto_code, rate in crypto_rates.items():
                    if rate > 0:

                        crypto_code_mapping = {
                            'bitcoin': 'BTC',
                            'ethereum': 'ETH',
                            'ripple': 'XRP',
                            'litecoin': 'LTC',
                            'cardano': 'ADA',
                            'polkadot': 'DOT',
                            'dogecoin': 'DOGE',
                            'solana': 'SOL'
                        }
                        
                        # Преобразуем код криптовалюты
                        actual_code = crypto_code_mapping.get(crypto_code.lower(), crypto_code.upper()[:3])
                        
                        # Проверяем существующую запись
                        existing = await CurrencyCRUD.get_by_code(session, actual_code)
                        
                        crypto_names = {
                            'BTC': 'Bitcoin',
                            'ETH': 'Ethereum',
                            'XRP': 'Ripple',
                            'LTC': 'Litecoin',
                            'ADA': 'Cardano',
                            'DOT': 'Polkadot',
                            'DOGE': 'Dogecoin',
                            'SOL': 'Solana'
                        }
                        
                        currency_name = crypto_names.get(actual_code, actual_code)
                        
                        if existing:
                            # Обновляем существующую запись
                            await CurrencyCRUD.update(
                                session,
                                existing.id,  # Используем ID существующей записи
                                {
                                    "rate": rate,
                                    "nominal": 1,
                                    "currency_name": f"{currency_name} (Crypto)"
                                }
                            )
                        else:
                            # Создаем новую запись                            
                            currency_obj = CurrencyCreate(
                                currency_code=actual_code,
                                currency_name=f"{currency_name} (Crypto)",
                                rate=rate,
                                nominal=1,
                                is_active=True,
                                is_user_defined=False
                            )
                            await CurrencyCRUD.create(session, currency_obj)
                        
                        updated_count += 1
                
                await session.commit()
                logger.info(f"Обработано {updated_count} криптовалют")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке криптовалют: {e}")
                await session.rollback()
        
        return updated_count
    
    async def run_once(self) -> Dict[str, Any]:
        """Однократный запуск задачи"""
        logger.info("Запуск фоновой задачи...")
        
        total_updated = 0
        traditional_updated = 0
        crypto_updated = 0
        
        # Получаем традиционные валюты
        if settings.ENABLE_TRADITIONAL:
            rates_data = await self.fetch_cbr_rates()
            traditional_updated = await self.process_traditional_rates(rates_data)
            total_updated += traditional_updated
        
        # Получаем криптовалюты
        if settings.ENABLE_CRYPTO:
            crypto_rates = await self.fetch_crypto_rates()
            crypto_updated = await self.process_crypto_rates(crypto_rates)
            total_updated += crypto_updated
        
        # Обновляем время последнего запуска
        self.last_run = datetime.now()
        
        # Публикуем в NATS
        if nats_client.connected and total_updated > 0:
            await nats_client.publish_task_completed({
                "currencies_updated": total_updated,
                "traditional": traditional_updated,
                "crypto": crypto_updated,
                "timestamp": self.last_run.isoformat(),
                "source": "mixed"
            })
        
        # Отправляем уведомление в WebSocket
        await manager.broadcast({
            "type": "background_task_completed",
            "data": {
                "currencies_updated": total_updated,
                "traditional": traditional_updated,
                "crypto": crypto_updated,
                "timestamp": self.last_run.isoformat(),
                "message": f"Обновлено {total_updated} валют"
            },
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Фоновая задача завершена. Обновлено: {total_updated} (традиционные: {traditional_updated}, крипто: {crypto_updated})")
        
        return {
            "currencies_updated": total_updated,
            "traditional": traditional_updated,
            "crypto": crypto_updated,
            "last_run": self.last_run.isoformat(),
            "status": "completed"
        }
    
    async def _run_periodically(self):
        """Запуск задачи периодически"""
        self.is_running = True
        logger.info(f"Фоновая задача запущена с интервалом {self.interval} секунд")
        
        while self.is_running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Ошибка в фоновой задаче: {e}")
            
            # Ждем указанный интервал
            await asyncio.sleep(self.interval)
    
    def start(self):
        """Запуск периодической задачи"""
        if not self.is_running:
            self.task = asyncio.create_task(self._run_periodically())
    
    def stop(self):
        """Остановка периодической задачи"""
        self.is_running = False
        if self.task:
            self.task.cancel()
        logger.info("Фоновая задача остановлена")

# Глобальный экземпляр
background_task = BackgroundTask()