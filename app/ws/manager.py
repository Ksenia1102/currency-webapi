import json
from typing import List, Dict, Any
from fastapi import WebSocket
from datetime import datetime

class ConnectionManager:
    """Менеджер WebSocket соединений"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Подключение клиента"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Новое подключение. Всего: {len(self.active_connections)}")
        
        # Отправляем приветственное сообщение
        await self.send_personal(
            websocket,
            {
                "type": "connected",
                "message": "WebSocket подключен",
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def disconnect(self, websocket: WebSocket):
        """Отключение клиента"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WS] Отключение. Осталось: {len(self.active_connections)}")
    
    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]):
        """Отправка сообщения конкретному клиенту"""
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Отправка сообщения всем клиентам"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for connection in disconnected:
            self.disconnect(connection)

    async def send_nats_notification(self, nats_message: Dict[str, Any]):
        """Специальный метод для NATS уведомлений"""
        notification = {
            "type": "nats_notification",
            "data": nats_message,
            "timestamp": datetime.now().isoformat(),
            "source": "nats"
        }
        await self.broadcast(notification)
        
# Глобальный экземпляр
manager = ConnectionManager()