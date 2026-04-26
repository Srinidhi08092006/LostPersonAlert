import sqlite3
import os

DB_NAME = 'alerts.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Create alerts table
    c.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            area TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            contact TEXT NOT NULL,
            photo TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Migrations
    try:
        c.execute('ALTER TABLE alerts ADD COLUMN device_id TEXT')
    except sqlite3.OperationalError:
        pass
        
    try:
        c.execute('ALTER TABLE alerts ADD COLUMN is_iot_updated INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE alerts ADD COLUMN user_id INTEGER')
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()
