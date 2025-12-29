# app/main.py - ИСПРАВЛЕННЫЙ
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json

from app.config import settings
from app.db.database import init_db
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
    
    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована")
    
    # Запуск фоновой задачи
    background_task.start()
    logger.info(f"Фоновая задача запущена (интервал: {settings.BACKGROUND_INTERVAL} сек)")
    
    logger.info("Запуск первичной загрузки валют...")
    asyncio.create_task(background_task.run_once())
    
     # Подключение к NATS
    if settings.NATS_ENABLED:
        asyncio.create_task(nats_client.connect())
        logger.info("Попытка подключения к NATS в фоновом режиме...")
    else:
        logger.info("NATS отключен в настройках")

        
    logger.info("Приложение готово")
    logger.info(f"API: http://localhost:8000/docs")
    logger.info(f"REST API: http://localhost:8000{settings.API_PREFIX}")
    logger.info(f"WebSocket: ws://localhost:8000/ws/currencies")
    
    yield
    
    # Shutdown
    logger.info("Остановка приложения...")
    
    # 1. Остановка фоновой задачи
    background_task.stop()
    
    # 2. Отключение от NATS
    if nats_client.connected:
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

@app.websocket("/ws/currencies")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Получаем статус NATS
        nats_status = "connected" if nats_client.connected else "disconnected"
        
        # Отправляем сообщение
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket подключен",
            "timestamp": datetime.now().isoformat(),
            "nats_status": nats_status,
            "active_connections": len(manager.active_connections)
        })
        
        # Основной цикл WebSocket
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
                        "server_time": datetime.now().isoformat(),
                        "nats_status": nats_status
                    })
                elif message.get('type') == 'get_nats_status':
                    await websocket.send_json({
                        "type": "nats_status",
                        "status": nats_status,
                        "timestamp": datetime.now().isoformat()
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                    "timestamp": datetime.now().isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket клиент отключен")

app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "endpoints": {
            "currencies": f"{settings.API_PREFIX}/currencies",
            "websocket": "/ws/currencies",
            "background_task": f"{settings.API_PREFIX}/tasks/run",
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "nats": "connected" if nats_client.connected else "disconnected",
        "background_task": "running" if background_task.is_running else "stopped",
        "active_ws_connections": len(manager.active_connections)
    }