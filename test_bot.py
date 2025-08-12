#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки функцій бота
"""

import os
import sys

def test_imports():
    """Тестуємо імпорти"""
    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
        print("✅ Telegram бібліотеки імпортовано успішно")
    except ImportError as e:
        print(f"❌ Помилка імпорту Telegram бібліотек: {e}")
        return False
    
    try:
        import psycopg2
        print("✅ psycopg2 імпортовано успішно")
    except ImportError as e:
        print(f"❌ Помилка імпорту psycopg2: {e}")
        return False
    
    try:
        from database import init_db, save_user, save_contact
        print("✅ Функції бази даних імпортовано успішно")
    except ImportError as e:
        print(f"❌ Помилка імпорту функцій БД: {e}")
        return False
    
    return True

def test_environment():
    """Тестуємо змінні середовища"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        print("✅ TELEGRAM_BOT_TOKEN знайдено")
    else:
        print("⚠️ TELEGRAM_BOT_TOKEN не знайдено")
    
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print("✅ DATABASE_URL знайдено")
    else:
        print("⚠️ DATABASE_URL не знайдено")
    
    return bool(token and db_url)

def test_files():
    """Тестуємо наявність файлів"""
    required_files = [
        "main.py",
        "database.py", 
        "broadcast.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} знайдено")
        else:
            print(f"❌ {file} не знайдено")
            missing_files.append(file)
    
    return len(missing_files) == 0

def main():
    print("🧪 Тестування бота...\n")
    
    tests = [
        ("Перевірка імпортів", test_imports),
        ("Перевірка змінних середовища", test_environment),
        ("Перевірка файлів", test_files)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"🔍 {test_name}:")
        try:
            result = test_func()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Помилка тесту: {e}\n")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    
    print(f"📊 Результати: {passed}/{total} тестів пройдено")
    
    if passed == total:
        print("🎉 Всі тести пройдено! Бот готовий до роботи.")
    else:
        print("⚠️ Деякі тести не пройдено. Перевірте налаштування.")
    
    return passed == total

if __name__ == "__main__":
    main() 