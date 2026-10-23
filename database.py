"""
Database layer for the Family Chore Chart Kiosk App.
Uses built-in sqlite3 for zero-configuration portability across PC and Mac.
"""
import os
import sqlite3
from datetime import date, timedelta

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chores.db")


def get_db_connection(db_path=None):
    """Return a sqlite3 connection with Row factory enabled."""
    target_path = db_path or os.environ.get("CHORE_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    """Create tables if they do not exist and seed initial sample data if empty."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            avatar TEXT NOT NULL DEFAULT '😎',
            color TEXT NOT NULL DEFAULT '#6366f1',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT NOT NULL DEFAULT '✨',
            category TEXT NOT NULL DEFAULT 'house',
            points INTEGER NOT NULL DEFAULT 10,
            frequency_type TEXT NOT NULL DEFAULT 'daily',
            days_of_week TEXT NOT NULL DEFAULT '',
            time_of_day TEXT NOT NULL DEFAULT 'any',
            anchor_date TEXT NOT NULL DEFAULT '2026-10-18',
            assigned_user_id INTEGER NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chore_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            target_date TEXT NOT NULL,
            slot TEXT NOT NULL DEFAULT 'ANY',
            points_earned INTEGER NOT NULL,
            was_stolen INTEGER NOT NULL DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chore_id, target_date, slot),
            FOREIGN KEY (chore_id) REFERENCES chores(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    # Seed settings if missing
    default_settings = {
        "household_name": "House HQ Chore Quest",
        "champion_reward": "Picks Friday Night Takeout (Zero Veto Power!) 🍕👑",
        "last_place_penalty": "Buys the next round of coffee or drinks! ☕🍺",
    }
    for k, v in default_settings.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Seed 3 default adults if no users exist yet
    cur.execute("SELECT COUNT(*) as cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        sample_users = [
            ("Alex", "🦊", "#6366f1"),
            ("Jordan", "🦖", "#10b981"),
            ("Sam", "🚀", "#f59e0b"),
        ]
        cur.executemany(
            "INSERT INTO users (name, avatar, color) VALUES (?, ?, ?)",
            sample_users,
        )

    # Seed sample chores if no chores exist yet
    cur.execute("SELECT COUNT(*) as cnt FROM chores")
    if cur.fetchone()["cnt"] == 0:
        # Compute most recent Sunday as a clean anchor for biweekly Sunday recycling
        today = date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        recent_sunday = (today - timedelta(days=days_since_sunday)).isoformat()

        sample_chores = [
            # (name, icon, category, points, frequency_type, days_of_week, time_of_day, anchor_date, assigned_user_id)
            ("Walk the Dog", "🐕", "dog", 15, "twice_daily", "", "both", recent_sunday, None),
            ("Feed the Dog", "🦴", "dog", 10, "twice_daily", "", "both", recent_sunday, None),
            ("Pick Up Dog Poop", "💩", "poop", 25, "daily", "", "any", recent_sunday, None),
            ("Clean the Kitchen", "🧽", "kitchen", 20, "daily", "", "evening", recent_sunday, None),
            ("Take Out the Trash", "🗑️", "trash", 20, "weekly", "0,3", "evening", recent_sunday, None),
            ("Take Out Recyclables", "♻️", "trash", 25, "biweekly", "6", "evening", recent_sunday, None),
        ]
        cur.executemany(
            """
            INSERT INTO chores
            (name, icon, category, points, frequency_type, days_of_week, time_of_day, anchor_date, assigned_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_chores,
        )

    conn.commit()
    conn.close()
