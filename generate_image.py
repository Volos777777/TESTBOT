#!/usr/bin/env python3
"""
Скрипт для генерації зображення бота за допомогою PIL
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    print("PIL імпортовано успішно")
except ImportError:
    print("PIL не встановлено. Встановлюю...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFont

def generate_bot_image():
    try:
        # Створюємо зображення
        width, height = 800, 600
        image = Image.new('RGB', (width, height), color='#ffffff')
        draw = ImageDraw.Draw(image)
        
        # Додаємо градієнтний фон
        for y in range(height):
            r = int(255 - (y / height) * 20)
            g = int(255 - (y / height) * 15)
            b = int(255 + (y / height) * 10)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Додаємо синій акцент
        draw.ellipse([50, 50, 150, 150], fill='#4a90e2', outline=None)
        
        # Додаємо логотип (простий чорний круг з білими точками)
        logo_x, logo_y = 400, 100
        draw.ellipse([logo_x-30, logo_y-30, logo_x+30, logo_y+30], fill='#000000', outline=None)
        draw.ellipse([logo_x-15, logo_y-15, logo_x-5, logo_y-5], fill='#ffffff', outline=None)
        draw.ellipse([logo_x+5, logo_y+15, logo_x+15, logo_y+25], fill='#ffffff', outline=None)
        
        # Додаємо текст "залетіло"
        try:
            font_large = ImageFont.truetype("arial.ttf", 36)
        except:
            font_large = ImageFont.load_default()
        
        draw.text((logo_x+40, logo_y-15), "залетіло", fill='#000000', font=font_large)
        
        # Додаємо заголовок
        try:
            font_title = ImageFont.truetype("arial.ttf", 48)
        except:
            font_title = ImageFont.load_default()
        
        title = "у нас знаходять\nкріейторів"
        draw.text((400, 200), title, fill='#000000', font=font_title, anchor="mm")
        
        # Додаємо чат-бульбашки
        # Перша бульбашка
        bubble1_x, bubble1_y = 150, 350
        draw.rounded_rectangle([bubble1_x, bubble1_y, bubble1_x+250, bubble1_y+80], 
                              radius=20, fill='#ffffff', outline='#e0e0e0', width=2)
        draw.ellipse([bubble1_x-15, bubble1_y+15, bubble1_x-5, bubble1_y+25], fill='#000000', outline=None)
        
        try:
            font_small = ImageFont.truetype("arial.ttf", 12)
        except:
            font_small = ImageFont.load_default()
        
        text1 = "Вітаю, шукаємо UGC кріейтора для огляд косметичної продукції власного виробництва. Бюджет до 1500 грн за огляд..."
        draw.text((bubble1_x+20, bubble1_y+20), text1, fill='#000000', font=font_small)
        
        # Друга бульбашка
        bubble2_x, bubble2_y = 450, 400
        draw.rounded_rectangle([bubble2_x, bubble2_y, bubble2_x+250, bubble2_y+80], 
                              radius=20, fill='#ffffff', outline='#e0e0e0', width=2)
        draw.ellipse([bubble2_x-15, bubble2_y+15, bubble2_x-5, bubble2_y+25], fill='#000000', outline=None)
        
        text2 = "Добрий день! Дуже терміново потрібна модель для зйомок в Києві, має мати чітку дикцію. Бажано щоб мала синю сукню"
        draw.text((bubble2_x+20, bubble2_y+20), text2, fill='#000000', font=font_small)
        
        # Зберігаємо зображення
        output_path = "images/bot_image.png"
        os.makedirs("images", exist_ok=True)
        image.save(output_path, "PNG")
        print(f"Зображення створено: {output_path}")
        
    except Exception as e:
        print(f"Помилка створення зображення: {e}")

if __name__ == "__main__":
    import os
    generate_bot_image() 