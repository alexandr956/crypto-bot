import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import os

# ========== ТОКЕН ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
# ===========================

# Минимальный веб-сервер для Render
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ========== ТЕЛЕГРАМ-БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 ТЕСТ", callback_data="test")]
    ])
    await message.answer("🏦 Добро пожаловать! Нажми кнопку:", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "test")
async def test_callback(call: types.CallbackQuery):
    await call.message.edit_text("✅ Кнопка работает!")
    await call.answer()

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()  # Запускаем веб-сервер в фоне
    asyncio.run(main())
