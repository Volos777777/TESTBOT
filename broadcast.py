from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from telegram.error import TelegramError
from database import load_users, update_blocked_status  # Оновлений імпорт

# Налаштування логування
logger = logging.getLogger(__name__)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /broadcast: розсилає повідомлення з текстом, картинкою, кнопкою або просто текстом."""
    user_id = update.message.from_user.id
    # Ваш Telegram ID для доступу до команди /broadcast
    admin_id = 293102975
    
    # Перевіряємо, чи користувач є адміністратором
    if user_id != admin_id:
        await update.message.reply_text("Ця команда доступна лише адміністратору!")
        return

    # Перевіряємо аргументи
    if not context.args:
        await update.message.reply_text(
            "Використання: /broadcast <текст> [URL_картинки] [текст_кнопки] [URL_посилання] [all]\n"
            "Приклад простого тексту: /broadcast Привіт, це тест!\n"
            "Приклад із картинкою та кнопкою: /broadcast Привіт https://picsum.photos/200/300 Перейти https://example.com\n"
            "Додайте 'all' в кінці, щоб надіслати всім користувачам (не лише підписаним)"
        )
        return

    try:
        # Отримуємо аргументи
        args = context.args
        send_to_all = args[-1].lower() == 'all' if args else False
        if send_to_all:
            args = args[:-1]  # Виключаємо 'all' із основних аргументів

        # Якщо лише один аргумент — це текст
        if len(args) == 1:
            text = args[0]
            users = load_users(subscribed_only=not send_to_all)
            if not users:
                await update.message.reply_text(f"Список користувачів порожній або немає {'підписаних' if not send_to_all else 'доступних'} користувачів!")
                return
            logger.info(f"Розпочинаємо розсилку тексту для {len(users)} користувачів")
            for user_id in users:
                try:
                    await context.bot.send_message(chat_id=user_id, text=text)
                    logger.info(f"Текст надіслано користувачу {user_id}")
                except TelegramError as e:
                    logger.error(f"Помилка при надсиланні користувачу {user_id}: {e}")
                    update_blocked_status(user_id, True)
            await update.message.reply_text(f"Розсилка тексту завершена для {len(users)} користувачів!")
            return

        # Якщо більше аргументів — повна розсилка з картинкою та кнопкою
        if len(args) < 4:
            await update.message.reply_text(
                "Для повної розсилки вкажіть: /broadcast <текст> <URL_картинки> <текст_кнопки> <URL_посилання> [all]"
            )
            return

        text = args[0]
        image_url = args[1]
        button_text = args[2]
        button_url = args[3]

        # Створюємо інлайн-кнопку з URL
        keyboard = [[InlineKeyboardButton(button_text, url=button_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Завантажуємо список користувачів
        users = load_users(subscribed_only=not send_to_all)
        if not users:
            await update.message.reply_text(f"Список користувачів порожній або немає {'підписаних' if not send_to_all else 'доступних'} користувачів!")
            return
        
        logger.info(f"Розпочинаємо розсилку для {len(users)} користувачів")
        # Надсилаємо повідомлення кожному користувачу
        for user_id in users:
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=image_url,
                    caption=text,
                    reply_markup=reply_markup
                )
                logger.info(f"Повідомлення надіслано користувачу {user_id}")
            except TelegramError as e:
                logger.error(f"Помилка при надсиланні користувачу {user_id}: {e}")
                update_blocked_status(user_id, True)
        
        await update.message.reply_text(f"Розсилка завершена для {len(users)} користувачів!")
    except Exception as e:
        logger.error(f"Помилка при розсилці: {e}")
        await update.message.reply_text(f"Помилка: {e}")
