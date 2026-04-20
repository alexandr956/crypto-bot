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
        crypto_amount REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER,
        updated_at INTEGER
    )
''')
cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        language TEXT DEFAULT 'ru'
    )
''')
conn.commit()

# Временное хранилище для неподтверждённых заявок
pending_orders = {}

# ========== ФУНКЦИЯ ДЛЯ КУРСОВ ==========
async def get_crypto_rates():
    """
    Рыночные курсы. Ты меняешь эти три цифры, остальное считается автоматически.
    """
    # ========== МЕНЯЙ ТОЛЬКО ЭТИ ТРИ ЦИФРЫ ==========
    market_usdt = 91.50     # Рыночный курс USDT
    market_btc = 5500000    # Рыночный курс BTC
    market_eth = 220000     # Рыночный курс ETH
    # ================================================
    
    # Комиссия MOSS PAY (покупка +10%, продажа -2%)
    commission_buy = 1.10    # +10%
    commission_sell = 0.98   # -2%
    
    # Рассчитываем курсы с комиссией
    buy_usdt = market_usdt * commission_buy
    buy_btc = market_btc * commission_buy
    buy_eth = market_eth * commission_buy
    
    sell_usdt = market_usdt * commission_sell
    sell_btc = market_btc * commission_sell
    sell_eth = market_eth * commission_sell
    
    return {
        'market': {'usdt': market_usdt, 'btc': market_btc, 'eth': market_eth},
        'buy': {'usdt': buy_usdt, 'btc': buy_btc, 'eth': buy_eth},
        'sell': {'usdt': sell_usdt, 'btc': sell_btc, 'eth': sell_eth}
    }

# ========== ФУНКЦИЯ ДЛЯ РАСЧЁТА КРИПТЫ ==========
def calculate_crypto_amount(rub, coin, action, rates):
    """
    Рассчитывает количество криптовалюты за указанную сумму в рублях.
    action: 'buy' или 'sell'
    coin: 'BTC', 'ETH', 'USDT', 'Rapira'
    """
    if action == 'buy':
        if coin == 'BTC':
            price = rates['buy']['btc']
            crypto = rub / price
        elif coin == 'ETH':
            price = rates['buy']['eth']
            crypto = rub / price
        elif coin == 'USDT':
            price = rates['buy']['usdt']
            crypto = rub / price
        else:  # RapiraRUB (1:1 с рублём)
            crypto = rub
    else:  # sell
        if coin == 'BTC':
            price = rates['sell']['btc']
            crypto = rub / price
        elif coin == 'ETH':
            price = rates['sell']['eth']
            crypto = rub / price
        elif coin == 'USDT':
            price = rates['sell']['usdt']
            crypto = rub / price
        else:  # RapiraRUB
            crypto = rub
    
    return crypto

# ========== ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ СТАТУСА ==========
async def update_order_status(order_id, new_status, user_id=None, admin_id=ADMIN_ID):
    """Обновляет статус заявки и уведомляет клиента и админа"""
    cur.execute('SELECT user_id, type, coin, amount, crypto_amount FROM orders WHERE id = ?', (order_id,))
    order = cur.fetchone()
    if not order:
        return
    
    user_id_db, o_type, coin, amount, crypto = order
    
    cur.execute('UPDATE orders SET status = ?, updated_at = ? WHERE id = ?', (new_status, int(time.time()), order_id))
    conn.commit()
    
    # Статусы и их отображение
    status_display = {
        'pending': '🟡 Ожидает обработки',
        'processing': '🔵 В обработке',
        'completed': '🟢 Выполнена',
        'rejected': '🔴 Отклонена',
        'cancelled': '⚫ Отменена'
    }
    
    status_text = status_display.get(new_status, new_status)
    type_text = "Покупка" if o_type == "buy" else "Продажа"
    
    # Уведомляем клиента
    user_lang = get_lang(user_id_db)
    if user_lang == 'ru':
        await bot.send_message(
            user_id_db,
            f"✅ *Статус заявки #{order_id} обновлён*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Сумма: {amount:,.0f} ₽\n"
            f"🪙 Крипта: {crypto:.8f} {coin}\n"
            f"📊 *Новый статус:* {status_text}",
            parse_mode="Markdown"
        )
    else:
        await bot.send_message(
            user_id_db,
            f"✅ *Order #{order_id} status updated*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Amount: {amount:,.0f} RUB\n"
            f"🪙 Crypto: {crypto:.8f} {coin}\n"
            f"📊 *New status:* {status_text}",
            parse_mode="Markdown"
        )

