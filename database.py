import os
import logging
import psycopg2
from urllib.parse import urlparse  # Виправлений імпорт
from telegram.error import TelegramError
from psycopg2.extras import Json

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
                phone_number VARCHAR(32),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE,
                is_subscribed BOOLEAN DEFAULT FALSE,
                language_code VARCHAR(10),
                interaction_count INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE
            )
        """)
        # На випадок, якщо таблиця створена раніше без phone_number
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32)
        """)
        
        # Якщо раніше зберігали телефони у user_contacts — перенесемо їх у users
        try:
            cur.execute("SELECT to_regclass('public.user_contacts')")
            exists = cur.fetchone()[0]
            if exists:
                cur.execute(
                    """
                    UPDATE users u
                    SET phone_number = c.phone_number,
                        first_name = COALESCE(u.first_name, c.first_name),
                        last_name  = COALESCE(u.last_name,  c.last_name),
                        updated_at = NOW()
                    FROM user_contacts c
                    WHERE u.user_id = c.user_id
                      AND (u.phone_number IS NULL OR u.phone_number = '')
                    """
                )
        except Exception as migrate_err:
            logger.warning(f"Міграція телефонів із user_contacts пропущена: {migrate_err}")
        
        # Таблиця логів переписок
        cur.execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                direction VARCHAR(10) NOT NULL, -- 'in' або 'out'
                message_type VARCHAR(50) NOT NULL,
                content TEXT,
                extra JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_logs_user_created
            ON message_logs(user_id, created_at)
        """)

        conn.commit()
        logger.info(f"База даних ініціалізована (db={DB_NAME}, host={DB_HOST})")
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

# Збереження контакту користувача (в таблиці users)
def save_contact(user_id, phone_number, first_name=None, last_name=None):
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
        # Спочатку пробуємо оновити існуючого користувача
        cur.execute(
            """
            UPDATE users
            SET phone_number = %s,
                first_name = COALESCE(%s, first_name),
                last_name = COALESCE(%s, last_name),
                updated_at = NOW()
            WHERE user_id = %s
            """,
            (phone_number, first_name, last_name, user_id),
        )
        # Якщо рядків не оновлено — вставляємо нового користувача
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name, phone_number, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET phone_number = EXCLUDED.phone_number,
                    first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                    last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                    updated_at = NOW()
                """,
                (user_id, None, first_name, last_name, phone_number),
            )
        conn.commit()
        logger.info(f"Контакт (phone) для користувача {user_id} збережений у users")
    except Exception as e:
        logger.error(f"Помилка збереження телефону для {user_id}: {e}")
    finally:
        if conn is not None:
            conn.close()

# Лог переписки
def log_message(user_id: int, direction: str, message_type: str, content: str | None = None, extra: dict | None = None):
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
        cur.execute(
            """
            INSERT INTO message_logs (user_id, direction, message_type, content, extra)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, direction, message_type, content, Json(extra) if extra is not None else None),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Помилка запису логу для {user_id}: {e}")
    finally:
        if conn is not None:
            conn.close()
