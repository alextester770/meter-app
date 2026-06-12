import sqlite3

def init_db():
    conn = sqlite3.connect("meters.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS meters (
        id TEXT,
        idg TEXT,
        idw TEXT,
        iin TEXT,
        name TEXT,
        position TEXT,
        prev REAL,
        prevg REAL,
        prevw REAL,
        period TEXT,
        org TEXT,
        edit_count INTEGER DEFAULT 0,
        edit_countg INTEGER DEFAULT 0,
        edit_countw INTEGER DEFAULT 0,
        current REAL DEFAULT 0,
        currentg REAL DEFAULT 0,
        currentw REAL DEFAULT 0,
        dolg INTEGER DEFAULT 0,
        date TEXT,
        kod_dogovora TEXT,
        rent INTEGER DEFAULT 0,   
        ePrice INTEGER DEFAULT 0,
        gPrice INTEGER DEFAULT 0,
        wPrice INTEGER DEFAULT 0,
        pim TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()