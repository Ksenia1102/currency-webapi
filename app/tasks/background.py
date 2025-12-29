# import asyncio
# import httpx
# import json
# from datetime import datetime
# from typing import Dict, List
# import logging

# from app.config import settings
# from app.crud import CurrencyCRUD
# from app.schemas import CurrencyCreate
# from app.database import AsyncSessionLocal
# from app.ws.manager import manager
# from app.nats.client import nats_client

# logger = logging.getLogger(__name__)

# class BackgroundTask:
#     """Фоновая задача для обновления курсов валют"""
    
#     def __init__(self):
#         self.is_running = False
#         self.task = None
#         self.interval = settings.BACKGROUND_INTERVAL
#         self.last_run = None
    
#     async def fetch_cbr_data(self) -> Dict:
#         """Получение данных с ЦБ РФ"""
#         async with httpx.AsyncClient(timeout=30.0) as client:
#             response = await client.get(settings.CBR_API_URL)
#             response.raise_for_status()
#             return response.json()
    
#     def parse_currencies(self, data: Dict) -> List[Dict]:
#         """Парсинг данных о валютах"""
#         currencies = []
#         valute_data = data.get("Valute", {})
        
#         for code, info in valute_data.items():
#             try:
#                 currencies.append({
#                     "currency_code": code,
#                     "currency_name": info.get("Name", ""),
#                     "rate": float(info.get("Value", 0)),
#                     "nominal": int(info.get("Nominal", 1))
#                 })
#             except (ValueError, TypeError) as e:
#                 logger.warning(f"Ошибка парсинга валюты {code}: {e}")
#                 continue
        
#         return currencies
    
#     async def update_database(self, currencies: List[Dict]) -> Dict:
#         """Обновление базы данных"""
#         stats = {"created": 0, "updated": 0, "errors": 0}
        
#         async with AsyncSessionLocal() as db:
#             for currency_data in currencies:
#                 try:
#                     existing = await CurrencyCRUD.get_by_code(db, currency_data["currency_code"])
                    
#                     if existing:
#                         # Обновляем если курс изменился
#                         if abs(existing.rate - currency_data["rate"]) > 0.0001:
#                             from app.schemas import CurrencyUpdate
#                             await CurrencyCRUD.update(
#                                 db, 
#                                 existing.id, 
#                                 CurrencyUpdate(rate=currency_data["rate"])
#                             )
#                             stats["updated"] += 1
                            
#                             # Публикуем в NATS
#                             await nats_client.publish_update(existing, currency_data["rate"])
#                     else:
#                         # Создаем новую
#                         await CurrencyCRUD.create(db, CurrencyCreate(**currency_data))
#                         stats["created"] += 1
                        
#                 except Exception as e:
#                     logger.error(f"Ошибка обновления {currency_data.get('currency_code')}: {e}")
#                     stats["errors"] += 1
        
#         return stats
    
#     async def run_once(self) -> Dict:
#         """Однократный запуск задачи"""
#         logger.info("Запуск обновления курсов валют...")
        
#         try:
#             # 1. Получаем данные
#             data = await self.fetch_cbr_data()
            
#             # 2. Парсим
#             currencies = self.parse_currencies(data)
            
#             if not currencies:
#                 raise ValueError("Не удалось получить данные о валютах")
            
#             # 3. Обновляем БД
#             stats = await self.update_database(currencies)
            
#             # 4. Отправляем уведомления
#             await manager.broadcast({
#                 "type": "currencies_updated",
#                 "data": stats,
#                 "timestamp": datetime.now().isoformat()
#             })
            
#             # 5. Публикуем в NATS
#             await nats_client.publish_task_completed(stats)
            
#             self.last_run = datetime.now()
#             logger.info(f"Обновление завершено. Статистика: {stats}")
            
#             return {
#                 "status": "success",
#                 "stats": stats,
#                 "message": f"Обновлено {stats['updated'] + stats['created']} валют"
#             }
            
#         except Exception as e:
#             logger.error(f"Ошибка фоновой задачи: {e}")
#             return {
#                 "status": "error",
#                 "message": str(e)
#             }
    
#     async def run_periodically(self):
#         """Периодический запуск задачи"""
#         self.is_running = True
#         logger.info(f"Фоновая задача запущена (интервал: {self.interval} сек)")
        
#         while self.is_running:
#             try:
#                 await self.run_once()
#             except Exception as e:
#                 logger.error(f"Критическая ошибка фоновой задачи: {e}")
            
#             await asyncio.sleep(self.interval)
    
#     def start(self):
#         """Запуск задачи"""
#         if not self.is_running:
#             self.task = asyncio.create_task(self.run_periodically())
    
#     def stop(self):
#         """Остановка задачи"""
#         self.is_running = False
#         if self.task:
#             self.task.cancel()

# # Глобальный экземпляр
# background_task = BackgroundTask()

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, List
import logging

from app.config import settings
from app.crud import CurrencyCRUD
from app.schemas import CurrencyCreate, CurrencyUpdate
from app.database import AsyncSessionLocal
from app.ws.manager import manager
from app.nats.client import nats_client

logger = logging.getLogger(__name__)

