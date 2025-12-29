#!/usr/bin/env python3
"""
Отдельный NATS subscriber для демонстрации работы с сообщениями
Запускается независимо от основного приложения
"""

import asyncio
import json
import logging
from datetime import datetime

# Установить pip install nats-py
import nats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция подписчика"""
    logger.info("🚀 Запуск NATS Subscriber...")
    
    try:
        # Подключаемся к NATS серверу
        nc = await nats.connect("nats://localhost:4222")
        logger.info("Подключено к NATS серверу")
        
        async def message_handler(msg):
            """Callback-функция для обработки сообщений"""
            try:
                data = json.loads(msg.data.decode())
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                print(f"\n{'='*50}")
                print(f"📨 [{timestamp}] Новое сообщение из NATS")
                print(f"   Канал: {msg.subject}")
                print(f"   Тип: {data.get('type', 'unknown')}")
                
                if data.get('type') == 'currency_updated':
                    print(f"   Валюта: {data.get('currency_code')}")
                    print(f"   Старый курс: {data.get('old_rate')}")
                    print(f"   Новый курс: {data.get('new_rate')}")
                    print(f"   Изменение: {data.get('change'):.4f}")
                
                elif data.get('type') == 'background_task_completed':
                    print(f"   Задача: {data.get('stats', {}).get('message', 'completed')}")
                    print(f"   Обновлено валют: {data.get('stats', {}).get('currencies_updated', 0)}")
                
                print(f"{'='*50}")
                
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
        
        # Подписываемся на каналы с callback
        await nc.subscribe("currency.updates", cb=message_handler)
        await nc.subscribe("currency.events", cb=message_handler)
        
        logger.info("📡 Подписка оформлена на каналы:")
        logger.info("   - currency.updates (обновления валют)")
        logger.info("   - currency.events (события задач)")
        logger.info("\nОжидание сообщений... (Ctrl+C для выхода)")
        
        # Бесконечно ждем сообщений
        while True:
            await asyncio.sleep(3600)  # Спим 1 час
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        logger.info("Убедитесь, что NATS сервер запущен:")
        logger.info("  docker run -d -p 4222:4222 --name nats-server nats")

if __name__ == "__main__":
    asyncio.run(main())