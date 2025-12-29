# Currency Monitoring Backend Service

Проект предназначен для мониторинга курсов валют и включает в себя:

- **REST API** для управления валютами
- **WebSocket** для обновлений курсов в реальном времени
- **Фоновая задача** парсинга курсов из ЦБ РФ и криптобирж
- **NATS** для асинхронной коммуникации
- **Асинхронная работа** с БД (SQLite/SQLAlchemy)

## Технологический стек
- **FastAPI** - асинхронный веб-фреймворк
- **SQLAlchemy 2.0** - асинхронная ORM
- **NATS** - брокер сообщений
- **WebSocket** - соединение между клиентом и сервером
- **HTTpx** - асинхронные HTTP-запросы
- **Pydantic** - валидация данных

## Запуск проекта

### 1. Клонирование и настройка
```bash
# Клонируйте репозиторий
git clone https://github.com/Ksenia1102/currency-webapi.git
cd currency-webapi

# Установите зависимости
pip install -r requirements.txt
```

### 2. Запуск приложения и NATS сервера вручную
```bash
# запустить сервер
docker run -d -p 4222:4222 -p 8222:8222 --name currency-nats nats -m 8222

# Заупстить приложение
python run.py
```
откройте index.html

## Доступ к сервисам
После запуска сервис будет доступен по следующим адресам:

- API: http://localhost:8000
- Документация (Swagger): http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/currencies

## Основные возможности

REST API

- GET /api/currencies - получить список всех валют
- GET /api/currencies/{id} - получить валюту по ID
- POST /api/currencies- создать новую валюту
- PATCH	/api/currencies/{id} - обновить валюту
- DELETE /api/currencies/{id} - удалить валюту (через интерфейс страницы только пользовательскую)
- POST	/api/tasks/run - принудительно запустить фоновую задачу
- GET	/api/tasks/status - получить статус фоновой задачи
- GET	/health	- проверка работоспособности сервиса

## Фоновая задача

- Автоматически получает курсы валют с ЦБ РФ (55+ валют)
- Автоматически получает курсы криптовалют с CoinGecko API (Bitcoin, Ethereum)
- Интервал обновления: 30 секунд (настраивается через .env)
- Сохраняет новые курсы в базу данных
- Отправляет уведомления через WebSocket и NATS
- Поддерживает ручной запуск через API

## NATS

- Публикация событий в канал currency.updates
- Публикация событий задач в канал currency.events
- Подписка на внешние события
- Асинхронная обработка сообщений

Пример работы subscriber + publisher можно посмотреть запустив скрипты в отдельных терминалах:

```bash
python nats_subscriber.py
```

и

```bash
python nats_publisher_test.py
```