class BackgroundTask:
    """Фоновая задача для обновления курсов валют"""
    
    def __init__(self):
        self.is_running = False
        self.task = None
        self.interval = settings.BACKGROUND_INTERVAL
        self.last_run = None
    
    async def fetch_cbr_data(self) -> Dict:
        """Получение данных с ЦБ РФ"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info("Запрос данных с ЦБ РФ...")
            response = await client.get(settings.CBR_API_URL)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Получено {len(data.get('Valute', {}))} валют с ЦБ РФ")
            return data
    
    async def fetch_crypto_data(self) -> List[Dict]:
        """Получение данных о криптовалютах с Binance"""
        crypto_pairs = {
            "BTCUSDT": "Bitcoin",
            "ETHUSDT": "Ethereum", 
            "BNBUSDT": "Binance Coin",
            "SOLUSDT": "Solana",
            "XRPUSDT": "Ripple"
        }
        
        crypto_currencies = []
        
        for symbol, name in crypto_pairs.items():
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        crypto_code = symbol.replace("USDT", "")
                        
                        crypto_currencies.append({
                            "currency_code": crypto_code,
                            "currency_name": f"{name} (Crypto)",
                            "rate": float(data['price']),
                            "nominal": 1
                        })
                        
            except Exception as e:
                logger.warning(f"Не удалось получить {symbol}: {e}")
                continue
        
        logger.info(f"Получено {len(crypto_currencies)} криптовалют")
        return crypto_currencies
    
    def parse_currencies(self, data: Dict) -> List[Dict]:
        """Парсинг данных о валютах"""
        currencies = []
        valute_data = data.get("Valute", {})
        
        # Только основные валюты
        main_currencies = ["USD", "EUR", "JPY", "CNY", "GBP", "CHF", "CAD", "AUD", "NZD", "SGD"]
        
        for code, info in valute_data.items():
            if code in main_currencies:
                try:
                    currencies.append({
                        "currency_code": code,
                        "currency_name": info.get("Name", ""),
                        "rate": float(info.get("Value", 0)),
                        "nominal": int(info.get("Nominal", 1))
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Ошибка парсинга валюты {code}: {e}")
                    continue
        
        return currencies
    
    async def update_database(self, currencies: List[Dict]) -> Dict:
        """Обновление базы данных"""
        stats = {"created": 0, "updated": 0, "errors": 0}
        
        async with AsyncSessionLocal() as db:
            for currency_data in currencies:
                try:
                    existing = await CurrencyCRUD.get_by_code(db, currency_data["currency_code"])
                    
                    if existing:
                        # Обновляем если курс изменился
                        if abs(existing.rate - currency_data["rate"]) > 0.0001:
                            await CurrencyCRUD.update(
                                db, 
                                existing.id, 
                                CurrencyUpdate(rate=currency_data["rate"])
                            )
                            stats["updated"] += 1
                            
                            # Публикуем в NATS
                            await nats_client.publish_update(existing, currency_data["rate"])
                    else:
                        # Создаем новую
                        await CurrencyCRUD.create(db, CurrencyCreate(**currency_data))
                        stats["created"] += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка обновления {currency_data.get('currency_code')}: {e}")
                    stats["errors"] += 1
        
        return stats
    
    async def run_once(self) -> Dict:
        """Однократный запуск задачи"""
        logger.info("Запуск обновления курсов валют...")
        
        # Отправляем уведомление о начале
        await manager.broadcast({
            "type": "background_task_started",
            "data": {"message": "Начинаем обновление курсов"},
            "timestamp": datetime.now().isoformat()
        })
        
        total_stats = {"created": 0, "updated": 0, "errors": 0}
        
        try:
            # 1. Традиционные валюты с ЦБ РФ
            try:
                cbr_data = await self.fetch_cbr_data()
                traditional_currencies = self.parse_currencies(cbr_data)
                
                if traditional_currencies:
                    stats = await self.update_database(traditional_currencies)
                    total_stats["created"] += stats["created"]
                    total_stats["updated"] += stats["updated"]
                    total_stats["errors"] += stats["errors"]
                    
                    logger.info(f"Традиционные валюты: {stats['created']} новых, {stats['updated']} обновлено")
            
            except Exception as e:
                logger.error(f"Ошибка обработки традиционных валют: {e}")
                total_stats["errors"] += 1
            
            # 2. Криптовалюты с Binance
            try:
                crypto_currencies = await self.fetch_crypto_data()
                
                if crypto_currencies:
                    stats = await self.update_database(crypto_currencies)
                    total_stats["created"] += stats["created"]
                    total_stats["updated"] += stats["updated"]
                    total_stats["errors"] += stats["errors"]
                    
                    logger.info(f"Криптовалюты: {stats['created']} новых, {stats['updated']} обновлено")
            
            except Exception as e:
                logger.error(f"Ошибка обработки криптовалют: {e}")
                total_stats["errors"] += 1
            
            # 3. Отправляем уведомления
            await manager.broadcast({
                "type": "currencies_updated",
                "data": {
                    "stats": total_stats,
                    "message": f"Обновлено: {total_stats['updated']} валют, создано: {total_stats['created']} новых"
                },
                "timestamp": datetime.now().isoformat()
            })
            
            # 4. Публикуем в NATS
            await nats_client.publish_task_completed(total_stats)
            
            self.last_run = datetime.now()
            logger.info(f"Обновление завершено. Статистика: {total_stats}")
            
            return {
                "status": "success",
                "stats": total_stats,
                "message": f"Обновлено {total_stats['updated'] + total_stats['created']} валют"
            }
            
        except Exception as e:
            logger.error(f"Ошибка фоновой задачи: {e}")
            
            await manager.broadcast({
                "type": "background_task_error",
                "data": {"error": str(e)},
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def run_periodically(self):
        """Периодический запуск задачи"""
        self.is_running = True
        logger.info(f"Фоновая задача запущена (интервал: {self.interval} сек)")
        
        while self.is_running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Критическая ошибка фоновой задачи: {e}")
            
            await asyncio.sleep(self.interval)
    
    def start(self):
        """Запуск задачи"""
        if not self.is_running:
            self.task = asyncio.create_task(self.run_periodically())
    
    def stop(self):
        """Остановка задачи"""
        self.is_running = False
        if self.task:
            self.task.cancel()

# Глобальный экземпляр
background_task = BackgroundTask()