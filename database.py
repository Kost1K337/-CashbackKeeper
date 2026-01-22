import sqlite3

DB_PATH = "bot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        UNIQUE(user_id, name),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER,
        name TEXT,
        cashback INTEGER,
        FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
    )
    """)

    conn.commit()
    conn.close()


# -------- users --------
def get_or_create_user(telegram_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
        (telegram_id,)
    )
    conn.commit()
    cursor.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    user_id = cursor.fetchone()[0]
    conn.close()
    return user_id


# -------- cards --------
def add_card(user_id: int, name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cards (user_id, name) VALUES (?, ?)",
        (user_id, name)
    )
    conn.commit()
    conn.close()


def get_cards(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM cards WHERE user_id = ?",
        (user_id,)
    )
    result = cursor.fetchall()
    conn.close()
    return result  # [(id, name)]


def get_card_id(user_id: int, card_name: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM cards WHERE user_id = ? AND name = ?",
        (user_id, card_name)
    )
    card_id = cursor.fetchone()[0]
    conn.close()
    return card_id


# -------- categories --------
def add_category(card_id: int, name: str, cashback: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO categories (card_id, name, cashback) VALUES (?, ?, ?)",
        (card_id, name, cashback)
    )
    conn.commit()
    conn.close()


def get_best_cashback(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        categories.name,
        MAX(categories.cashback),
        cards.name
    FROM categories
    JOIN cards ON categories.card_id = cards.id
    WHERE cards.user_id = ?
    GROUP BY categories.name
    ORDER BY MAX(categories.cashback) DESC
    """, (user_id,))
    result = cursor.fetchall()
    conn.close()
    return result
