import sqlite3

def init_db():
    conn = sqlite3.connect("meters.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS meters (
        id TEXT,
        iin TEXT,
        name TEXT,
        position TEXT,
        prev REAL,
        period TEXT,
        org TEXT,
        edit_count INTEGER DEFAULT 0,
        current REAL DEFAULT 0,
        dolg INTEGER DEFAULT 0,
        date TEXT,
        kod_dogovora TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()