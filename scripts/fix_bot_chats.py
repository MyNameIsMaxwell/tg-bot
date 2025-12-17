import sqlite3
from pathlib import Path


def main():
    path = Path("data/app.db")
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(bot_chats)")
    cols = [r[1] for r in cur.fetchall()]
    print("Columns:", cols)
    if "access_hash" not in cols:
        cur.execute("ALTER TABLE bot_chats ADD COLUMN access_hash BIGINT")
        conn.commit()
        print("Added access_hash")
    else:
        print("access_hash already exists")
    conn.close()


if __name__ == "__main__":
    main()

