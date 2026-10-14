import sqlite3
import os
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reset_token TEXT,
        reset_expires TIMESTAMP
    );
    """)
    
    # 2. Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    
    # 3. Tasks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        start_time TEXT,
        end_time TEXT,
        duration_min INTEGER DEFAULT 30,
        priority TEXT CHECK(priority IN ('high', 'medium', 'low')) DEFAULT 'medium',
        deadline TEXT,
        status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'postponed')) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    
    # 4. Calendar Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        all_day INTEGER DEFAULT 0,
        event_type TEXT DEFAULT 'event',
        task_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
    );
    """)
    
    # 5. Schedule Proposals Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedule_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        raw_prompt TEXT NOT NULL,
        summary TEXT NOT NULL,
        proposals_json TEXT NOT NULL,
        conflicts_json TEXT DEFAULT '[]',
        status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    
    # 6. User Preferences Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER PRIMARY KEY,
        quiet_hours_start TEXT DEFAULT '22:00',
        quiet_hours_end TEXT DEFAULT '07:00',
        notifications_enabled INTEGER DEFAULT 1,
        sound_enabled INTEGER DEFAULT 1,
        theme TEXT DEFAULT 'dark',
        default_game_duration INTEGER DEFAULT 5,
        ai_mode TEXT DEFAULT 'builtin',
        api_key TEXT DEFAULT '',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    
    # 7. Game Scores Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_id TEXT NOT NULL,
        score INTEGER NOT NULL,
        level_reached INTEGER DEFAULT 1,
        duration_sec INTEGER NOT NULL,
        accuracy REAL DEFAULT 100.0,
        played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    
    # 8. Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        task_id INTEGER,
        message TEXT NOT NULL,
        notification_type TEXT DEFAULT 'task_checkin',
        action_taken TEXT DEFAULT 'none',
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
    );
    """)

    # Indexes for fast querying & tenant isolation
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_user_id ON calendar_events(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_scores_user_id ON game_scores(user_id, game_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id, is_read);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("MentiNous AI Database initialized successfully.")