# ========== ТЕКСТЫ ==========
TEXTS = {
    'ru': {
        'welcome': "👋 *Привет, {name}!*\n\n🏦 *Добро пожаловать в КриптоОбменник MOSS PAY*\n\n💎 *Почему выбирают нас:*\n• 🚀 Мгновенные заявки\n• 🔒 Безопасные сделки\n• 💬 Поддержка 24/7\n• 💰 Лучшие курсы\n\n👇 *Выберите действие в меню ниже*",
        'buy_btn': "🟢 Купить",
        'sell_btn': "🔴 Продать",
        'rates_btn': "📊 Курсы",
        'help_btn': "❓ Помощь",
        'contacts_btn': "📞 Контакты",
        'back_btn': "🔙 Назад",
        'select_buy': "💰 *Введи сумму в рублях для покупки {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽",
        'select_sell': "💰 *Введи сумму в рублях для продажи {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽",
        'limit_error': "❌ *Сумма должна быть от 1 000 до 50 000 ₽*",
        'confirm_order': "💰 *Вы ввели:* {amount} ₽\n🪙 *Вы получите:* {crypto:.8f} {coin}\n📊 *Лимиты:* 1 000 - 50 000 ₽\n\n✅ *Подтвердить заявку?*",
        'order_created': "✅ *Заявка #{id} создана!*\n\n📌 {type} {coin}\n💰 Сумма: {amount} ₽\n🪙 Крипта: {crypto:.8f} {coin}\n📊 Статус: 🟡 Ожидает обработки\n\n📞 *Оператор свяжется с вами*",
        'order_cancelled': "❌ *Заявка отменена*",
        'no_orders': "📭 *Нет заявок*",
        'orders_title': "📋 *Ваши заявки:*\n\n",
        'type_buy': "Покупка",
        'type_sell': "Продажа",
        'change_lang': "🌐 Сменить язык",
        'lang_selected': "✅ Язык: Русский",
        'select_lang': "🌐 *Выбери язык:*",
        'help_text': (
            "❓ *Как пользоваться обменником:*\n\n"
            "1️⃣ *Купить криптовалюту*\n"
            "   • Выбери валюту (USDT, BTC, ETH, RapiraRUB)\n"
            "   • Введи сумму в рублях (от 1000 до 50000)\n"
            "   • Подтверди заявку\n"
            "   • Оператор свяжется с тобой\n\n"
            "2️⃣ *Продать криптовалюту*\n"
            "   • Выбери валюту\n"
            "   • Введи сумму в рублях\n"
            "   • Подтверди заявку\n"
            "   • Оператор свяжется с тобой\n\n"
            "3️⃣ *Курсы*\n"
            "   • Актуальные курсы с наценкой 10% (покупка) и -2% (продажа)\n\n"
            "4️⃣ *Контакты*\n"
            "   • Связь с оператором: кнопка ниже\n\n"
            "⏰ *Время работы:* 10:00 – 22:00 МСК"
        ),
        'contacts_text': (
            "📞 *Связь с оператором:*\n\n"
            "• Telegram: @shakakobmen\n"
            "• WhatsApp: +7 999 123-45-67\n"
            "• Email: support@crypto-exchange.ru\n\n"
            "⏰ *Время ответа:* обычно в течение 5 минут"
        ),
        'admin_panel': "🔧 *Панель администратора*\n\nВыберите действие:",
        'admin_orders_btn': "📋 Список заявок",
        'admin_stats_btn': "📊 Статистика",
        'loading_rates': "🔄 *Загружаю актуальные курсы...*",
        'confirm_yes': "✅ Да, подтверждаю",
        'confirm_no': "❌ Нет, отменить"
    },
    'en': {
        'welcome': "👋 *Hi {name}!*\n\n🏦 *Welcome to MOSS PAY Crypto Exchanger*\n\n💎 *Why choose us:*\n• 🚀 Instant orders\n• 🔒 Secure transactions\n• 💬 24/7 support\n• 💰 Best rates\n\n👇 *Select an action below*",
        'buy_btn': "🟢 Buy",
        'sell_btn': "🔴 Sell",
        'rates_btn': "📊 Rates",
        'help_btn': "❓ Help",
        'contacts_btn': "📞 Contacts",
        'back_btn': "🔙 Back",
        'select_buy': "💰 *Enter amount in RUB to buy {coin}:*\n📊 *Limits:* 1,000 - 50,000 RUB",
        'select_sell': "💰 *Enter amount in RUB to sell {coin}:*\n📊 *Limits:* 1,000 - 50,000 RUB",
        'limit_error': "❌ *Amount must be between 1,000 and 50,000 RUB*",
        'confirm_order': "💰 *You entered:* {amount} RUB\n🪙 *You will receive:* {crypto:.8f} {coin}\n📊 *Limits:* 1,000 - 50,000 RUB\n\n✅ *Confirm order?*",
        'order_created': "✅ *Order #{id} created!*\n\n📌 {type} {coin}\n💰 Amount: {amount} RUB\n🪙 Crypto: {crypto:.8f} {coin}\n📊 Status: 🟡 Pending\n\n📞 *Operator will contact you*",
        'order_cancelled': "❌ *Order cancelled*",
        'no_orders': "📭 *No orders*",
        'orders_title': "📋 *Your orders:*\n\n",
        'type_buy': "Purchase",
        'type_sell': "Sale",
        'change_lang': "🌐 Change language",
        'lang_selected': "✅ Language: English",
        'select_lang': "🌐 *Choose language:*",
        'help_text': (
            "❓ *How to use the exchanger:*\n\n"
            "1️⃣ *Buy crypto*\n"
            "   • Choose currency (USDT, BTC, ETH, RapiraRUB)\n"
            "   • Enter amount in RUB (1000 - 50000)\n"
            "   • Confirm order\n"
            "   • Operator will contact you\n\n"
            "2️⃣ *Sell crypto*\n"
            "   • Choose currency\n"
            "   • Enter amount in RUB\n"
            "   • Confirm order\n"
            "   • Operator will contact you\n\n"
            "3️⃣ *Rates*\n"
            "   • Current rates with 10% markup (buy) and -2% (sell)\n\n"
            "4️⃣ *Contacts*\n"
            "   • Contact operator: button below\n\n"
            "⏰ *Working hours:* 10:00 – 22:00 MSK"
        ),
        'contacts_text': (
            "📞 *Contact operator:*\n\n"
            "• Telegram: @shakakobmen\n"
            "• WhatsApp: +7 999 123-45-67\n"
            "• Email: support@crypto-exchange.ru\n\n"
            "⏰ *Response time:* usually within 5 minutes"
        ),
        'admin_panel': "🔧 *Admin panel*\n\nSelect action:",
        'admin_orders_btn': "📋 Orders list",
        'admin_stats_btn': "📊 Statistics",
        'loading_rates': "🔄 *Loading current rates...*",
        'confirm_yes': "✅ Yes, confirm",
        'confirm_no': "❌ No, cancel"
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
        [InlineKeyboardButton(text=get_text(user_id, 'help_btn'), callback_data="help")],
        [InlineKeyboardButton(text=get_text(user_id, 'contacts_btn'), callback_data="contacts")],
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

def confirm_menu(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_yes_{order_id}"),
         InlineKeyboardButton(text="❌ Нет", callback_data=f"confirm_no_{order_id}")]
    ])

