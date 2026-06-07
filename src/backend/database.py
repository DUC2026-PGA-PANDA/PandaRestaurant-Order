import sqlite3
from .config import Config

DB_PATH = Config.DATABASE_PATH


def db_query(query, params=(), fetch_one=False, fetch_all=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    if fetch_one:
        result = cursor.fetchone()
    elif fetch_all:
        result = cursor.fetchall()
    else:
        result = cursor.lastrowid
        conn.commit()
    conn.close()
    return result


def init_database():
    # No-op database initialization helper; the application initializes schema directly.
    return None


def get_menu_items(category=None, subcategory=None):
    query = "SELECT * FROM menu_items"
    params = []
    if category is not None:
        query += " WHERE category = ?"
        params.append(category)
    elif subcategory is not None:
        query += " WHERE subcategory = ?"
        params.append(subcategory)

    rows = db_query(query, tuple(params), fetch_all=True)
    return [dict(row) for row in rows] if rows else []
