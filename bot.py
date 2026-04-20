import asyncio
import sqlite3
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8177854087

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

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('exchange_bot.db', check_same_thread=False)
cur = conn.cursor()
cur.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        full_name TEXT,
        type TEXT,
        coin TEXT,
        amount REAL,
        status TEXT,
        created_at INTEGER
    )
''')
cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        language TEXT DEFAULT 'ru'
    )
''')
conn.commit()

# Временное хранилище
user_choice = {}

# ========== ТЕКСТЫ ==========
TEXTS = {
    'ru': {
        'welcome': "🏦 *Добро пожаловать в КриптоОбменник!*",
        'buy_btn': "🟢 Купить",
        'sell_btn': "🔴 Продать",
        'rates_btn': "📊 Курсы",
        'test_btn': "🔴 ТЕСТ",
        'back_btn': "🔙 Назад",
        'select_buy': "💰 *Введи сумму в рублях для покупки {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽",
        'select_sell': "💰 *Введи сумму в рублях для продажи {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽",
        'limit_error': "❌ *Сумма должна быть от 1 000 до 50 000 ₽*",
        'order_created': "✅ *Заявка #{id} создана!*\n\n{type} {coin} на {amount} ₽\n\n📞 *Оператор свяжется с вами*",
        'test_success': "✅ Кнопка работает!",
        'no_orders': "📭 *Нет новых заявок*",
        'orders_title': "📋 *Новые заявки:*\n\n",
        'type_buy': "Покупка",
        'type_sell': "Продажа",
        'change_lang': "🌐 Сменить язык",
        'lang_selected': "✅ Язык: Русский",
        'select_lang': "🌐 *Выбери язык:*",
        'rates_text': (
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
    },
    'en': {
        'welcome': "🏦 *Welcome to Crypto Exchanger!*",
        'buy_btn': "🟢 Buy",
        'sell_btn': "🔴 Sell",
        'rates_btn': "📊 Rates",
        'test_btn': "🔴 TEST",
        'back_btn': "🔙 Back",
        'select_buy': "💰 *Enter amount in RUB to buy {coin}:*\n📊 *Limits:* 1,000 - 50,000 RUB",
        'select_sell': "💰 *Enter amount in RUB to sell {coin}:*\n📊 *Limits:* 1,000 - 50,000 RUB",
        'limit_error': "❌ *Amount must be between 1,000 and 50,000 RUB*",
        'order_created': "✅ *Order #{id} created!*\n\n{type} {coin} for {amount} RUB\n\n📞 *Operator will contact you*",
        'test_success': "✅ Button works!",
        'no_orders': "📭 *No new orders*",
        'orders_title': "📋 *New orders:*\n\n",
        'type_buy': "Purchase",
        'type_sell': "Sale",
        'change_lang': "🌐 Change language",
        'lang_selected': "✅ Language: English",
        'select_lang': "🌐 *Choose language:*",
        'rates_text': (
            "📊 *Market rates:*\n"
            "└ USDT: 82.81 RUB\n"
            "└ BTC: 5,725,873 RUB\n"
            "└ ETH: 174,639 RUB\n\n"
            "📈 *Buy via MOSS PAY:*\n"
            "└ USDT: 91.81 RUB (+10%)\n"
            "└ BTC: 6,298,873 RUB (+10%)\n"
            "└ ETH: 192,102 RUB (+10%)\n\n"
            "📉 *Sell via MOSS PAY:*\n"
            "└ USDT: 81.15 RUB (-2%)\n"
            "└ BTC: 5,611,355 RUB (-2%)\n"
            "└ ETH: 171,146 RUB (-2%)\n\n"
            "⚙️ *Markup:* buy +10%, sell -2%"
        )
    }
}

def get_text(user_id, key, **kwargs):
    cur.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    lang = row[0] if row else 'ru'
    text = TEXTS[lang].get(key, TEXTS['ru'][key])
    if kwargs:
        text = text.format(**kwargs)
    return text

def get_lang(user_id):
    cur.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else 'ru'

def main_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(user_id, 'buy_btn'), callback_data="buy")],
        [InlineKeyboardButton(text=get_text(user_id, 'sell_btn'), callback_data="sell")],
        [InlineKeyboardButton(text=get_text(user_id, 'rates_btn'), callback_data="rates")],
        [InlineKeyboardButton(text=get_text(user_id, 'test_btn'), callback_data="test")],
        [InlineKeyboardButton(text=get_text(user_id, 'change_lang'), callback_data="change_lang")]
    ])

def buy_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 USDT", callback_data="buy_USDT")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="buy_BTC")],
        [InlineKeyboardButton(text="💎 ETH", callback_data="buy_ETH")],
        [InlineKeyboardButton(text="💳 RapiraRUB", callback_data="buy_Rapira")],
        [InlineKeyboardButton(text=get_text(user_id, 'back_btn'), callback_data="main")]
    ])

