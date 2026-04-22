import asyncio
import sqlite3
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8177854087

# Настройки по умолчанию
DEFAULT_MIN_LIMIT = 1000
DEFAULT_MAX_LIMIT = 50000
DEFAULT_MARKET_USDT = 91.50
DEFAULT_MARKET_BTC = 5500000
DEFAULT_MARKET_ETH = 220000

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
        reject_reason TEXT DEFAULT '',
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
cur.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
''')
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_limit', ?)", (str(DEFAULT_MIN_LIMIT),))
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('max_limit', ?)", (str(DEFAULT_MAX_LIMIT),))
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('market_usdt', ?)", (str(DEFAULT_MARKET_USDT),))
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('market_btc', ?)", (str(DEFAULT_MARKET_BTC),))
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('market_eth', ?)", (str(DEFAULT_MARKET_ETH),))
conn.commit()

def get_setting(key, default):
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    if row:
        try:
            return float(row[0]) if '.' in row[0] else int(row[0])
        except:
            return default
    return default

def set_setting(key, value):
    cur.execute("UPDATE settings SET value = ? WHERE key = ?", (str(value), key))
    conn.commit()

def get_min_limit():
    return get_setting('min_limit', DEFAULT_MIN_LIMIT)

def get_max_limit():
    return get_setting('max_limit', DEFAULT_MAX_LIMIT)

def get_market_usdt():
    return get_setting('market_usdt', DEFAULT_MARKET_USDT)

def get_market_btc():
    return get_setting('market_btc', DEFAULT_MARKET_BTC)

def get_market_eth():
    return get_setting('market_eth', DEFAULT_MARKET_ETH)

def set_market_usdt(value):
    set_setting('market_usdt', value)

def set_market_btc(value):
    set_setting('market_btc', value)

def set_market_eth(value):
    set_setting('market_eth', value)

def set_min_limit(value):
    set_setting('min_limit', value)

def set_max_limit(value):
    set_setting('max_limit', value)

pending_orders = {}

# ========== ФУНКЦИЯ ДЛЯ КУРСОВ ==========
async def get_crypto_rates():
    market_usdt = get_market_usdt()
    market_btc = get_market_btc()
    market_eth = get_market_eth()
    
    commission_buy = 1.10
    commission_sell = 0.98
    
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

def calculate_crypto_amount(rub, coin, action, rates):
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
        else:
            crypto = rub
    else:
        if coin == 'BTC':
            price = rates['sell']['btc']
            crypto = rub / price
        elif coin == 'ETH':
            price = rates['sell']['eth']
            crypto = rub / price
        elif coin == 'USDT':
            price = rates['sell']['usdt']
            crypto = rub / price
        else:
            crypto = rub
    return crypto

def format_datetime(timestamp):
    """Форматирует timestamp в читаемую дату и время"""
    return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')

def get_status_emoji(status):
    """Возвращает эмодзи для статуса"""
    emojis = {
        'pending': '🟡',
        'processing': '🔵',
        'completed': '🟢',
        'rejected': '🔴',
        'cancelled': '⚫'
    }
    return emojis.get(status, '⚪')

def get_status_text(status, lang='ru'):
    """Возвращает текст статуса на нужном языке"""
    statuses = {
        'ru': {
            'pending': 'Ожидает обработки',
            'processing': 'В обработке',
            'completed': 'Выполнена',
            'rejected': 'Отклонена',
            'cancelled': 'Отменена'
        },
        'en': {
            'pending': 'Pending',
            'processing': 'Processing',
            'completed': 'Completed',
            'rejected': 'Rejected',
            'cancelled': 'Cancelled'
        }
    }
    return statuses[lang].get(status, status)

def user_notification_buttons(order_id, lang='ru'):
    """Кнопки для уведомления клиента"""
    if lang == 'ru':
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Написать оператору", url="https://t.me/shakakobmen")],
            [InlineKeyboardButton(text="📜 Мои заявки", callback_data="history")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Contact operator", url="https://t.me/shakakobmen")],
            [InlineKeyboardButton(text="📜 My orders", callback_data="history")]
        ])

def reject_reason_menu(order_id):
    """Кнопки для выбора причины отклонения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Недостаточно средств", callback_data=f"reject_reason_{order_id}_insufficient_funds")],
        [InlineKeyboardButton(text="❌ Неверный курс", callback_data=f"reject_reason_{order_id}_wrong_rate")],
        [InlineKeyboardButton(text="❌ Пользователь не ответил", callback_data=f"reject_reason_{order_id}_no_answer")],
        [InlineKeyboardButton(text="❌ Другая причина", callback_data=f"reject_reason_{order_id}_other")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_order_{order_id}")]
    ])

async def update_order_status(order_id, new_status, reject_reason=None):
    """Обновляет статус заявки и уведомляет клиента"""
    cur.execute('SELECT user_id, type, coin, amount, crypto_amount FROM orders WHERE id = ?', (order_id,))
    order = cur.fetchone()
    if not order:
        return
    
    user_id_db, o_type, coin, amount, crypto = order
    
    if new_status == 'rejected' and reject_reason:
        cur.execute('UPDATE orders SET status = ?, reject_reason = ?, updated_at = ? WHERE id = ?', 
                   (new_status, reject_reason, int(time.time()), order_id))
    else:
        cur.execute('UPDATE orders SET status = ?, updated_at = ? WHERE id = ?', 
                   (new_status, int(time.time()), order_id))
    conn.commit()
    
    status_emoji = get_status_emoji(new_status)
    user_lang = get_lang(user_id_db)
    status_text = get_status_text(new_status, user_lang)
    type_text = "Покупка" if o_type == "buy" else "Продажа"
    updated_time = format_datetime(int(time.time()))
    
    # Формируем сообщение для клиента
    if new_status == 'rejected' and reject_reason:
        reason_text = f"\n📝 Причина: {reject_reason}"
    else:
        reason_text = ""
    
    if user_lang == 'ru':
        notification = (
            f"{status_emoji} *Статус заявки #{order_id} обновлён*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Сумма: {amount:,.0f} ₽\n"
            f"🪙 Крипта: {crypto:.8f} {coin}\n"
            f"📊 Новый статус: {status_text}{reason_text}\n"
            f"🕐 Время: {updated_time}"
        )
    else:
        notification = (
            f"{status_emoji} *Order #{order_id} status updated*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Amount: {amount:,.0f} RUB\n"
            f"🪙 Crypto: {crypto:.8f} {coin}\n"
            f"📊 New status: {status_text}{reason_text}\n"
            f"🕐 Time: {updated_time}"
        )
    
    await bot.send_message(
        user_id_db,
        notification,
        parse_mode="Markdown",
        reply_markup=user_notification_buttons(order_id, user_lang)
    )

# ========== ТЕКСТЫ ==========
TEXTS = {
    'ru': {
        'welcome': "🏦 Добро пожаловать в КриптоОбменник MOSS PAY",
        'buy_btn': "🟢 Купить",
        'sell_btn': "🔴 Продать",
        'rates_btn': "📊 Курсы",
        'history_btn': "📜 История заявок",
        'help_btn': "❓ Помощь",
        'contacts_btn': "📞 Контакты",
        'back_btn': "🔙 Назад",
        'select_buy': "💰 Введи сумму в рублях для покупки {coin}:\n📊 Лимиты: {min} - {max} ₽",
        'select_sell': "💰 Введи сумму в рублях для продажи {coin}:\n📊 Лимиты: {min} - {max} ₽",
        'limit_error': "❌ Сумма должна быть от {min} до {max} ₽",
        'confirm_order': "💰 Вы ввели: {amount} ₽\n🪙 Вы получите: {crypto:.8f} {coin}\n📊 Лимиты: {min} - {max} ₽\n\n✅ Подтвердить заявку?",
        'order_created': "✅ Заявка #{id} создана!\n\n📌 {type} {coin}\n💰 Сумма: {amount} ₽\n🪙 Крипта: {crypto:.8f} {coin}\n📊 Статус: Ожидает обработки\n\n📞 Оператор свяжется с вами",
        'order_cancelled': "❌ Заявка отменена",
        'no_orders': "📭 Нет заявок",
        'orders_title': "📋 Ваши заявки:\n\n",
        'type_buy': "Покупка",
        'type_sell': "Продажа",
        'change_lang': "🌐 Сменить язык",
        'lang_selected': "✅ Язык: Русский",
        'select_lang': "🌐 Выбери язык:",
        'help_text': "❓ Как пользоваться обменником:\n\n1️⃣ Купить криптовалюту\n   • Выбери валюту\n   • Введи сумму\n   • Подтверди заявку\n\n2️⃣ Продать криптовалюту\n   • Выбери валюту\n   • Введи сумму\n   • Подтверди заявку\n\n3️⃣ Курсы\n   • Актуальные курсы с наценкой 10% (покупка) и -2% (продажа)\n\n4️⃣ Контакты\n   • Связь с оператором: кнопка ниже\n\n⏰ Время работы: 10:00 – 22:00 МСК",
        'contacts_text': "📞 Связь с оператором:\n\n• Telegram: @shakakobmen\n• WhatsApp: +7 999 123-45-67\n• Email: support@crypto-exchange.ru\n\n⏰ Время ответа: обычно в течение 5 минут",
        'admin_panel': "🔧 Панель администратора\n\nВыберите действие:",
        'admin_orders_btn': "📋 Список заявок",
        'admin_stats_btn': "📊 Статистика",
        'loading_rates': "🔄 Загружаю актуальные курсы...",
        'confirm_yes': "✅ Да, подтверждаю",
        'confirm_no': "❌ Нет, отменить"
    },
    'en': {
        'welcome': "🏦 Welcome to MOSS PAY Crypto Exchanger",
        'buy_btn': "🟢 Buy",
        'sell_btn': "🔴 Sell",
        'rates_btn': "📊 Rates",
        'history_btn': "📜 Order history",
        'help_btn': "❓ Help",
        'contacts_btn': "📞 Contacts",
        'back_btn': "🔙 Back",
        'select_buy': "💰 Enter amount in RUB to buy {coin}:\n📊 Limits: {min} - {max} RUB",
        'select_sell': "💰 Enter amount in RUB to sell {coin}:\n📊 Limits: {min} - {max} RUB",
        'limit_error': "❌ Amount must be between {min} and {max} RUB",
        'confirm_order': "💰 You entered: {amount} RUB\n🪙 You will receive: {crypto:.8f} {coin}\n📊 Limits: {min} - {max} RUB\n\n✅ Confirm order?",
        'order_created': "✅ Order #{id} created!\n\n📌 {type} {coin}\n💰 Amount: {amount} RUB\n🪙 Crypto: {crypto:.8f} {coin}\n📊 Status: Pending\n\n📞 Operator will contact you",
        'order_cancelled': "❌ Order cancelled",
        'no_orders': "📭 No orders",
        'orders_title': "📋 Your orders:\n\n",
        'type_buy': "Purchase",
        'type_sell': "Sale",
        'change_lang': "🌐 Change language",
        'lang_selected': "✅ Language: English",
        'select_lang': "🌐 Choose language:",
        'help_text': "❓ How to use:\n\n1️⃣ Buy crypto\n   • Choose currency\n   • Enter amount\n   • Confirm order\n\n2️⃣ Sell crypto\n   • Choose currency\n   • Enter amount\n   • Confirm order\n\n3️⃣ Rates\n   • Current rates with 10% markup (buy) and -2% (sell)\n\n4️⃣ Contacts\n   • Contact operator: button below\n\n⏰ Working hours: 10:00 – 22:00 MSK",
        'contacts_text': "📞 Contact operator:\n\n• Telegram: @shakakobmen\n• WhatsApp: +7 999 123-45-67\n• Email: support@crypto-exchange.ru\n\n⏰ Response time: usually within 5 minutes",
        'admin_panel': "🔧 Admin panel\n\nSelect action:",
        'admin_orders_btn': "📋 Orders list",
        'admin_stats_btn': "📊 Statistics",
        'loading_rates': "🔄 Loading current rates...",
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
        [InlineKeyboardButton(text=get_text(user_id, 'history_btn'), callback_data="history")],
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

def back_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(user_id, 'back_btn'), callback_data="main")]
    ])

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
        welcome_text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"🏦 Добро пожаловать в КриптоОбменник MOSS PAY\n\n"
            f"💎 Почему выбирают нас:\n"
            f"• 🚀 Мгновенные заявки\n"
            f"• 🔒 Безопасные сделки\n"
            f"• 💬 Поддержка 24/7\n"
            f"• 💰 Лучшие курсы\n"
            f"• 🔑 Обмен без KYC (верификации)\n\n"
            f"👇 Выберите действие в меню ниже"
        )
    else:
        welcome_text = (
            f"👋 Hi {message.from_user.first_name}!\n\n"
            f"🏦 Welcome to MOSS PAY Crypto Exchanger\n\n"
            f"💎 Why choose us:\n"
            f"• 🚀 Instant orders\n"
            f"• 🔒 Secure transactions\n"
            f"• 💬 24/7 support\n"
            f"• 💰 Best rates\n"
            f"• 🔑 Exchange without KYC (verification)\n\n"
            f"👇 Select an action below"
        )
    
    try:
        await message.answer_photo(photo_url, caption=welcome_text, reply_markup=main_menu(uid))
    except:
        await message.answer(welcome_text, reply_markup=main_menu(uid))

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(get_text(ADMIN_ID, 'admin_panel'), reply_markup=admin_menu())

@dp.message(Command("setrates"))
async def set_rates(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                f"❌ Неверный формат\n\n"
                f"Используй:\n"
                f"/setrates usdt 92.50\n"
                f"/setrates btc 5600000\n"
                f"/setrates eth 230000\n\n"
                f"📊 Текущие курсы:\n"
                f"└ USDT: {get_market_usdt()} ₽\n"
                f"└ BTC: {get_market_btc():,.0f} ₽\n"
                f"└ ETH: {get_market_eth():,.0f} ₽"
            )
            return
        
        currency = parts[1].lower()
        new_rate = float(parts[2])
        
        if new_rate <= 0:
            await message.answer("❌ Курс должен быть положительным числом")
            return
        
        if currency == 'usdt':
            set_market_usdt(new_rate)
            await message.answer(f"✅ Курс USDT обновлён!\n\nНовый курс: {new_rate:.2f} ₽")
        elif currency == 'btc':
            set_market_btc(new_rate)
            await message.answer(f"✅ Курс BTC обновлён!\n\nНовый курс: {new_rate:,.0f} ₽")
        elif currency == 'eth':
            set_market_eth(new_rate)
            await message.answer(f"✅ Курс ETH обновлён!\n\nНовый курс: {new_rate:,.0f} ₽")
        else:
            await message.answer("❌ Доступные валюты: usdt, btc, eth")
        
    except ValueError:
        await message.answer("❌ Введи число. Пример: /setrates usdt 92.50")

@dp.message(Command("rates"))
async def show_rates_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer(
        f"📊 Текущие рыночные курсы:\n\n"
        f"└ USDT: {get_market_usdt():.2f} ₽\n"
        f"└ BTC: {get_market_btc():,.0f} ₽\n"
        f"└ ETH: {get_market_eth():,.0f} ₽"
    )

@dp.message(Command("setlimits"))
async def set_limits(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                f"❌ Неверный формат\n\n"
                f"Используй: /setlimits 1000 50000\n"
                f"Текущие лимиты: {get_min_limit()} - {get_max_limit()} ₽"
            )
            return
        
        new_min = int(parts[1])
        new_max = int(parts[2])
        
        if new_min <= 0 or new_max <= 0:
            await message.answer("❌ Лимиты должны быть положительными числами")
            return
        
        if new_min >= new_max:
            await message.answer("❌ Минимальный лимит должен быть меньше максимального")
            return
        
        set_min_limit(new_min)
        set_max_limit(new_max)
        
        await message.answer(f"✅ Лимиты обновлены!\n\n📊 Новые лимиты: {new_min} - {new_max} ₽")
        
    except ValueError:
        await message.answer("❌ Введи числа. Пример: /setlimits 1000 50000")

@dp.message(Command("limits"))
async def show_limits_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer(
        f"📊 Текущие лимиты:\n\n"
        f"💰 Минимальная сумма: {get_min_limit()} ₽\n"
        f"💰 Максимальная сумма: {get_max_limit()} ₽"
    )

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
            INSERT INTO orders (user_id, username, full_name, type, coin, amount, crypto_amount, status, reject_reason, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (uid, call.from_user.username, call.from_user.full_name, action, coin, rub, crypto, 'pending', '', int(time.time()), int(time.time())))
        order_id_db = cur.lastrowid
        conn.commit()
        
        del pending_orders[order_id]
        
        await call.message.edit_text(
            get_text(uid, 'order_created', id=order_id_db, type=type_text, coin=coin, amount=f"{rub:,.0f}", crypto=crypto),
            reply_markup=main_menu(uid)
        )
        
        username = f"@{call.from_user.username}" if call.from_user.username else "no username"
        await bot.send_message(
            ADMIN_ID,
            f"🆕 НОВАЯ ЗАЯВКА #{order_id_db}\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Сумма: {rub:,.0f} ₽\n"
            f"🪙 Крипта: {crypto:.8f} {coin}\n"
            f"👤 Пользователь: {call.from_user.full_name}\n"
            f"{username}\n"
            f"🆔 ID: {uid}\n"
            f"📊 Статус: Ожидает",
            reply_markup=order_buttons(order_id_db, 'pending')
        )
        await call.answer()
        return
    
    if data.startswith("confirm_no_"):
        order_id = int(data.split("_")[2])
        if order_id in pending_orders:
            del pending_orders[order_id]
        await call.message.edit_text(get_text(uid, 'order_cancelled'), reply_markup=main_menu(uid))
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
        await call.message.answer(get_text(uid, 'lang_selected'))
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
        await call.message.answer(get_text(uid, 'loading_rates'))
        
        rates = await get_crypto_rates()
        if rates is None:
            await call.message.answer("❌ Не удалось загрузить курсы. Попробуйте позже.")
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
                f"📊 Рыночные курсы:\n"
                f"└ USDT: {market_usdt:.2f} ₽\n"
                f"└ BTC: {market_btc:,.0f} ₽\n"
                f"└ ETH: {market_eth:,.0f} ₽\n\n"
                f"📈 Покупка через MOSS PAY (+10%):\n"
                f"└ USDT: {buy_usdt:.2f} ₽\n"
                f"└ BTC: {buy_btc:,.0f} ₽\n"
                f"└ ETH: {buy_eth:,.0f} ₽\n\n"
                f"📉 Продажа через MOSS PAY (-2%):\n"
                f"└ USDT: {sell_usdt:.2f} ₽\n"
                f"└ BTC: {sell_btc:,.0f} ₽\n"
                f"└ ETH: {sell_eth:,.0f} ₽\n\n"
                f"⚙️ Комиссия MOSS PAY: покупка +10%, продажа -2%"
            )
        else:
            text = (
                f"📊 Market rates:\n"
                f"└ USDT: {market_usdt:.2f} RUB\n"
                f"└ BTC: {market_btc:,.0f} RUB\n"
                f"└ ETH: {market_eth:,.0f} RUB\n\n"
                f"📈 Buy via MOSS PAY (+10%):\n"
                f"└ USDT: {buy_usdt:.2f} RUB\n"
                f"└ BTC: {buy_btc:,.0f} RUB\n"
                f"└ ETH: {buy_eth:,.0f} RUB\n\n"
                f"📉 Sell via MOSS PAY (-2%):\n"
                f"└ USDT: {sell_usdt:.2f} RUB\n"
                f"└ BTC: {sell_btc:,.0f} RUB\n"
                f"└ ETH: {sell_eth:,.0f} RUB\n\n"
                f"⚙️ MOSS PAY fee: buy +10%, sell -2%"
            )
        
        await call.message.answer(text, reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # История заявок
    if data == "history":
        cur.execute('SELECT id, type, coin, amount, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (uid,))
        orders = cur.fetchall()
        
        if not orders:
            await call.message.answer(get_text(uid, 'no_orders'), reply_markup=back_menu(uid))
            await call.answer()
            return
        
        text = get_text(uid, 'orders_title')
        for order in orders:
            order_id, o_type, coin, amount, status, created_at = order
            type_text = "Покупка" if o_type == "buy" else "Продажа"
            status_emoji = get_status_emoji(status)
            status_text = get_status_text(status, get_lang(uid))
            date = time.strftime('%d.%m %H:%M', time.localtime(created_at))
            text += f"{status_emoji} #{order_id} | {type_text} {coin}\n   💰 {amount:,.0f} ₽ | {status_text} | {date}\n\n"
        
        await call.message.answer(text, reply_markup=back_menu(uid))
        await call.answer()
        return
    
    # Помощь
    if data == "help":
        await call.message.answer(get_text(uid, 'help_text'), reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Контакты
    if data == "contacts":
        await call.message.answer(get_text(uid, 'contacts_text'), reply_markup=contacts_menu(uid))
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
            await call.message.answer(get_text(ADMIN_ID, 'no_orders'))
        else:
            for order in orders:
                order_id, o_type, coin, amount, status = order
                type_text = "Покупка" if o_type == "buy" else "Продажа"
                status_emoji = get_status_emoji(status)
                status_text = get_status_text(status, 'ru')
                text = f"{status_emoji} Заявка #{order_id}\n\n{type_text} {coin}\n💰 {amount:,.0f} ₽\n📊 Статус: {status_text}"
                await call.message.answer(text, reply_markup=order_buttons(order_id, status))
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
            f"📊 Статистика:\n\n"
            f"🟡 Ожидают: {pending_orders_count or 0} (на {pending_sum or 0:,.0f} ₽)\n"
            f"🔵 В обработке: {processing_orders or 0} (на {processing_sum or 0:,.0f} ₽)\n"
            f"🟢 Выполнено: {completed_orders or 0} (на {completed_sum or 0:,.0f} ₽)\n\n"
            f"📦 Всего заявок: {total_orders or 0}\n"
            f"💵 Общая сумма: {total_sum or 0:,.0f} ₽"
        )
        await call.message.answer(text, reply_markup=admin_menu())
        await call.answer()
        return
    
    # Обработка принятия/отклонения заявки
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
    
    # Отклонение заявки с выбором причины
    if data.startswith("reject_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[1])
        await call.message.answer(f"❌ Выберите причину отклонения заявки #{order_id}:", reply_markup=reject_reason_menu(order_id))
        await call.answer()
        return
    
    # Обработка выбранной причины отклонения
    if data.startswith("reject_reason_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        parts = data.split("_")
        order_id = int(parts[2])
        reason_code = parts[3]
        
        reasons = {
            'insufficient_funds': 'Недостаточно средств на счету',
            'wrong_rate': 'Неверный курс обмена',
            'no_answer': 'Пользователь не ответил на связь',
            'other': 'Другая причина (свяжитесь с оператором)'
        }
        
        reject_reason = reasons.get(reason_code, 'Причина не указана')
        await update_order_status(order_id, 'rejected', reject_reason)
        await call.message.edit_text(f"❌ Заявка #{order_id} отклонена!\n📝 Причина: {reject_reason}", reply_markup=None)
        await call.answer()
        return
    
    if data.startswith("back_to_order_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[3])
        cur.execute('SELECT type, coin, amount, status FROM orders WHERE id = ?', (order_id,))
        order = cur.fetchone()
        if order:
            o_type, coin, amount, status = order
            type_text = "Покупка" if o_type == "buy" else "Продажа"
            status_emoji = get_status_emoji(status)
            status_text = get_status_text(status, 'ru')
            text = f"{status_emoji} Заявка #{order_id}\n\n{type_text} {coin}\n💰 {amount:,.0f} ₽\n📊 Статус: {status_text}"
            await call.message.edit_text(text, reply_markup=order_buttons(order_id, status))
        await call.answer()
        return
    
    # Выбор валюты для покупки
    if data.startswith("buy_"):
        coin = data.split("_")[1]
        rates = await get_crypto_rates()
        if rates is None:
            await call.message.answer("❌ Ошибка загрузки курсов. Попробуйте позже.")
            await call.answer()
            return
        
        pending_orders[uid] = {"action": "buy", "coin": coin, "rates": rates}
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        await call.message.answer(
            get_text(uid, 'select_buy', coin=coin, min=min_limit, max=max_limit)
        )
        await call.answer()
        return
    
    # Выбор валюты для продажи
    if data.startswith("sell_"):
        coin = data.split("_")[1]
        rates = await get_crypto_rates()
        if rates is None:
            await call.message.answer("❌ Ошибка загрузки курсов. Попробуйте позже.")
            await call.answer()
            return
        
        pending_orders[uid] = {"action": "sell", "coin": coin, "rates": rates}
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        await call.message.answer(
            get_text(uid, 'select_sell', coin=coin, min=min_limit, max=max_limit)
        )
        await call.answer()
        return

@dp.message()
async def handle_amount(message: types.Message):
    uid = message.from_user.id
    if uid not in pending_orders:
        return
    
    try:
        rub = float(message.text.replace(",", ".").replace(" ", ""))
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        
        if rub < min_limit or rub > max_limit:
            await message.answer(
                get_text(uid, 'limit_error', min=min_limit, max=max_limit)
            )
            return
        
        action = pending_orders[uid]["action"]
        coin = pending_orders[uid]["coin"]
        rates = pending_orders[uid]["rates"]
        
        crypto = calculate_crypto_amount(rub, coin, action, rates)
        
        order_id = int(time.time() * 1000)
        pending_orders[order_id] = (action, coin, rub, crypto)
        del pending_orders[uid]
        
        await message.answer(
            get_text(uid, 'confirm_order', amount=f"{rub:,.0f}", crypto=crypto, coin=coin, min=min_limit, max=max_limit),
            reply_markup=confirm_menu(order_id)
        )
        
    except ValueError:
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        await message.answer(
            get_text(uid, 'limit_error', min=min_limit, max=max_limit)
        )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook удален")
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
