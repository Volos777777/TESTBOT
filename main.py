import os
import signal
import logging
import time
import asyncio
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import TelegramError, Conflict
from broadcast import broadcast  # Імпорт broadcast з окремого файлу
from database import init_db, load_users, save_user, update_subscription_status, update_blocked_status, save_contact  # Імпорт з database.py

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Змінні середовища
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1002834216129"  # Перевірте та оновіть цей ID для https://t.me/+QPGNI10IfqU5MGEy
CHANNEL_LINK = "https://t.me/+ZzEgiQVCP6s2Y2Ji"  # Посилання на канал
DATABASE_URL = os.getenv("DATABASE_URL")

# Обробник команди /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    save_user(
        user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code
    )
    
    # Створюємо клавіатуру для запиту контактів
    keyboard = [[KeyboardButton("Поділитися контактом", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Вітаємо {user.first_name}! Для продовження роботи потрібно поділитися вашим контактом.",
        reply_markup=reply_markup
    )

# Обробник отримання контактів
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    contact = update.message.contact
    
    if contact:
        # Зберігаємо контакт в базу даних
        save_contact(
            user_id=user.id,
            phone_number=contact.phone_number,
            first_name=contact.first_name,
            last_name=contact.last_name
        )
        
        # Видаляємо клавіатуру з контактами
        await update.message.reply_text(
            "Дякуємо! Тепер ви можете продовжити роботу з ботом.",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
        
        # Відправляємо основне повідомлення з зображенням
        await send_main_message(update, context)
        
        # Запускаємо таймер для повторної відправки
        asyncio.create_task(schedule_reminder(update, context))
    else:
        await update.message.reply_text("Будь ласка, поділіться вашим контактом для продовження роботи.")

# Функція відправки основного повідомлення з зображенням
async def send_main_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Перевіряємо чи існує файл зображення та чи це дійсно зображення
        image_path = "images/bot_image.png"
        if os.path.exists(image_path) and os.path.getsize(image_path) > 1000:  # Перевіряємо розмір файлу
            # Відправляємо зображення
            with open(image_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption="Вітаємо! Тут бренди шукають креаторів для співпраці."
                )
        else:
            # Якщо зображення не знайдено або занадто мале, відправляємо тільки текст
            raise FileNotFoundError("Зображення не знайдено або некоректне")
        
    except (FileNotFoundError, OSError, Exception) as e:
        logger.info(f"Зображення недоступне, відправляю тільки текст: {e}")
        # Fallback - відправляємо тільки текст
        keyboard = [
            [InlineKeyboardButton("Підписався (лась)", callback_data="subscribe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Вітаємо! Тут бренди шукають креаторів для співпраці.\nПідписуйтесь!\n{CHANNEL_LINK}",
            reply_markup=reply_markup
        )
        return
    
    # Відправляємо текст з кнопкою після зображення
    keyboard = [
        [InlineKeyboardButton("Підписався (лась)", callback_data="subscribe")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Підписуйтесь на наш канал!\n{CHANNEL_LINK}",
        reply_markup=reply_markup
    )

# Функція для запланування повторної відправки
async def schedule_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Чекаємо 10 секунд
    await asyncio.sleep(10)
    
    try:
        # Відправляємо напоминаюче повідомлення
        await update.message.reply_text(
            f"Мабуть хтось заснув, будь-ласка підпишіться на телеграм канал\n{CHANNEL_LINK}"
        )
    except Exception as e:
        logger.error(f"Помилка відправки напоминаючого повідомлення: {e}")

# Обробник колбека для кнопки підписки та регіонів
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "subscribe":
        chat_id = CHANNEL_ID  # Використовуємо змінну CHANNEL_ID
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            logger.info(f"Статус користувача {user_id} у каналі {chat_id}: {member.status}")
            if member.status in ['member', 'administrator', 'creator']:
                update_subscription_status(user_id, True)
                keyboard = [
                    [
                        InlineKeyboardButton("Київ", url="https://t.me/+MAtbwy9ufGAwMzli"),
                        InlineKeyboardButton("Дніпро", url="https://t.me/+YvX-FzQHpU1kNGZi"),
                        InlineKeyboardButton("Харків", url="https://t.me/+kanHOVAz99FlODYy")
                    ],
                    [
                        InlineKeyboardButton("Одеса", url="https://t.me/+FyKju8C82b43OGEy"),
                        InlineKeyboardButton("Львів", url="https://t.me/+rbesn-FqWKkxMDFi")
                    ],
                    [
                        InlineKeyboardButton("Інші регіони", callback_data="other_regions")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    "Дякуємо за підписку!\n\n"
                    "Тепер ви можете знаходити замовлення та створювати оголошення у вашому регіоні.\n\n"
                    "Оберіть свій регіон:",
                    reply_markup=reply_markup
                )
            else:
                await query.message.reply_text(
                    "Ви не підписані на канал.\n\n"
                    "Будь ласка, підпишіться, щоб продовжити!\n\n"
                    f"Приєднуйтесь до нашого каналу: {CHANNEL_LINK}"
                )
        except TelegramError as e:
            if "not enough rights" in str(e).lower() or "unauthorized" in str(e).lower():
                logger.error(f"Бот не має прав для перевірки підписки в каналі {chat_id} для користувача {user_id}: {str(e)}")
                await query.message.reply_text(
                    "Помилка: бот не має доступу до каналу. Зверніться до адміністратора."
                )
            else:
                logger.error(f"Помилка при перевірці підписки для користувача {user_id}: {str(e)}")
                await query.message.reply_text(
                    "Помилка перевірки підписки.\n\n"
                    "Спробуйте ще раз або зверніться до адміністратора."
                )
        except Exception as e:
            logger.error(f"Невідома помилка при перевірці підписки для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                "Помилка перевірки підписки.\n\n"
                "Спробуйте ще раз або зверніться до адміністратора."
            )
    
    elif query.data == "other_regions":
        try:
            logger.info(f"Обробка кнопки 'Інші регіони' для користувача {user_id}")
            region_urls = {
                "Запоріжжя": "https://t.me/+XE-XiYnCSOwwYzAy",
                "Вінниця": "https://t.me/+TsEar0CH3z0wYzQy",
                "Полтава": "https://t.me/+cQcCFMOlQ6dkMWQy",
                "Чернігів": "https://t.me/+KPOzzkb_B4RhNjU6",
                "Черкаси": "https://t.me/+6d_cW6rKyrU0MDE6",
                "Хмельницький": "https://t.me/+2ZktT_xJXd81NTJi",
                "Житомир": "https://t.me/+-X78W7iXLkMzZTgy",
                "Суми": "https://t.me/+f0P0ATKrmB5lYTli",
                "Рівне": "https://t.me/+FaswQkcAfw5jNTli",
                "Івано-Франківськ": "https://t.me/+hqOtVtNY41tkYjMy",
                "Тернопіль": "https://t.me/+k2UwXPJrBg9mZjky",
                "Ужгород": "https://t.me/+ZGu30lrloOM1ZWMy",
                "Луцьк": "https://t.me/+wSOX_aMM9oJkZTdi",
                "Чернівці": "https://t.me/+zU3actkWQlwwZjI6",
                "Миколаїв": "https://t.me/+vyd6xO6jZ9o2NWI6",
                "Херсон": "https://t.me/+pNd7r-LabUY5Yzky",
                "Кропивницький": "https://t.me/+CAClUadjBbxhZDI6"
            }
            
            keyboard = []
            region_list = list(region_urls.items())
            
            # Розбиваємо на рядки по 2 кнопки для кращого відображення
            for i in range(0, len(region_list), 2):
                row = []
                for j in range(2):
                    if i + j < len(region_list):
                        region_name, region_url = region_list[i + j]
                        row.append(InlineKeyboardButton(region_name, url=region_url))
                keyboard.append(row)
            
            # Додаємо кнопку "Назад"
            keyboard.append([InlineKeyboardButton("« Назад до основних міст", callback_data="main_cities")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Оберіть ваш регіон:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Помилка при обробці 'Інші регіони' для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                f"Помилка при завантаженні регіонів: {str(e)}\n\n"
                "Спробуйте ще раз або зверніться до адміністратора."
            )
    
    elif query.data == "main_cities":
        try:
            keyboard = [
                [
                    InlineKeyboardButton("Київ", url="https://t.me/+MAtbwy9ufGAwMzli"),
                    InlineKeyboardButton("Дніпро", url="https://t.me/+YvX-FzQHpU1kNGZi"),
                    InlineKeyboardButton("Харків", url="https://t.me/+kanHOVAz99FlODYy")
                ],
                [
                    InlineKeyboardButton("Одеса", url="https://t.me/+FyKju8C82b43OGEy"),
                    InlineKeyboardButton("Львів", url="https://t.me/+rbesn-FqWKkxMDFi")
                ],
                [
                    InlineKeyboardButton("Інші регіони", callback_data="other_regions")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Дякуємо за підписку!\n\n"
                "Тепер ви можете знаходити замовлення та створювати оголошення у вашому регіоні.\n\n"
                "Оберіть свій регіон:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Помилка при поверненні до основних міст для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                "Помилка при завантаженні меню. Спробуйте ще раз або зверніться до адміністратора."
            )

# Обробник команди /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    admin_id = 293102975
    if user_id != admin_id:
        await update.message.reply_text("Ця команда доступна лише адміністратору!")
        return
    
    conn = None
    try:
        # Отримуємо параметри підключення з змінних середовища
        if DATABASE_URL:
            # Використовуємо DATABASE_URL
            conn = psycopg2.connect(DATABASE_URL)
        else:
            # Використовуємо окремі параметри
            conn = psycopg2.connect(
                dbname=os.getenv("PGDATABASE"),
                user=os.getenv("PGUSER"),
                password=os.getenv("PGPASSWORD"),
                host=os.getenv("PGHOST"),
                port=os.getenv("PGPORT")
            )
        
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = TRUE AND is_blocked = FALSE")
        subscribed_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE is_blocked = TRUE")
        blocked_users = cur.fetchone()[0]
        
        await update.message.reply_text(
            f"Статистика користувачів:\n\n"
            f"Загальна кількість: {total_users}\n"
            f"Підписані на канал: {subscribed_users}\n"
            f"Заблоковані: {blocked_users}"
        )
    except Exception as e:
        logger.error(f"Помилка при отриманні статистики: {e}")
        await update.message.reply_text(f"Помилка: {e}")
    finally:
        if conn:
            conn.close()

# Обробник сигналів для коректного завершення
def signal_handler(sig, frame):
    logger.info("Отримано сигнал завершення, вимикаю бота...")
    os._exit(0)

# Ініціалізація та запуск бота
if __name__ == "__main__":
    # Перевіряємо наявність токена
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не знайдено в змінних середовища!")
        exit(1)
    
    # Налаштування обробки сигналів
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ініціалізація бази даних
    init_db()

    # Створення додатку з правильними таймаутами
    application = (Application.builder()
                  .token(TOKEN)
                  .get_updates_read_timeout(30)
                  .get_updates_write_timeout(30)
                  .get_updates_connect_timeout(30)
                  .get_updates_pool_timeout(30)
                  .build())

    # Додавання обробників команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    # Запуск бота з повторною спробою при конфлікті
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Запуск бота, спроба {attempt + 1}/{max_retries}")
            
            # Видаляємо webhook перед запуском (якщо не перша спроба)
            if attempt > 0:
                logger.info("Чекаю перед повторною спробою...")
                time.sleep(10 + attempt * 5)
            
            # Запускаємо бот
            application.run_polling(drop_pending_updates=True)
            break
            
        except Conflict as e:
            logger.error(f"Конфлікт із іншою інстанцією бота на спробі {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.error(f"Чекаю {15 + attempt * 10} секунд перед повторною спробою...")
                time.sleep(15 + attempt * 10)
        except Exception as e:
            logger.error(f"Помилка запуску бота на спробі {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                break
    else:
        logger.error("Не вдалося запустити бота після всіх спроб.")
        exit(1)
