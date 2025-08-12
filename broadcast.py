from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio
import logging
from telegram.error import TelegramError, Forbidden, BadRequest
from database import load_users, update_blocked_status

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
            "Використання:\n"
            "1. Простий текст: /broadcast <текст> [all]\n"
            "2. З картинкою: /broadcast <текст> <URL_картинки> <текст_кнопки> <URL_посилання> [all]\n\n"
            "Приклади:\n"
            "• /broadcast Привіт, це тест!\n"
            "• /broadcast Привіт, це тест! all\n"
            "• /broadcast Підписуйтесь на @mychannel all\n"
            "• /broadcast Переходьте на https://t.me/mychannel all\n"
            "• /broadcast Привіт https://picsum.photos/200/300 Перейти https://example.com\n"
            "• /broadcast Привіт https://picsum.photos/200/300 Перейти https://example.com all\n\n"
            "Додайте 'all' для надсилання всім користувачам (не лише підписаним)"
        )
        return

    try:
        # Отримуємо повний текст повідомлення після команди
        message_text = update.message.text
        command_parts = message_text.split(' ', 1)  # Розділяємо на команду та решту
        
        if len(command_parts) < 2:
            await update.message.reply_text("Помилка: не вказано текст для розсилки!")
            return
            
        full_text = command_parts[1]  # Весь текст після /broadcast
        
        # Розумна перевірка на "all" в кінці
        # Розбиваємо текст на слова
        words = full_text.split()
        send_to_all = False
        
        if len(words) > 0 and words[-1].lower() == 'all':
            # Перевіряємо, чи "all" не є частиною URL або @username
            if len(words) == 1:
                # Якщо тільки "all" - це команда
                send_to_all = True
                full_text = ""
            else:
                prev_word = words[-2] if len(words) >= 2 else ""
                # Якщо попереднє слово не закінчується на URL-подібні символи
                if not (prev_word.endswith('.me') or 
                       prev_word.startswith('@') or
                       prev_word.startswith('http') or
                       ('/' in prev_word and ('t.me' in prev_word or 'telegram' in prev_word))):
                    send_to_all = True
                    # Видаляємо останнє слово "all"
                    full_text = ' '.join(words[:-1])
        
        if send_to_all:
            logger.info("Розсилка буде надіслана ВСІМ користувачам")
        else:
            logger.info("Розсилка буде надіслана лише ПІДПИСАНИМ користувачам")

        # Тепер розбираємо аргументи з очищеного тексту
        args = full_text.split() if full_text.strip() else []
        
        if not args and not send_to_all:
            await update.message.reply_text("Помилка: не вказано текст для розсилки!")
            return
        elif not args and send_to_all:
            await update.message.reply_text("Помилка: не вказано текст для розсилки! (знайдено тільки 'all')")
            return

        # Завантажуємо список користувачів
        users = load_users(subscribed_only=not send_to_all)
        if not users:
            status_text = "всіх" if send_to_all else "підписаних"
            await update.message.reply_text(f"Список користувачів порожній або немає {status_text} користувачів!")
            return

        status_message = await update.message.reply_text(f"🚀 Розпочинаю розсилку для {len(users)} користувачів...")

        # Лічильники
        sent_count = 0
        blocked_count = 0
        error_count = 0

        # Перевіряємо тип розсилки
        if len(args) == 4:
            # Повна розсилка з картинкою та кнопкою
            text, image_url, button_text, button_url = args
            logger.info(f"Розпочинаємо повну розсилку з картинкою для {len(users)} користувачів")

            # Створюємо інлайн-кнопку з URL
            keyboard = [[InlineKeyboardButton(button_text, url=button_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            for i, user_id in enumerate(users):
                try:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=image_url,
                        caption=text,
                        reply_markup=reply_markup
                    )
                    sent_count += 1
                    logger.info(f"Повідомлення з картинкою надіслано користувачу {user_id}")
                    
                    # Оновлюємо статус кожні 50 повідомлень
                    if (i + 1) % 50 == 0:
                        await status_message.edit_text(
                            f"📤 Надіслано: {sent_count}/{len(users)}\n"
                            f"❌ Заблоковано: {blocked_count}\n"
                            f"⚠️ Помилок: {error_count}"
                        )
                    
                    # Затримка для запобігання rate limit
                    await asyncio.sleep(0.1)
                    
                except Forbidden:
                    blocked_count += 1
                    logger.warning(f"Користувач {user_id} заблокував бота")
                    update_blocked_status(user_id, True)
                except BadRequest as e:
                    if "chat not found" in str(e).lower():
                        blocked_count += 1
                        logger.warning(f"Чат з користувачем {user_id} не знайдено")
                        update_blocked_status(user_id, True)
                    else:
                        error_count += 1
                        logger.error(f"BadRequest для користувача {user_id}: {e}")
                except TelegramError as e:
                    error_count += 1
                    logger.error(f"TelegramError для користувача {user_id}: {e}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Невідома помилка для користувача {user_id}: {e}")
        else:
            # Простий текст
            if len(args) > 1 and len(args) != 4:
                text = full_text  # Використовуємо повний текст для складних повідомлень
            else:
                text = args[0] if args else full_text
            
            logger.info(f"Розпочинаємо розсилку тексту: '{text[:50]}...' для {len(users)} користувачів")
            
            for i, user_id in enumerate(users):
                try:
                    await context.bot.send_message(chat_id=user_id, text=text)
                    sent_count += 1
                    logger.info(f"Текст надіслано користувачу {user_id}")
                    
                    # Оновлюємо статус кожні 50 повідомлень
                    if (i + 1) % 50 == 0:
                        await status_message.edit_text(
                            f"📤 Надіслано: {sent_count}/{len(users)}\n"
                            f"❌ Заблоковано: {blocked_count}\n"
                            f"⚠️ Помилок: {error_count}"
                        )
                    
                    # Затримка для запобігання rate limit
                    await asyncio.sleep(0.1)
                    
                except Forbidden:
                    blocked_count += 1
                    logger.warning(f"Користувач {user_id} заблокував бота")
                    update_blocked_status(user_id, True)
                except BadRequest as e:
                    if "chat not found" in str(e).lower():
                        blocked_count += 1
                        logger.warning(f"Чат з користувачем {user_id} не знайдено")
                        update_blocked_status(user_id, True)
                    else:
                        error_count += 1
                        logger.error(f"BadRequest для користувача {user_id}: {e}")
                except TelegramError as e:
                    error_count += 1
                    logger.error(f"TelegramError для користувача {user_id}: {e}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Невідома помилка для користувача {user_id}: {e}")

        # Фінальний звіт
        final_message = (
            f"✅ Розсилка завершена!\n\n"
            f"👥 Всього користувачів: {len(users)}\n"
            f"📤 Успішно надіслано: {sent_count}\n"
            f"❌ Заблоковано боту: {blocked_count}\n"
            f"⚠️ Помилок: {error_count}\n\n"
            f"📊 Успішність: {(sent_count/len(users)*100):.1f}%" if users else "📊 Успішність: 0%"
        )
        
        await status_message.edit_text(final_message)
        logger.info(f"Розсилка завершена. Надіслано: {sent_count}, Заблоковано: {blocked_count}, Помилок: {error_count}")
        
    except Exception as e:
        logger.error(f"Критична помилка при розсилці: {e}")
        await update.message.reply_text(f"❌ Критична помилка: {e}")
