import json
import logging
from typing import Dict, Any
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

class NATSClient:
    """Клиент для работы с NATS"""
    
    def __init__(self):
        self.connected = False
        self.nc = None
    
    async def connect(self):
        """Подключение к NATS серверу"""
        if not settings.NATS_ENABLED:
            logger.info("NATS отключен в настройках")
            return
        
        try:
            import nats
            
            self.nc = await nats.connect(settings.NATS_URL)
            self.connected = True
            
            # Подписываемся на каналы
            await self.nc.subscribe(
                settings.NATS_UPDATES_CHANNEL,
                cb=self.handle_update
            )
            
            logger.info(f"✅ Подключено к NATS: {settings.NATS_URL}")
            
        except ImportError:
            logger.warning("❌ Библиотека nats-py не установлена. Установите: pip install nats-py")
            self.connected = False
        except Exception as e:
            logger.warning(f"❌ Не удалось подключиться к NATS: {e}")
            self.connected = False
    
    async def handle_update(self, msg):
        """Обработка сообщений из NATS"""
        try:
            data = json.loads(msg.data.decode())
            logger.info(f"NATS сообщение: {data.get('type')}")
            
            # Отправляем уведомление в WebSocket
            from app.ws.manager import manager
            await manager.broadcast({
                "type": "nats_message_received",
                "data": data,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Ошибка обработки NATS сообщения: {e}")
    
    async def publish_task_completed(self, stats: Dict[str, Any]):
        """Публикация события завершения фоновой задачи"""
        if not self.connected:
            logger.debug("NATS не подключен, пропускаем публикацию задачи")
            return
        
        message = {
            "type": "background_task_completed",
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await self.nc.publish(
                settings.NATS_EVENTS_CHANNEL,
                json.dumps(message).encode()
            )
            logger.info("Опубликовано завершение фоновой задачи в NATS")
            
            # Также отправляем в WebSocket
            from app.ws.manager import manager
            await manager.broadcast({
                "type": "nats_task_completed",
                "data": message,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Ошибка публикации в NATS: {e}")

    async def publish_currency_update(self, currency, new_rate: float):
        """Публикация обновления курса валюты"""
        if not self.connected:
            # Если NATS не подключен, просто логируем
            logger.debug("NATS не подключен, пропускаем публикацию")
            return
        
        # currency может быть как объектом модели, так и словарем
        if hasattr(currency, 'currency_code'):
            currency_code = currency.currency_code
            currency_name = currency.currency_name
            old_rate = currency.rate
        else:
            # Если это словарь
            currency_code = currency.get('currency_code', '')
            currency_name = currency.get('currency_name', '')
            old_rate = currency.get('rate', 0)
        
        message = {
            "type": "currency_updated",
            "currency_code": currency_code,
            "currency_name": currency_name,
            "old_rate": old_rate,
            "new_rate": new_rate,
            "change": new_rate - old_rate,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await self.nc.publish(
                settings.NATS_UPDATES_CHANNEL,
                json.dumps(message).encode()
            )
            logger.info(f"📤 Опубликовано в NATS: {currency_code}")
            
            # отправляем в WebSocket
            from app.ws.manager import manager
            await manager.broadcast({
                "type": "nats_currency_update",
                "data": message,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в NATS: {e}")
    
    async def disconnect(self):
        """Отключение от NATS"""
        if self.connected and self.nc:
            await self.nc.drain()
            await self.nc.close()
            self.connected = False
            logger.info("Отключено от NATS")

# Глобальный экземпляр
nats_client = NATSClient()