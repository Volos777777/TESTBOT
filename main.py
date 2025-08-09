import os
import signal
import logging
import time
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError, Conflict
from broadcast import broadcast
from database import init_db, load_users, save_user, update_subscription_status, update_blocked_status

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Змінні середовища
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "-1002834216129"  # ID нового каналу
CHANNEL_LINK = "https://t.me/+ZzEgiQVCP6s2Y2Ji"  # Посилання на новий канал
DATABASE_URL = os.getenv("DATABASE_URL")

# Функція для створення клавіатури регіонів
def create_region_keyboard():
    return InlineKeyboardMarkup([
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
    ])

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
    # Перевіряємо статус підписки
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user.id)
        if member.status in ['member', 'administrator', 'creator']:
            update_subscription_status(user.id, True)
            await update.message.reply_text(
                "Дякуємо за підписку!\n\n"
                "Тепер ви можете знаходити замовлення та створювати оголошення у вашому регіоні.\n\n"
                "Оберіть свій регіон:",
                reply_markup=create_region_keyboard()
            )
            return
    except TelegramError as e:
        logger.error(f"Помилка при перевірці підписки для користувача {user.id}: {str(e)}")
    
    # Якщо не підписаний, пропонуємо підписку та запускаємо нагадування
    keyboard = [[InlineKeyboardButton("Підписався (лась)", callback_data="subscribe")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Привіт, {user.first_name}!\n\n"
        f"Ласкаво просимо до бота @zaletilo_bot!\n\n"
        f"Приєднуйтесь до нашого каналу: {CHANNEL_LINK}",
        reply_markup=reply_markup
    )
    # Запускаємо нагадування через 3 хвилини (180 секунд)
    context.job_queue.run_once(remind_to_subscribe, 180, data={'chat_id': update.message.chat_id, 'user_id': user.id}, name=str(user.id))

# Функція нагадування про підписку
async def remind_to_subscribe(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data['chat_id']
    user_id = context.job.data['user_id']
    
    # Перевіряємо, чи користувач підписався
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return  # Користувач підписався, нагадування не потрібне
    except TelegramError as e:
        logger.error(f"Помилка при перевірці підписки в нагадуванні для користувача {user_id}: {str(e)}")
        return

    # Надсилаємо нагадування
    keyboard = [[InlineKeyboardButton("Підписатися", url=CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=chat_id,
        text="Схоже, хтось заснув і не підписався на канал 😴, поспіши підписатись на канал, щоб отримувати замовлення!",
        reply_markup=reply_markup
    )
    logger.info(f"Нагадування надіслано користувачу {user_id}")

# Обробник колбека для кнопки підписки та регіонів
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "subscribe":
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            logger.info(f"Статус користувача {user_id} у каналі {CHANNEL_ID}: {member.status}")
            if member.status in ['member', 'administrator', 'creator']:
                update_subscription_status(user_id, True)
                await query.message.reply_text(
                    "Дякуємо за підписку!\n\n"
                    "Тепер ви можете знаходити замовлення та створювати оголошення у вашому регіоні.\n\n"
                    "Оберіть свій регіон:",
                    reply_markup=create_region_keyboard()
                )
            else:
                keyboard = [[InlineKeyboardButton "Підписатися", url=CHANNEL_LINK)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    "Ви не підписані на канал.\n\n"
                    "Будь ласка, підпишіться, щоб продовжити!\n\n"
                    f"Приєднуйтесь до нашого каналу: {CHANNEL_LINK}",
                    reply_markup=reply_markup
                )
        except TelegramError as e:
            if "not enough rights" in str(e).lower() or "unauthorized" in str(e).lower():
                logger.error(f"Бот не має прав для перевірки підписки в каналі {CHANNEL_ID} для користувача {user_id}: {str(e)}")
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
            }
            keyboard = [[InlineKeyboardButton(city, url=url) for city, url in region_urls.items()]]
            keyboard.append([InlineKeyboardButton("Назад до основних міст", callback_data="main_cities")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Оберіть ваш регіон:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Помилка при обробці 'Інші регіони' для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                "Помилка при завантаженні регіонів. Спробуйте ще раз або зверніться до адміністратора."
            )
    
    elif query.data == "main_cities":
        try:
            await query.edit_message_text(
                "Дякуємо за підписку!\n\n"
                "Тепер ви можете знаходити замовлення та створювати оголошення у вашому регіоні.\n\n"
                "Оберіть свій регіон:",
                reply_markup=create_region_keyboard()
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
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
        else:
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
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не знайдено в змінних середовища!")
        exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    init_db()

    application = (Application.builder()
                  .token(TOKEN)
                  .get_updates_read_timeout(30)
                  .get_updates_write_timeout(30)
                  .get_updates_connect_timeout(30)
                  .get_updates_pool_timeout(30)
                  .build())

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_callback))

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Запуск бота, спроба {attempt + 1}/{max_retries}")
            if attempt > 0:
                logger.info("Чекаю перед повторною спробою...")
                time.sleep(10 + attempt * 5)
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