def sell_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 USDT", callback_data="sell_USDT")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="sell_BTC")],
        [InlineKeyboardButton(text="💎 ETH", callback_data="sell_ETH")],
        [InlineKeyboardButton(text="💳 RapiraRUB", callback_data="sell_Rapira")],
        [InlineKeyboardButton(text=get_text(user_id, 'back_btn'), callback_data="main")]
    ])

def lang_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    cur.execute("INSERT OR IGNORE INTO users (user_id, language) VALUES (?, 'ru')", (uid,))
    conn.commit()
    
    photo_url = "https://raw.githubusercontent.com/alexandr956/crypto-bot/main/welcome.jpg"
    try:
        await message.answer_photo(photo_url, caption=get_text(uid, 'welcome'), parse_mode="Markdown", reply_markup=main_menu(uid))
    except:
        await message.answer(get_text(uid, 'welcome'), parse_mode="Markdown", reply_markup=main_menu(uid))

@dp.callback_query()
async def handle_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    data = call.data
    
    # Смена языка
    if data == "change_lang":
        await call.message.edit_reply_markup(reply_markup=lang_menu())
        await call.answer()
        return
    
    if data.startswith("lang_"):
        lang = 'ru' if data == "lang_ru" else 'en'
        cur.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))
        conn.commit()
        await call.message.edit_reply_markup(reply_markup=main_menu(uid))
        await call.message.answer(get_text(uid, 'lang_selected'), parse_mode="Markdown")
        await call.answer()
        return
    
    # Назад в главное меню
    if data == "main":
        await call.message.edit_reply_markup(reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Покупка
    if data == "buy":
        await call.message.edit_reply_markup(reply_markup=buy_menu(uid))
        await call.answer()
        return
    
    # Продажа
    if data == "sell":
        await call.message.edit_reply_markup(reply_markup=sell_menu(uid))
        await call.answer()
        return
    
    # Курсы
    if data == "rates":
        await call.message.answer(get_text(uid, 'rates_text'), parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Тест
    if data == "test":
        await call.message.answer(get_text(uid, 'test_success'), reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Выбор валюты для покупки
    if data.startswith("buy_"):
        coin = data.split("_")[1]
        user_choice[uid] = ("buy", coin)
        await call.message.answer(get_text(uid, 'select_buy', coin=coin), parse_mode="Markdown")
        await call.answer()
        return
    
    # Выбор валюты для продажи
    if data.startswith("sell_"):
        coin = data.split("_")[1]
        user_choice[uid] = ("sell", coin)
        await call.message.answer(get_text(uid, 'select_sell', coin=coin), parse_mode="Markdown")
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
            await message.answer(get_text(uid, 'limit_error'), parse_mode="Markdown")
            return
        
        action, coin = user_choice[uid]
        type_text = get_text(uid, 'type_buy') if action == "buy" else get_text(uid, 'type_sell')
        
        # Сохраняем заявку
        cur.execute('''
            INSERT INTO orders (user_id, username, full_name, type, coin, amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (uid, message.from_user.username, message.from_user.full_name, action, coin, rub, "new", int(time.time())))
        conn.commit()
        order_id = cur.lastrowid
        
        await message.answer(
            get_text(uid, 'order_created', id=order_id, type=type_text, coin=coin, amount=f"{rub:,.0f}"),
            parse_mode="Markdown",
            reply_markup=main_menu(uid)
        )
        
        # Уведомление админу
        username = f"@{message.from_user.username}" if message.from_user.username else "no username"
        await bot.send_message(
            ADMIN_ID,
            f"🆕 *NEW ORDER #{order_id}*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Amount: {rub:,.0f} RUB\n"
            f"👤 User: {message.from_user.full_name}\n"
            f"{username}\n"
            f"🆔 ID: {uid}",
            parse_mode="Markdown"
        )
        
        del user_choice[uid]
        
    except ValueError:
        await message.answer(get_text(uid, 'limit_error'), parse_mode="Markdown")

@dp.message(Command("orders"))
async def admin_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cur.execute('SELECT id, type, coin, amount, status FROM orders WHERE status = "new" ORDER BY created_at DESC')
    orders = cur.fetchall()
    
    if not orders:
        await message.answer(get_text(ADMIN_ID, 'no_orders'), parse_mode="Markdown")
        return
    
    text = get_text(ADMIN_ID, 'orders_title')
    for order in orders:
        text += f"#{order[0]} | {order[1]} {order[2]} | {order[3]:,.0f} ₽ | {order[4]}\n"
    
    await message.answer(text, parse_mode="Markdown")

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
