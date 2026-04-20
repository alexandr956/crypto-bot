import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Курсы", callback_data="rates")],
        [InlineKeyboardButton(text="🔴 ТЕСТ", callback_data="test")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    photo_url = "https://raw.githubusercontent.com/alexandr956/crypto-bot/main/welcome.jpg"
    try:
        await message.answer_photo(photo_url, caption="🏦 *Добро пожаловать в КриптоОбменник!*", parse_mode="Markdown", reply_markup=main_menu())
    except:
        await message.answer("🏦 *Добро пожаловать в КриптоОбменник!*", parse_mode="Markdown", reply_markup=main_menu())

@dp.callback_query(lambda c: c.data == "test")
async def test_callback(call: types.CallbackQuery):
    await call.message.answer("✅ Кнопка работает!", reply_markup=main_menu())
    await call.answer()

@dp.callback_query(lambda c: c.data == "rates")
async def rates_callback(call: types.CallbackQuery):
    text = (
        "📊 *Актуальные курсы:*\n\n"
        "└ *USDT:* 82,81 ₽\n"
        "└ *BTC:* 5 725 873 ₽\n"
        "└ *ETH:* 174 639 ₽\n\n"
        "📞 *Точный курс уточняйте у оператора*"
    )
    await call.message.answer(text, parse_mode="Markdown", reply_markup=main_menu())
    await call.answer()

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
