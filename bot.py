import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# Токен будет браться из переменных Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

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
    asyncio.run(main())