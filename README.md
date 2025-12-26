# Telegram Summary Mini-App Bot

Telegram mini-app (WebApp) bot that lets users define digest templates: collect posts from selected channels/chats, summarize them via DeepSeek AI, and send the digest to destination chats on a schedule.

## Features

- **FastAPI Backend** - REST API for the mini-app with CORS protection and rate limiting
- **SQLite + SQLAlchemy** - Async database with Alembic migrations
- **Telegram WebApp Auth** - Secure `initData` validation for user authentication
- **Telethon Client** - Fetching channel posts and sending digests
- **DeepSeek AI** - Intelligent summarization with structured prompts and retry logic
- **Async Scheduler** - Background worker that runs templates on schedule with concurrency control

## Architecture

```
tg-bot/
├── app/                    # FastAPI application
│   ├── main.py             # App entrypoint, lifespan, middleware
│   ├── config.py           # Pydantic settings from env
│   ├── db.py               # Async SQLAlchemy engine & session
│   ├── models.py           # ORM models (User, Template, etc.)
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── auth.py             # Telegram initData validation
│   ├── deepseek_client.py  # AI summarization with retry
│   ├── telegram_client.py  # Telethon bot/user clients
│   ├── rate_limit.py       # slowapi rate limiting
│   └── routers/
│       └── templates.py    # CRUD endpoints for templates
├── worker/
│   ├── scheduler.py        # Main loop checking due templates
│   └── processor.py        # Fetch → Summarize → Send pipeline
├── frontend/               # Telegram WebApp UI
│   ├── index.html          # iOS-style interface
│   └── main.js             # Frontend logic
├── alembic/                # Database migrations
│   ├── env.py
│   └── versions/
├── tests/                  # Pytest test suite
└── requirements.txt
```

## Getting Started

### Prerequisites

- Python 3.10+
- Telegram Bot (create via [@BotFather](https://t.me/BotFather))
- Telegram API credentials (get from [my.telegram.org](https://my.telegram.org))
- DeepSeek API key (get from [platform.deepseek.com](https://platform.deepseek.com))

### Installation

1. **Clone and setup environment**
   ```bash
   git clone <repository>
   cd tg-bot
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

2. **Configure environment variables**
   ```bash
   cp env.example .env
   # Edit .env with your credentials
   ```

3. **Initialize database**
   ```bash
   # Using Alembic (recommended for production)
   alembic upgrade head
   
   # Or auto-create on first run (development)
   # Tables are created automatically on app startup
   ```

4. **Run the application**
   ```bash
   # Start FastAPI server
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   
   # In another terminal, start the scheduler
   python -m worker.scheduler
   ```

5. **Configure Telegram Bot**
   - Open [@BotFather](https://t.me/BotFather)
   - Send `/mybots` → Select your bot → Bot Settings → Menu Button
   - Set Menu Button URL to your hosting URL (e.g., `https://your-domain.com/app`)

### Generate User Session (Optional)

To fetch from private channels where the bot can't read:

```bash
python stringSession.py
```

Copy the generated session string to `TELEGRAM_SESSION` in `.env`.

## API Reference

### Authentication

All endpoints require `X-Telegram-Init-Data` header with valid Telegram WebApp initData.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/templates/` | List user's templates |
| POST | `/api/templates/` | Create new template |
| PUT | `/api/templates/{id}` | Update template |
| DELETE | `/api/templates/{id}` | Delete template |
| POST | `/api/templates/{id}/toggle` | Toggle active status |
| POST | `/api/templates/{id}/run-now` | Trigger immediate run |
| GET | `/api/templates/targets` | List available target chats |

### Rate Limits

- `GET /api/templates/` - 30 requests/minute
- `POST /api/templates/` - 10 requests/minute
- `POST /{id}/run-now` - 5 requests/minute

## Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

See `env.example` for all available options:

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_API_ID` | Yes | Telegram API ID |
| `TELEGRAM_API_HASH` | Yes | Telegram API Hash |
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key |
| `DATABASE_URL` | No | Database connection string |
| `WEBAPP_BASE_URL` | No | Base URL for CORS |
| `SCHEDULER_INTERVAL_SECONDS` | No | Check interval (default: 300) |

### Production Checklist

- [ ] Set `WEBAPP_BASE_URL` to your production domain
- [ ] Use PostgreSQL instead of SQLite for better concurrency
- [ ] Run behind reverse proxy (nginx) with HTTPS
- [ ] Set up process manager (systemd, supervisor)
- [ ] Configure log aggregation
- [ ] Set up monitoring and alerts

## Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=worker --cov-report=html

# Run specific test file
pytest tests/test_deepseek_client.py -v
```

## Development

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Code Style

The project uses standard Python conventions. Key dependencies:
- FastAPI for async web framework
- SQLAlchemy 2.0 with async support
- Pydantic v2 for validation
- Telethon for Telegram MTProto
- tenacity for retry logic

## License

MIT
