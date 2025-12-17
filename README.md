# Telegram Summary Mini-App Bot

Telegram mini-app (WebApp) bot that lets users define digest templates: collect posts from selected channels/chats, summarize them via DeepSeek, and send the digest to destination chats on a schedule.

## Features
- FastAPI backend for the mini-app API and static assets.
- SQLite + SQLAlchemy for storing users, templates, sources, and run logs.
- Telegram WebApp `initData` validation for user auth.
- Telethon client for fetching channel posts and sending digests.
- DeepSeek API integration for AI summaries.
- Async scheduler worker that periodically runs templates with concurrency control.

## Getting Started
1. Copy `.env.example` to `.env` and fill required values.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run FastAPI app: `uvicorn app.main:app --reload`.
4. Run scheduler worker: `python -m worker.scheduler`.
5. Configure your Telegram bot to show the WebApp button pointing to your hosting URL.

## Tests
```
pytest
```
