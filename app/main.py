# app/main.py

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json

from app.config import settings
from app.database import init_db
from app.api.endpoints import router as api_router
from app.ws.manager import manager
from app.tasks.background import background_task
from app.nats.client import nats_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Запуск {settings.APP_NAME} v{settings.VERSION}")
    
    # 1. Инициализация БД
    await init_db()
    logger.info("База данных инициализирована")
    
    # 2. Подключение к NATS
    await nats_client.connect()
    
    # 3. Запуск фоновой задачи
    background_task.start()
    logger.info(f"Фоновая задача запущена (интервал: {settings.BACKGROUND_INTERVAL} сек)")
    
    logger.info("Приложение готово")
    logger.info(f"API: http://localhost:8000/docs")
    logger.info(f"REST API: http://localhost:8000/api")
    logger.info(f"WebSocket: ws://localhost:8000/ws/currencies")
    
    yield
    
    # Shutdown
    logger.info("Остановка приложения...")
    
    # 1. Остановка фоновой задачи
    background_task.stop()
    
    # 2. Отключение от NATS
    await nats_client.disconnect()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. WebSocket endpoint
@app.websocket("/ws/currencies")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Получаем статус NATS
        from app.nats.client import nats_client
        nats_status = "connected" if nats_client.connected else "disconnected"
        # Отправляем приветственное сообщение
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket подключен",
            "timestamp": datetime.now().isoformat(),
            "nats_status": nats_status,  # Добавляем статус NATS
            "active_connections": len(manager.active_connections)
        })
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get('type') == 'ping':
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                elif message.get('type') == 'get_info':
                    await websocket.send_json({
                        "type": "info",
                        "timestamp": datetime.now().isoformat(),
                        "active_connections": len(manager.active_connections),
                        "server_time": datetime.now().isoformat()
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                    "timestamp": datetime.now().isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

# 2. Подключаем REST API роутер С префиксом /api
app.include_router(api_router, prefix=settings.API_PREFIX)  # /api

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "endpoints": {
            "currencies": "/api/currencies",
            "websocket": "/ws/currencies",
            "background_task": "/api/tasks/run",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "nats": "connected" if nats_client.connected else "disconnected",
        "background_task": "running" if background_task.is_running else "stopped"
    }