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

# Временное хранилище для выбора валюты
user_choice = {}

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Купить", callback_data="buy")],
        [InlineKeyboardButton(text="🔴 Продать", callback_data="sell")],
        [InlineKeyboardButton(text="📊 Курсы", callback_data="rates")],
        [InlineKeyboardButton(text="🔴 ТЕСТ", callback_data="test")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 USDT", callback_data="buy_USDT")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="buy_BTC")],
        [InlineKeyboardButton(text="💎 ETH", callback_data="buy_ETH")],
        [InlineKeyboardButton(text="💳 RapiraRUB", callback_data="buy_Rapira")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

def sell_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 USDT", callback_data="sell_USDT")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="sell_BTC")],
        [InlineKeyboardButton(text="💎 ETH", callback_data="sell_ETH")],
        [InlineKeyboardButton(text="💳 RapiraRUB", callback_data="sell_Rapira")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    photo_url = "https://raw.githubusercontent.com/alexandr956/crypto-bot/main/welcome.jpg"
    try:
        await message.answer_photo(photo_url, caption="🏦 *Добро пожаловать в КриптоОбменник!*", parse_mode="Markdown", reply_markup=main_menu())
    except:
        await message.answer("🏦 *Добро пожаловать в КриптоОбменник!*", parse_mode="Markdown", reply_markup=main_menu())

@dp.callback_query()
async def handle_callback(call: types.CallbackQuery):
    data = call.data
    
    # Назад в главное меню
    if data == "main":
        await call.message.edit_reply_markup(reply_markup=main_menu())
        await call.answer()
        return
    
    # Покупка
    if data == "buy":
        await call.message.edit_reply_markup(reply_markup=buy_menu())
        await call.answer()
        return
    
    # Продажа
    if data == "sell":
        await call.message.edit_reply_markup(reply_markup=sell_menu())
        await call.answer()
        return
    
    # Курсы
    if data == "rates":
        text = (
            "📊 *Рыночные курсы:*\n"
            "└ USDT: 82,81 ₽\n"
            "└ BTC: 5 725 873 ₽\n"
            "└ ETH: 174 639 ₽\n\n"
            "📈 *Покупка через MOSS PAY:*\n"
            "└ USDT: 91,81 ₽ (+10%)\n"
            "└ BTC: 6 298 873 ₽ (+10%)\n"
            "└ ETH: 192 102 ₽ (+10%)\n\n"
            "📉 *Продажа через MOSS PAY:*\n"
            "└ USDT: 81,15 ₽ (-2%)\n"
            "└ BTC: 5 611 355 ₽ (-2%)\n"
            "└ ETH: 171 146 ₽ (-2%)\n\n"
            "⚙️ *Наценка:* на покупку 10%, на продажу -2%"
        )
        await call.message.answer(text, parse_mode="Markdown", reply_markup=main_menu())
        await call.answer()
        return
    
    # Тест
    if data == "test":
        await call.message.answer("✅ Кнопка работает!", reply_markup=main_menu())
        await call.answer()
        return
    
    # Выбор валюты для покупки
    if data.startswith("buy_"):
        coin = data.split("_")[1]
        user_choice[call.from_user.id] = ("buy", coin)
        await call.message.answer(f"💰 *Введи сумму в рублях для покупки {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽", parse_mode="Markdown")
        await call.answer()
        return
    
    # Выбор валюты для продажи
    if data.startswith("sell_"):
        coin = data.split("_")[1]
        user_choice[call.from_user.id] = ("sell", coin)
        await call.message.answer(f"💰 *Введи сумму в рублях для продажи {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽", parse_mode="Markdown")
        await call.answer()
        return

@dp.message()
async def handle_amount(message: types.Message):
    uid = message.from_user.id
    if uid not in user_choice:
        return
    
    try:
        rub = float(message.text.replace(",", ".").replace(" ", ""))
        if rub < 1000 or rub > 50000:
            await message.answer("❌ *Сумма должна быть от 1 000 до 50 000 ₽*", parse_mode="Markdown")
            return
        
        action, coin = user_choice[uid]
        type_text = "Покупка" if action == "buy" else "Продажа"
        
        # Пока просто подтверждение (базу данных добавим позже)
        await message.answer(f"✅ *Заявка создана!*\n\n{type_text} {coin} на {rub:,.0f} ₽\n\n📞 *Оператор свяжется с вами*", parse_mode="Markdown", reply_markup=main_menu())
        
        # Удаляем выбор пользователя
        del user_choice[uid]
        
    except ValueError:
        await message.answer("❌ *Введи число, например: 5000*", parse_mode="Markdown")

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
