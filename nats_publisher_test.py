#!/usr/bin/env python3
"""
Тестовый NATS publisher для демонстрации
Можно запускать вручную для проверки подписчика
"""

import asyncio
import json
from datetime import datetime
import nats

async def main():
    """Отправка тестовых сообщений в NATS"""
    print("Запуск тестового NATS Publisher...")
    
    try:
        nc = await nats.connect("nats://localhost:4222")
        print("Подключено к NATS")
        
        # Тестовое сообщение 1
        test_msg_1 = {
            "type": "test_message",
            "message": "Тестовое сообщение от publisher",
            "timestamp": datetime.now().isoformat(),
            "data": {"test": 123, "value": "hello"}
        }
        
        await nc.publish("currency.updates", json.dumps(test_msg_1).encode())
        print("Отправлено тестовое сообщение в currency.updates")
        
        # Тестовое сообщение 2 (имитация обновления валюты)
        test_msg_2 = {
            "type": "currency_updated",
            "currency_code": "USD",
            "currency_name": "US Dollar",
            "old_rate": 75.50,
            "new_rate": 76.20,
            "change": 0.70,
            "timestamp": datetime.now().isoformat()
        }
        
        await nc.publish("currency.updates", json.dumps(test_msg_2).encode())
        print("Отправлено имитация обновления USD")
        
        # Тестовое сообщение 3 (имитация фоновой задачи)
        test_msg_3 = {
            "type": "background_task_completed",
            "stats": {
                "currencies_updated": 15,
                "traditional": 10,
                "crypto": 5,
                "message": "Фоновая задача завершена",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        await nc.publish("currency.events", json.dumps(test_msg_3).encode())
        print("Отправлено имитация завершения фоновой задачи")
        
        await nc.drain()
        print("Все тестовые сообщения отправлены")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        print("Убедитесь, что NATS сервер запущен!")

if __name__ == "__main__":
    asyncio.run(main())