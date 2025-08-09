import os
import logging
import psycopg2
from urllib.parse import urlparse  # Виправлений імпорт
from telegram.error import TelegramError

# Налаштування логування
logger = logging.getLogger(__name__)

# Змінні середовища
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Розбір DATABASE_URL для psycopg2
    url = urlparse(DATABASE_URL)
    DB_HOST = url.hostname
    DB_PORT = url.port
    DB_USER = url.username
    DB_PASSWORD = url.password
    DB_NAME = url.path[1:]  # Прибираємо початкову "/"
else:
    DB_HOST = os.getenv("PGHOST")
    DB_PORT = os.getenv("PGPORT")
    DB_USER = os.getenv("PGUSER")
    DB_PASSWORD = os.getenv("PGPASSWORD")
    DB_NAME = os.getenv("PGDATABASE")

# Ініціалізація бази даних
def init_db():
    conn = None  # Ініціалізація conn як None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE,
                is_subscribed BOOLEAN DEFAULT FALSE,
                language_code VARCHAR(10),
                interaction_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE
            )
        """)
        conn.commit()
        logger.info("База даних ініціалізована")
    except Exception as e:
        logger.error(f"Помилка ініціалізації бази даних: {e}")
    finally:
        if conn is not None:  # Закриваємо лише якщо з’єднання існує
            conn.close()

# Завантаження списку користувачів
def load_users(subscribed_only=True):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        if subscribed_only:
            cur.execute("""
                SELECT user_id FROM users WHERE is_subscribed = TRUE AND is_blocked = FALSE
            """)
        else:
            cur.execute("""
                SELECT user_id FROM users WHERE is_blocked = FALSE
            """)
        users = [row[0] for row in cur.fetchall()]
        return users
    except Exception as e:
        logger.error(f"Помилка завантаження користувачів: {e}")
        return []
    finally:
        if conn is not None:
            conn.close()

# Збереження користувача
def save_user(user_id, username=None, first_name=None, last_name=None, language_code=None):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, language_code, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                language_code = EXCLUDED.language_code,
                updated_at = NOW()
        """, (user_id, username, first_name, last_name, language_code))
        conn.commit()
        logger.info(f"Користувач {user_id} збережений")
    except Exception as e:
        logger.error(f"Помилка збереження користувача {user_id}: {e}")
    finally:
        if conn is not None:
            conn.close()

# Оновлення статусу підписки
def update_subscription_status(user_id, is_subscribed):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET is_subscribed = %s,
                updated_at = NOW(),
                interaction_count = interaction_count + 1
            WHERE user_id = %s
        """, (is_subscribed, user_id))
        conn.commit()
        logger.info(f"Статус підписки для користувача {user_id} оновлено: {is_subscribed}")
    except Exception as e:
        logger.error(f"Помилка оновлення статусу підписки для {user_id}: {e}")
    finally:
        if conn is not None:
            conn.close()

# Оновлення статусу блокування
def update_blocked_status(user_id, is_blocked):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET is_blocked = %s,
                updated_at = NOW()
            WHERE user_id = %s
        """, (is_blocked, user_id))
        conn.commit()
        logger.info(f"Статус блокування для користувача {user_id} оновлено: {is_blocked}")
    except Exception as e:
        logger.error(f"Помилка оновлення статусу блокування для {user_id}: {e}")
    finally:
        if conn is not None:
            conn.close()
