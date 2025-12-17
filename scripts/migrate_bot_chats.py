"""Migration script to update bot_chats table with user_id column."""

import sqlite3
import pathlib

db_path = pathlib.Path("data/app.db")

if not db_path.exists():
    print("Database not found, skipping migration")
    exit(0)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check if old table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_chats'")
if not cur.fetchone():
    print("bot_chats table not found, skipping migration")
    conn.close()
    exit(0)

# Check if user_id column already exists
cur.execute("PRAGMA table_info(bot_chats)")
cols = [r[1] for r in cur.fetchall()]
print("Current columns:", cols)

if "user_id" in cols:
    print("user_id column already exists, skipping migration")
    conn.close()
    exit(0)

# Drop the old table and let SQLAlchemy recreate it
print("Dropping old bot_chats table...")
cur.execute("DROP TABLE IF EXISTS bot_chats")
conn.commit()

print("Migration complete. The table will be recreated on next app startup.")
conn.close()

