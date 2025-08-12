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
from database import init_db, load_users, save_user, update_subscription_status, update_blocked_status, save_contact, log_message  # Імпорт з database.py

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
    log_message(user.id, 'in', 'command', '/start', extra={'username': user.username})
    
    # Створюємо клавіатуру для запиту контактів
    keyboard = [[KeyboardButton("Поділитися контактом", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Вітаємо {user.first_name}! Для продовження роботи потрібно поділитися вашим контактом.",
        reply_markup=reply_markup
    )
    log_message(user.id, 'out', 'text', 'Запит контакту на старті')

# Перевірка підписки користувача
async def is_user_subscribed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramError as e:
        logger.error(f"Не вдалося перевірити підписку для {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Невідома помилка перевірки підписки для {user_id}: {e}")
        return False

# Відправка інвайту до каналу з посиланням і зображенням (якщо є)
async def send_channel_invite_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    image_path = "images/bot_image.png"  # Замініть файлом, який ви надішлете
    caption = (
        "Приєднуйтесь до нашого каналу, щоб отримувати замовлення та оновлення."
    )
    keyboard = [
        [InlineKeyboardButton("Відкрити канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton("Я підписався", callback_data="subscribe")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if os.path.exists(image_path) and os.path.getsize(image_path) > 1000:
            with open(image_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"{caption}\n{CHANNEL_LINK}", reply_markup=reply_markup)
        # Лог вихідного повідомлення
        log_message(chat_id, 'out', 'invite', caption, extra={'with_buttons': True})
    except Exception as e:
        logger.error(f"Помилка відправки інвайту в канал: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"{caption}\n{CHANNEL_LINK}", reply_markup=reply_markup)
        log_message(chat_id, 'out', 'invite', caption, extra={'fallback': True, 'with_buttons': True})

# Відправка меню регіональних каналів
async def send_region_menu(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    keyboard = [
        [
            InlineKeyboardButton("Київ", url="https://t.me/+MAtbwy9ufGAwMzli"),
            InlineKeyboardButton("Дніпро", url="https://t.me/+YvX-FzQHpU1kNGZi"),
            InlineKeyboardButton("Харків", url="https://t.me/+kanHOVAz99FlODYy"),
        ],
        [
            InlineKeyboardButton("Одеса", url="https://t.me/+FyKju8C82b43OGEy"),
            InlineKeyboardButton("Львів", url="https://t.me/+rbesn-FqWKkxMDFi"),
        ],
        [InlineKeyboardButton("Інші регіони", callback_data="other_regions")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "Тепер ви можете знаходити замовлення та створювати оголошення у вашому регіоні.\n\n"
        "Оберіть свій регіон:"
    )
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    log_message(chat_id, 'out', 'text', text)

# Фолов-ап після надання контакту: чек підписки через 60с, нагадування (якщо треба), потім меню регіонів
async def post_contact_followup(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    await asyncio.sleep(60)
    subscribed = await is_user_subscribed(context, user_id)
    if not subscribed:
        try:
            text = "Мабуть хтось заснув, будь-ласка підпишіться на телеграм канал"
            keyboard = [
                [InlineKeyboardButton("Відкрити канал", url=CHANNEL_LINK)],
                [InlineKeyboardButton("Я підписався", callback_data="subscribe")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            log_message(user_id, 'out', 'reminder', text)
        except Exception as e:
            logger.error(f"Не вдалося надіслати нагадування: {e}")
    # Після цього надсилаємо меню регіонів незалежно від підписки
    await send_region_menu(context, chat_id)

# Обробник отримання контактів
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    contact = update.message.contact
    chat_id = update.effective_chat.id
    
    if contact:
        # Зберігаємо контакт в базу даних
        save_contact(
            user_id=user.id,
            phone_number=contact.phone_number,
            first_name=contact.first_name,
            last_name=contact.last_name,
        )
        log_message(user.id, 'in', 'contact', contact.phone_number, extra={'first_name': contact.first_name, 'last_name': contact.last_name})
        
        # Прибираємо клавіатуру
        await update.message.reply_text(
            "Дякуємо!",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True),
        )
        log_message(user.id, 'out', 'text', 'Підтвердження отримання контакту')
        
        # 1) Інвайт у канал з посиланням і (за наявності) зображенням
        await send_channel_invite_message(context, chat_id)
        
        # 2) Через 60с: якщо не підписався — нагадаємо; далі відправимо меню регіонів
        asyncio.create_task(post_contact_followup(context, user.id, chat_id))
    else:
        await update.message.reply_text("Будь ласка, поділіться вашим контактом для продовження роботи.")
        log_message(user.id, 'out', 'text', 'Запит повторити надсилання контакту')

# Обробник колбека для кнопки підписки та регіонів
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    log_message(user_id, 'in', 'callback', query.data)
    
    if query.data == "subscribe":
        chat_id = CHANNEL_ID  # Використовуємо змінну CHANNEL_ID
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            logger.info(f"Статус користувача {user_id} у каналі {chat_id}: {member.status}")
            if member.status in ['member', 'administrator', 'creator']:
                update_subscription_status(user_id, True)
                # Після підтвердження підписки показуємо меню регіонів
                await send_region_menu(context, query.message.chat_id)
            else:
                text = (
                    "Ви не підписані на канал.\n\n"
                    "Будь ласка, підпишіться, щоб продовжити!\n\n"
                    f"Приєднуйтесь до нашого каналу: {CHANNEL_LINK}"
                )
                await query.message.reply_text(text)
                log_message(user_id, 'out', 'text', text)
        except TelegramError as e:
            if "not enough rights" in str(e).lower() or "unauthorized" in str(e).lower():
                logger.error(f"Бот не має прав для перевірки підписки в каналі {chat_id} для користувача {user_id}: {str(e)}")
                await query.message.reply_text(
                    "Помилка: бот не має доступу до каналу. Зверніться до адміністратора."
                )
                log_message(user_id, 'out', 'text', 'Помилка доступу до каналу при перевірці підписки')
            else:
                logger.error(f"Помилка при перевірці підписки для користувача {user_id}: {str(e)}")
                await query.message.reply_text(
                    "Помилка перевірки підписки.\n\n"
                    "Спробуйте ще раз або зверніться до адміністратора."
                )
                log_message(user_id, 'out', 'text', 'Помилка перевірки підписки')
        except Exception as e:
            logger.error(f"Невідома помилка при перевірці підписки для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                "Помилка перевірки підписки.\n\n"
                "Спробуйте ще раз або зверніться до адміністратора."
            )
            log_message(user_id, 'out', 'text', 'Невідома помилка перевірки підписки')
    
    elif query.data == "other_regions":
        try:
            await send_region_menu(context, query.message.chat_id)
        except Exception as e:
            logger.error(f"Помилка при обробці 'Інші регіони' для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                f"Помилка при завантаженні регіонів: {str(e)}\n\n"
                "Спробуйте ще раз або зверніться до адміністратора."
            )
            log_message(user_id, 'out', 'text', 'Помилка при завантаженні регіонів')
    
    elif query.data == "main_cities":
        try:
            await send_region_menu(context, query.message.chat_id)
        except Exception as e:
            logger.error(f"Помилка при поверненні до основних міст для користувача {user_id}: {str(e)}")
            await query.message.reply_text(
                "Помилка при завантаженні меню. Спробуйте ще раз або зверніться до адміністратора."
            )
            log_message(user_id, 'out', 'text', 'Помилка при завантаженні меню регіонів')

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