def order_buttons(order_id, status):
    """Кнопки для админа в зависимости от статуса заявки"""
    if status == 'pending':
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ В обработку", callback_data=f"process_{order_id}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")]
        ])
    elif status == 'processing':
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнить", callback_data=f"complete_{order_id}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")]
        ])
    else:
        return None

def lang_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def contacts_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Написать оператору", url="https://t.me/shakakobmen")],
        [InlineKeyboardButton(text="📞 WhatsApp", url="https://wa.me/79991234567")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    cur.execute("INSERT OR IGNORE INTO users (user_id, language) VALUES (?, 'ru')", (uid,))
    conn.commit()
    
    photo_url = "https://raw.githubusercontent.com/alexandr956/crypto-bot/main/welcome.jpg"
    lang = get_lang(uid)
    
    if lang == 'ru':
        welcome_text = f"👋 *Привет, {message.from_user.first_name}!*\n\n🏦 *Добро пожаловать в КриптоОбменник MOSS PAY*\n\n💎 *Почему выбирают нас:*\n• 🚀 Мгновенные заявки\n• 🔒 Безопасные сделки\n• 💬 Поддержка 24/7\n• 💰 Лучшие курсы\n\n👇 *Выберите действие в меню ниже*"
    else:
        welcome_text = f"👋 *Hi {message.from_user.first_name}!*\n\n🏦 *Welcome to MOSS PAY Crypto Exchanger*\n\n💎 *Why choose us:*\n• 🚀 Instant orders\n• 🔒 Secure transactions\n• 💬 24/7 support\n• 💰 Best rates\n\n👇 *Select an action below*"
    
    try:
        await message.answer_photo(photo_url, caption=welcome_text, parse_mode="Markdown", reply_markup=main_menu(uid))
    except:
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu(uid))

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(get_text(ADMIN_ID, 'admin_panel'), parse_mode="Markdown", reply_markup=admin_menu())

@dp.callback_query()
async def handle_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    data = call.data
    
    # Подтверждение заявки
    if data.startswith("confirm_yes_"):
        order_id = int(data.split("_")[2])
        if order_id not in pending_orders:
            await call.message.edit_text("❌ Заявка не найдена", reply_markup=main_menu(uid))
            await call.answer()
            return
        
        order_data = pending_orders[order_id]
        action, coin, rub, crypto = order_data
        
        type_text = get_text(uid, 'type_buy') if action == "buy" else get_text(uid, 'type_sell')
        
        cur.execute('''
            INSERT INTO orders (user_id, username, full_name, type, coin, amount, crypto_amount, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (uid, call.from_user.username, call.from_user.full_name, action, coin, rub, crypto, 'pending', int(time.time()), int(time.time())))
        order_id_db = cur.lastrowid
        conn.commit()
        
        del pending_orders[order_id]
        
        await call.message.edit_text(
            get_text(uid, 'order_created', id=order_id_db, type=type_text, coin=coin, amount=f"{rub:,.0f}", crypto=crypto),
            parse_mode="Markdown",
            reply_markup=main_menu(uid)
        )
        
        username = f"@{call.from_user.username}" if call.from_user.username else "no username"
        await bot.send_message(
            ADMIN_ID,
            f"🆕 *НОВАЯ ЗАЯВКА #{order_id_db}*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Сумма: {rub:,.0f} ₽\n"
            f"🪙 Крипта: {crypto:.8f} {coin}\n"
            f"👤 Пользователь: {call.from_user.full_name}\n"
            f"{username}\n"
            f"🆔 ID: {uid}\n"
            f"📊 Статус: 🟡 Ожидает",
            parse_mode="Markdown",
            reply_markup=order_buttons(order_id_db, 'pending')
        )
        await call.answer()
        return
    
    if data.startswith("confirm_no_"):
        order_id = int(data.split("_")[2])
        if order_id in pending_orders:
            del pending_orders[order_id]
        await call.message.edit_text(get_text(uid, 'order_cancelled'), parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
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
        await call.message.answer(get_text(uid, 'loading_rates'), parse_mode="Markdown")
        
        rates = await get_crypto_rates()

        if rates is None:
            await call.message.answer("❌ *Не удалось загрузить курсы. Попробуйте позже.*", parse_mode="Markdown")
            await call.answer()
            return

        market_usdt = rates['market']['usdt']
        market_btc = rates['market']['btc']
        market_eth = rates['market']['eth']
        
        buy_usdt = rates['buy']['usdt']
        buy_btc = rates['buy']['btc']
        buy_eth = rates['buy']['eth']
        
        sell_usdt = rates['sell']['usdt']
        sell_btc = rates['sell']['btc']
        sell_eth = rates['sell']['eth']

        if get_lang(uid) == 'ru':
            text = (
                f"📊 *Рыночные курсы:*\n"
                f"└ USDT: {market_usdt:.2f} ₽\n"
                f"└ BTC: {market_btc:,.0f} ₽\n"
                f"└ ETH: {market_eth:,.0f} ₽\n\n"
                
                f"📈 *Покупка через MOSS PAY (+10%):*\n"
                f"└ USDT: {buy_usdt:.2f} ₽\n"
                f"└ BTC: {buy_btc:,.0f} ₽\n"
                f"└ ETH: {buy_eth:,.0f} ₽\n\n"
                
                f"📉 *Продажа через MOSS PAY (-2%):*\n"
                f"└ USDT: {sell_usdt:.2f} ₽\n"
                f"└ BTC: {sell_btc:,.0f} ₽\n"
                f"└ ETH: {sell_eth:,.0f} ₽\n\n"
                
                f"⚙️ *Комиссия MOSS PAY:* покупка +10%, продажа -2%"
            )
        else:
            text = (
                f"📊 *Market rates:*\n"
                f"└ USDT: {market_usdt:.2f} RUB\n"
                f"└ BTC: {market_btc:,.0f} RUB\n"
                f"└ ETH: {market_eth:,.0f} RUB\n\n"
                
                f"📈 *Buy via MOSS PAY (+10%):*\n"
                f"└ USDT: {buy_usdt:.2f} RUB\n"
                f"└ BTC: {buy_btc:,.0f} RUB\n"
                f"└ ETH: {buy_eth:,.0f} RUB\n\n"
                
                f"📉 *Sell via MOSS PAY (-2%):*\n"
                f"└ USDT: {sell_usdt:.2f} RUB\n"
                f"└ BTC: {sell_btc:,.0f} RUB\n"
                f"└ ETH: {sell_eth:,.0f} RUB\n\n"
                
                f"⚙️ *MOSS PAY fee:* buy +10%, sell -2%"
            )
        
        await call.message.answer(text, parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Помощь
    if data == "help":
        await call.message.answer(get_text(uid, 'help_text'), parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Контакты
    if data == "contacts":
        await call.message.answer(get_text(uid, 'contacts_text'), parse_mode="Markdown", reply_markup=contacts_menu(uid))
        await call.answer()
        return
    
    # Админ панель - список заявок
    if data == "admin_orders":
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        cur.execute('SELECT id, type, coin, amount, status FROM orders WHERE status != "completed" ORDER BY created_at DESC')
        orders = cur.fetchall()
        if not orders:
            await call.message.answer(get_text(ADMIN_ID, 'no_orders'), parse_mode="Markdown")
        else:
            for order in orders:
                order_id, o_type, coin, amount, status = order
                type_text = "Покупка" if o_type == "buy" else "Продажа"
                status_display = {
                    'pending': '🟡 Ожидает',
                    'processing': '🔵 В обработке',
                    'rejected': '🔴 Отклонена',
                    'cancelled': '⚫ Отменена'
                }
                status_text = status_display.get(status, status)
                text = f"📋 *Заявка #{order_id}*\n\n{type_text} {coin}\n💰 {amount:,.0f} ₽\n📊 Статус: {status_text}"
                await call.message.answer(text, parse_mode="Markdown", reply_markup=order_buttons(order_id, status))
        await call.answer()
        return
    
    # Админ панель - статистика
    if data == "admin_stats":
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        cur.execute('SELECT COUNT(*), SUM(amount) FROM orders WHERE status = "pending"')
        pending_orders_count, pending_sum = cur.fetchone()
        cur.execute('SELECT COUNT(*), SUM(amount) FROM orders WHERE status = "processing"')
        processing_orders, processing_sum = cur.fetchone()
        cur.execute('SELECT COUNT(*), SUM(amount) FROM orders WHERE status = "completed"')
        completed_orders, completed_sum = cur.fetchone()
        cur.execute('SELECT COUNT(*), SUM(amount) FROM orders')
        total_orders, total_sum = cur.fetchone()
        
        text = (
            "📊 *Статистика:*\n\n"
            f"🟡 Ожидают: {pending_orders_count or 0} (на {pending_sum or 0:,.0f} ₽)\n"
            f"🔵 В обработке: {processing_orders or 0} (на {processing_sum or 0:,.0f} ₽)\n"
            f"🟢 Выполнено: {completed_orders or 0} (на {completed_sum or 0:,.0f} ₽)\n\n"
            f"📦 Всего заявок: {total_orders or 0}\n"
            f"💵 Общая сумма: {total_sum or 0:,.0f} ₽"
        )
        await call.message.answer(text, parse_mode="Markdown", reply_markup=admin_menu())
        await call.answer()
        return
    
    # Обработка админских кнопок (статусы)
    if data.startswith("process_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[1])
        await update_order_status(order_id, 'processing')
        await call.message.edit_text(f"✅ Заявка #{order_id} переведена в статус «В обработке»", reply_markup=order_buttons(order_id, 'processing'))
        await call.answer()
        return
    
    if data.startswith("complete_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[1])
        await update_order_status(order_id, 'completed')
        await call.message.edit_text(f"✅ Заявка #{order_id} выполнена!", reply_markup=None)
        await call.answer()
        return
    
    if data.startswith("reject_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[1])
        await update_order_status(order_id, 'rejected')
        await call.message.edit_text(f"❌ Заявка #{order_id} отклонена!", reply_markup=None)
        await call.answer()
        return
    
    # Выбор валюты для покупки
    if data.startswith("buy_"):
        coin = data.split("_")[1]
        rates = await get_crypto_rates()
        if rates is None:
            await call.message.answer("❌ *Ошибка загрузки курсов. Попробуйте позже.*", parse_mode="Markdown")
            await call.answer()
            return
        
        pending_orders[uid] = {"action": "buy", "coin": coin, "rates": rates}
        await call.message.answer(get_text(uid, 'select_buy', coin=coin), parse_mode="Markdown")
        await call.answer()
        return
    
    # Выбор валюты для продажи
    if data.startswith("sell_"):
        coin = data.split("_")[1]
        rates = await get_crypto_rates()
        if rates is None:
            await call.message.answer("❌ *Ошибка загрузки курсов. Попробуйте позже.*", parse_mode="Markdown")
            await call.answer()
            return
        
        pending_orders[uid] = {"action": "sell", "coin": coin, "rates": rates}
        await call.message.answer(get_text(uid, 'select_sell', coin=coin), parse_mode="Markdown")
        await call.answer()
        return

@dp.message()
async def handle_amount(message: types.Message):
    uid = message.from_user.id
    if uid not in pending_orders:
        return
    
    try:
        rub = float(message.text.replace(",", ".").replace(" ", ""))
        if rub < 1000 or rub > 50000:
            await message.answer(get_text(uid, 'limit_error'), parse_mode="Markdown")
            return
        
        action = pending_orders[uid]["action"]
        coin = pending_orders[uid]["coin"]
        rates = pending_orders[uid]["rates"]
        
        # Рассчитываем количество крипты
        crypto = calculate_crypto_amount(rub, coin, action, rates)
        
        # Сохраняем заявку во временное хранилище с уникальным ID
        order_id = int(time.time() * 1000)
        pending_orders[order_id] = (action, coin, rub, crypto)
        del pending_orders[uid]
        
        await message.answer(
            get_text(uid, 'confirm_order', amount=f"{rub:,.0f}", crypto=crypto, coin=coin),
            parse_mode="Markdown",
            reply_markup=confirm_menu(order_id)
        )
        
    except ValueError:
        await message.answer(get_text(uid, 'limit_error'), parse_mode="Markdown")

@dp.message(Command("orders"))
async def user_orders(message: types.Message):
    uid = message.from_user.id
    cur.execute('SELECT id, type, coin, amount, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (uid,))
    orders = cur.fetchall()
    
    if not orders:
        await message.answer(get_text(uid, 'no_orders'), parse_mode="Markdown")
        return
    
    status_display = {
        'pending': '🟡 Ожидает обработки',
        'processing': '🔵 В обработке',
        'completed': '🟢 Выполнена',
        'rejected': '🔴 Отклонена',
        'cancelled': '⚫ Отменена'
    }
    
    text = get_text(uid, 'orders_title')
    for order in orders:
        order_id, o_type, coin, amount, status, created_at = order
        type_text = "Покупка" if o_type == "buy" else "Продажа"
        status_text = status_display.get(status, status)
        date = time.strftime('%d.%m %H:%M', time.localtime(created_at))
        text += f"📌 #{order_id} | {type_text} {coin}\n   💰 {amount:,.0f} ₽ | {status_text} | {date}\n\n"
    
    await message.answer(text, parse_mode="Markdown")

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
