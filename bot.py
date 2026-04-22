import asyncio
import sqlite3
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from flask import Flask
from threading import Thread
import os
import random
import string

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8177854087

# Настройки по умолчанию
DEFAULT_MIN_LIMIT = 1000
DEFAULT_MAX_LIMIT = 50000
REFERRAL_BONUS_PERCENT = 1

# Режим техработ (глобальная переменная)
TECH_MODE = False
TECH_MESSAGE = ""

# Курсы для разных валют (в рублях)
DEFAULT_RATES = {
    'RUB': {'usdt': 91.50, 'btc': 5500000, 'eth': 220000},
    'BYN': {'usdt': 28.50, 'btc': 1715000, 'eth': 68600},
    'UAH': {'usdt': 37.50, 'btc': 2255000, 'eth': 90200},
    'KZT': {'usdt': 450.00, 'btc': 27000000, 'eth': 1080000},
    'TRY': {'usdt': 30.00, 'btc': 1800000, 'eth': 72000},
    'AMD': {'usdt': 390.00, 'btc': 23400000, 'eth': 936000}
}

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

# ========== КЛАВИАТУРЫ ==========
def reply_menu(user_id):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Контакты"), KeyboardButton(text="💱 Сменить валюту")],
            [KeyboardButton(text="👥 Реферальная система"), KeyboardButton(text="🌐 Сменить язык")]
        ],
        resize_keyboard=True
    )

def main_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Купить", callback_data="buy")],
        [InlineKeyboardButton(text="🔴 Продать", callback_data="sell")],
        [InlineKeyboardButton(text="📊 Курсы", callback_data="rates")],
        [InlineKeyboardButton(text="📜 История заявок", callback_data="history")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

# ========== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ТЕХРЕЖИМА ==========
async def check_tech_mode(message=None, call=None):
    """Проверяет, включён ли режим техработ, и отправляет сообщение пользователю"""
    global TECH_MODE, TECH_MESSAGE
    
    if TECH_MODE:
        user_id = None
        if message:
            user_id = message.from_user.id
        elif call:
            user_id = call.from_user.id
        
        if user_id and user_id != ADMIN_ID:
            lang = get_lang(user_id)
            if lang == 'ru':
                text = f"🔧 *Технические работы*\n\n{TECH_MESSAGE}\n\n⏰ Пожалуйста, повторите попытку позже.\n\nПриносим извинения за временные неудобства!"
            else:
                text = f"🔧 *Technical maintenance*\n\n{TECH_MESSAGE}\n\n⏰ Please try again later.\n\nWe apologize for the temporary inconvenience!"
            
            if message:
                await message.answer(text, parse_mode="Markdown")
            elif call:
                await call.message.answer(text, parse_mode="Markdown")
            return True
    return False

# ========== ФУНКЦИЯ ДЛЯ РЕФЕРАЛЬНОЙ ССЫЛКИ ==========
def get_referral_link_sync(user_id):
    cur.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row[0]:
        return f"https://t.me/mosspay_bot?start=ref_{row[0]}"
    return None

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
        fiat_currency TEXT DEFAULT 'RUB',
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
        username TEXT,
        full_name TEXT,
        language TEXT DEFAULT 'ru',
        fiat_currency TEXT DEFAULT 'RUB',
        referrer_id INTEGER DEFAULT NULL,
        referral_code TEXT,
        created_at INTEGER,
        bonus_balance REAL DEFAULT 0,
        total_earned REAL DEFAULT 0
    )
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        created_at INTEGER,
        status TEXT DEFAULT 'pending'
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
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_bonus_percent', ?)", (str(REFERRAL_BONUS_PERCENT),))

for currency, rates in DEFAULT_RATES.items():
    for crypto, rate in rates.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (f"{currency}_{crypto}", str(rate)))
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

def get_crypto_rate(currency, crypto):
    rate = get_setting(f"{currency}_{crypto}", 0)
    if rate == 0:
        return DEFAULT_RATES.get(currency, DEFAULT_RATES['RUB']).get(crypto, 0)
    return rate

def get_all_rates(currency):
    return {
        'usdt': get_crypto_rate(currency, 'usdt'),
        'btc': get_crypto_rate(currency, 'btc'),
        'eth': get_crypto_rate(currency, 'eth')
    }

def set_crypto_rate(currency, crypto, value):
    set_setting(f"{currency}_{crypto}", value)

def set_min_limit(value):
    set_setting('min_limit', value)

def set_max_limit(value):
    set_setting('max_limit', value)

def get_user_fiat(user_id):
    cur.execute("SELECT fiat_currency FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    return row[0] if row else 'RUB'

def set_user_fiat(user_id, currency):
    cur.execute("UPDATE users SET fiat_currency = ? WHERE user_id = ?", (currency, user_id))
    conn.commit()

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def add_bonus(user_id, amount, reason):
    cur.execute("UPDATE users SET bonus_balance = bonus_balance + ?, total_earned = total_earned + ? WHERE user_id = ?", (amount, amount, user_id))
    conn.commit()
    
    user_lang = get_lang(user_id)
    if user_lang == 'ru':
        asyncio.create_task(bot.send_message(user_id, f"🎉 *Бонус начислен!*\n\n💰 Сумма: {amount:,.2f} ₽\n📝 Причина: {reason}\n\nБонусы можно использовать для оплаты комиссии при обмене.", parse_mode="Markdown"))
    else:
        asyncio.create_task(bot.send_message(user_id, f"🎉 *Bonus added!*\n\n💰 Amount: {amount:,.2f} RUB\n📝 Reason: {reason}\n\nBonuses can be used to pay commission on exchanges.", parse_mode="Markdown"))

def get_referral_stats(user_id):
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    total_referrals = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status = 'completed'", (user_id,))
    active_referrals = cur.fetchone()[0] or 0
    
    cur.execute("SELECT total_earned FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    total_earned = row[0] if row else 0
    
    cur.execute("SELECT bonus_balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    current_balance = row[0] if row else 0
    
    return {
        'total': total_referrals,
        'active': active_referrals,
        'earned': total_earned,
        'balance': current_balance
    }

pending_orders = {}

# ========== ФУНКЦИЯ ДЛЯ КУРСОВ ==========
async def get_crypto_rates(user_id):
    currency = get_user_fiat(user_id)
    rates = get_all_rates(currency)
    
    commission_buy = 1.10
    commission_sell = 0.98
    
    return {
        'market': rates,
        'buy': {
            'usdt': rates['usdt'] * commission_buy,
            'btc': rates['btc'] * commission_buy,
            'eth': rates['eth'] * commission_buy
        },
        'sell': {
            'usdt': rates['usdt'] * commission_sell,
            'btc': rates['btc'] * commission_sell,
            'eth': rates['eth'] * commission_sell
        },
        'currency': currency
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
    return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')

def get_status_emoji(status):
    emojis = {
        'pending': '🟡',
        'processing': '🔵',
        'completed': '🟢',
        'rejected': '🔴',
        'cancelled': '⚫'
    }
    return emojis.get(status, '⚪')

def get_status_text(status, lang='ru'):
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

def get_currency_symbol(currency):
    symbols = {
        'RUB': '₽',
        'BYN': 'Br',
        'UAH': '₴',
        'KZT': '₸',
        'TRY': '₺',
        'AMD': '֏'
    }
    return symbols.get(currency, currency)

def user_notification_buttons(order_id, lang='ru'):
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

def back_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
    ])

def fiat_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 RUB", callback_data="fiat_RUB"),
         InlineKeyboardButton(text="🇧🇾 BYN", callback_data="fiat_BYN")],
        [InlineKeyboardButton(text="🇺🇦 UAH", callback_data="fiat_UAH"),
         InlineKeyboardButton(text="🇰🇿 KZT", callback_data="fiat_KZT")],
        [InlineKeyboardButton(text="🇹🇷 TRY", callback_data="fiat_TRY"),
         InlineKeyboardButton(text="🇦🇲 AMD", callback_data="fiat_AMD")]
    ])

def reject_reason_menu(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Недостаточно средств", callback_data=f"reject_reason_{order_id}_insufficient_funds")],
        [InlineKeyboardButton(text="❌ Неверный курс", callback_data=f"reject_reason_{order_id}_wrong_rate")],
        [InlineKeyboardButton(text="❌ Пользователь не ответил", callback_data=f"reject_reason_{order_id}_no_answer")],
        [InlineKeyboardButton(text="❌ Другая причина", callback_data=f"reject_reason_{order_id}_other")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_order_{order_id}")]
    ])

async def update_order_status(order_id, new_status, reject_reason=None):
    cur.execute('SELECT user_id, type, coin, fiat_currency, amount, crypto_amount FROM orders WHERE id = ?', (order_id,))
    order = cur.fetchone()
    if not order:
        return
    
    user_id_db, o_type, coin, fiat_currency, amount, crypto = order
    
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
    currency_symbol = get_currency_symbol(fiat_currency)
    
    if new_status == 'rejected' and reject_reason:
        reason_text = f"\n📝 Причина: {reject_reason}"
    else:
        reason_text = ""
    
    if user_lang == 'ru':
        notification = (
            f"{status_emoji} *Статус заявки #{order_id} обновлён*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Сумма: {amount:,.0f} {currency_symbol}\n"
            f"🪙 Крипта: {crypto:.8f} {coin}\n"
            f"📊 Новый статус: {status_text}{reason_text}\n"
            f"🕐 Время: {updated_time}"
        )
    else:
        notification = (
            f"{status_emoji} *Order #{order_id} status updated*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Amount: {amount:,.0f} {currency_symbol}\n"
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
    
    if new_status == 'completed':
        bonus_percent = get_setting('referral_bonus_percent', 1)
        bonus = amount * (bonus_percent / 100)
        
        if bonus > 0:
            cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id_db,))
            row = cur.fetchone()
            if row and row[0]:
                referrer_id = row[0]
                add_bonus(referrer_id, bonus, f"Заявка #{order_id} от реферала ({bonus_percent}%)")
                cur.execute("UPDATE referrals SET status = 'completed' WHERE referred_id = ?", (user_id_db,))
                conn.commit()

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
        'change_currency': "💱 Сменить валюту",
        'referral_btn': "👥 Реферальная система",
        'change_lang_btn': "🌐 Сменить язык",
        'back_btn': "🔙 Назад",
        'select_fiat': "💱 *Выберите валюту:*",
        'select_buy': "💰 Введи сумму в {currency} для покупки {coin}:\n📊 Лимиты: {min} - {max} {symbol}",
        'select_sell': "💰 Введи сумму в {currency} для продажи {coin}:\n📊 Лимиты: {min} - {max} {symbol}",
        'limit_error': "❌ Сумма должна быть от {min} до {max} {symbol}",
        'confirm_order': "💰 Вы ввели: {amount} {symbol}\n🪙 Вы получите: {crypto:.8f} {coin}\n📊 Лимиты: {min} - {max} {symbol}\n\n✅ Подтвердить заявку?",
        'order_created': "✅ Заявка #{id} создана!\n\n📌 {type} {coin}\n💰 Сумма: {amount} {symbol}\n🪙 Крипта: {crypto:.8f} {coin}\n📊 Статус: Ожидает обработки\n\n📞 Оператор свяжется с вами",
        'order_cancelled': "❌ Заявка отменена",
        'no_orders': "📭 Нет заявок",
        'orders_title': "📋 Ваши заявки:\n\n",
        'type_buy': "Покупка",
        'type_sell': "Продажа",
        'lang_selected': "✅ Язык: Русский",
        'select_lang': "🌐 Выбери язык:",
        'currency_changed': "✅ Валюта изменена на {currency}",
        'help_text': "❓ *Как пользоваться обменником:*\n\n1️⃣ *Купить криптовалюту*\n   • Выбери валюту\n   • Выбери криптовалюту\n   • Введи сумму\n   • Подтверди заявку\n\n2️⃣ *Продать криптовалюту*\n   • Выбери валюту\n   • Выбери криптовалюту\n   • Введи сумму\n   • Подтверди заявку\n\n3️⃣ *Курсы*\n   • Актуальные курсы с наценкой 10% (покупка) и -2% (продажа)\n\n4️⃣ *Контакты*\n   • Связь с оператором: @shakakobmen\n\n⏰ *Время работы:* 10:00 – 22:00 МСК\n\n💎 *Бонусы:* приглашай друзей и получай 1% от их заявок",
        'contacts_text': "📞 *Связь с оператором:*\n\n• Telegram: @shakakobmen\n• WhatsApp: +7 999 123-45-67\n• Email: support@crypto-exchange.ru\n\n⏰ *Время ответа:* обычно в течение 5 минут",
        'admin_panel': "🔧 Панель администратора\n\nВыберите действие:",
        'admin_orders_btn': "📋 Список заявок",
        'admin_stats_btn': "📊 Статистика",
        'loading_rates': "🔄 Загружаю актуальные курсы...",
        'confirm_yes': "✅ Да, подтверждаю",
        'confirm_no': "❌ Нет, отменить",
        'clear_db_success': "✅ База данных полностью очищена!\n\n- Удалены все пользователи\n- Удалены все заявки\n- Удалены все реферальные связи",
        'referral_info': "👥 *Реферальная система*\n\nПриглашай друзей и получай бонусы!\n\n🔗 *Твоя ссылка:*\n`{link}`\n\n📊 *Твоя статистика:*\n• 👥 Приглашено друзей: {total}\n• ✅ Активных рефералов: {active}\n• 💰 Всего заработано: {earned:.2f} ₽\n• 💎 Текущий баланс: {balance:.2f} ₽\n\n💎 *Как это работает:*\n• Отправь ссылку другу\n• Друг переходит по ссылке и нажимает Start\n• При выполнении заявки другом ты получаешь {percent}% бонус\n\n📋 Нажми «Скопировать ссылку», затем отправь её другу.",
        'no_referral_code': "❌ Не удалось создать реферальную ссылку",
        'tech_on_success': "🔧 *Режим технических работ ВКЛЮЧЁН*\n\nСообщение отправлено всем пользователям.\n\n📝 Текст: {message}\n\n⚠️ Теперь пользователи не смогут создавать заявки до отключения режима.\n\nДля отключения используй `/tech_off`"
    },
    'en': {
        'welcome': "🏦 Welcome to MOSS PAY Crypto Exchanger",
        'buy_btn': "🟢 Buy",
        'sell_btn': "🔴 Sell",
        'rates_btn': "📊 Rates",
        'history_btn': "📜 Order history",
        'help_btn': "❓ Help",
        'contacts_btn': "📞 Contacts",
        'change_currency': "💱 Change currency",
        'referral_btn': "👥 Referral system",
        'change_lang_btn': "🌐 Change language",
        'back_btn': "🔙 Back",
        'select_fiat': "💱 *Select currency:*",
        'select_buy': "💰 Enter amount in {currency} to buy {coin}:\n📊 Limits: {min} - {max} {symbol}",
        'select_sell': "💰 Enter amount in {currency} to sell {coin}:\n📊 Limits: {min} - {max} {symbol}",
        'limit_error': "❌ Amount must be between {min} and {max} {symbol}",
        'confirm_order': "💰 You entered: {amount} {symbol}\n🪙 You will receive: {crypto:.8f} {coin}\n📊 Limits: {min} - {max} {symbol}\n\n✅ Confirm order?",
        'order_created': "✅ Order #{id} created!\n\n📌 {type} {coin}\n💰 Amount: {amount} {symbol}\n🪙 Crypto: {crypto:.8f} {coin}\n📊 Status: Pending\n\n📞 Operator will contact you",
        'order_cancelled': "❌ Order cancelled",
        'no_orders': "📭 No orders",
        'orders_title': "📋 Your orders:\n\n",
        'type_buy': "Purchase",
        'type_sell': "Sale",
        'lang_selected': "✅ Language: English",
        'select_lang': "🌐 Choose language:",
        'currency_changed': "✅ Currency changed to {currency}",
        'help_text': "❓ *How to use:*\n\n1️⃣ *Buy crypto*\n   • Choose currency\n   • Choose crypto\n   • Enter amount\n   • Confirm order\n\n2️⃣ *Sell crypto*\n   • Choose currency\n   • Choose crypto\n   • Enter amount\n   • Confirm order\n\n3️⃣ *Rates*\n   • Current rates with 10% markup (buy) and -2% (sell)\n\n4️⃣ *Contacts*\n   • Contact operator: @shakakobmen\n\n⏰ *Working hours:* 10:00 – 22:00 MSK\n\n💎 *Bonuses:* invite friends and get 1% from their orders",
        'contacts_text': "📞 *Contact operator:*\n\n• Telegram: @shakakobmen\n• WhatsApp: +7 999 123-45-67\n• Email: support@crypto-exchange.ru\n\n⏰ *Response time:* usually within 5 minutes",
        'admin_panel': "🔧 Admin panel\n\nSelect action:",
        'admin_orders_btn': "📋 Orders list",
        'admin_stats_btn': "📊 Statistics",
        'loading_rates': "🔄 Loading current rates...",
        'confirm_yes': "✅ Yes, confirm",
        'confirm_no': "❌ No, cancel",
        'clear_db_success': "✅ Database cleared!\n\n- All users deleted\n- All orders deleted\n- All referral links deleted",
        'referral_info': "👥 *Referral system*\n\nInvite friends and get bonuses!\n\n🔗 *Your link:*\n`{link}`\n\n📊 *Your statistics:*\n• 👥 Friends invited: {total}\n• ✅ Active referrals: {active}\n• 💰 Total earned: {earned:.2f} RUB\n• 💎 Current balance: {balance:.2f} RUB\n\n💎 *How it works:*\n• Send link to friend\n• Friend follows link and presses Start\n• When friend completes an order, you get {percent}% bonus\n\n📋 Press «Copy link», then send it to your friend.",
        'no_referral_code': "❌ Failed to create referral link",
        'tech_on_success': "🔧 *Technical maintenance mode ENABLED*\n\nMessage sent to all users.\n\n📝 Text: {message}\n\n⚠️ Users cannot create orders until maintenance is disabled.\n\nUse `/tech_off` to disable"
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

def buy_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 USDT", callback_data="buy_USDT")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="buy_BTC")],
        [InlineKeyboardButton(text="💎 ETH", callback_data="buy_ETH")],
        [InlineKeyboardButton(text="💳 RapiraRUB", callback_data="buy_Rapira")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

def sell_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 USDT", callback_data="sell_USDT")],
        [InlineKeyboardButton(text="₿ BTC", callback_data="sell_BTC")],
        [InlineKeyboardButton(text="💎 ETH", callback_data="sell_ETH")],
        [InlineKeyboardButton(text="💳 RapiraRUB", callback_data="sell_Rapira")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

def confirm_menu(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_yes_{order_id}"),
         InlineKeyboardButton(text="❌ Нет", callback_data=f"confirm_no_{order_id}")]
    ])

def order_buttons(order_id, status):
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

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список заявок", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

# ========== КОМАНДА ДЛЯ ВКЛЮЧЕНИЯ ТЕХРАБОТ ==========
@dp.message(Command("tech_on"))
async def tech_on(message: types.Message):
    global TECH_MODE, TECH_MESSAGE
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    # Получаем текст сообщения после команды
    tech_text = message.text.replace("/tech_on", "").strip()
    if not tech_text:
        await message.answer("❌ *Неверный формат*\n\nИспользуй: `/tech_on Текст сообщения`\n\nПример: `/tech_on Обновление базы данных, бот вернётся через 15 минут`", parse_mode="Markdown")
        return
    
    TECH_MODE = True
    TECH_MESSAGE = tech_text
    
    # Получаем всех пользователей
    cur.execute("SELECT user_id, language FROM users")
    users = cur.fetchall()
    
    sent_count = 0
    error_count = 0
    
    for user_id, lang in users:
        try:
            if lang == 'ru':
                await bot.send_message(user_id, f"🔧 *Технические работы*\n\n{tech_text}\n\n⏰ Бот временно недоступен. Пожалуйста, повторите попытку позже.\n\nПриносим извинения за временные неудобства!", parse_mode="Markdown")
            else:
                await bot.send_message(user_id, f"🔧 *Technical maintenance*\n\n{tech_text}\n\n⏰ Bot is temporarily unavailable. Please try again later.\n\nWe apologize for the temporary inconvenience!", parse_mode="Markdown")
            sent_count += 1
        except:
            error_count += 1
        await asyncio.sleep(0.05)
    
    await message.answer(
        get_text(ADMIN_ID, 'tech_on_success', message=tech_text),
        parse_mode="Markdown"
    )

# ========== КОМАНДА ДЛЯ ВЫКЛЮЧЕНИЯ ТЕХРАБОТ ==========
@dp.message(Command("tech_off"))
async def tech_off(message: types.Message):
    global TECH_MODE, TECH_MESSAGE
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not TECH_MODE:
        await message.answer("❌ Режим технических работ и так выключен")
        return
    
    TECH_MODE = False
    TECH_MESSAGE = ""
    
    await message.answer("✅ *Режим технических работ ВЫКЛЮЧЕН*\n\nБот снова доступен для пользователей.", parse_mode="Markdown")

@dp.message(Command("start"))
async def start(message: types.Message):
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    uid = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    referrer_id = None
    if message.text and ' ' in message.text:
        parts = message.text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            ref_code = parts[1][4:]
            cur.execute("SELECT user_id FROM users WHERE referral_code = ?", (ref_code,))
            row = cur.fetchone()
            if row:
                referrer_id = row[0]
    
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not cur.fetchone():
        referral_code = generate_referral_code()
        cur.execute('''
            INSERT INTO users (user_id, username, full_name, language, fiat_currency, referrer_id, referral_code, created_at, bonus_balance, total_earned)
            VALUES (?, ?, ?, 'ru', 'RUB', ?, ?, ?, 0, 0)
        ''', (uid, username, full_name, referrer_id, referral_code, int(time.time())))
        
        if referrer_id:
            cur.execute('''
                INSERT INTO referrals (referrer_id, referred_id, created_at, status)
                VALUES (?, ?, ?, 'pending')
            ''', (referrer_id, uid, int(time.time())))
        
        conn.commit()
    
    photo_url = "https://raw.githubusercontent.com/alexandr956/crypto-bot/main/welcome.jpg"
    lang = get_lang(uid)
    
    if lang == 'ru':
        welcome_text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"🏦 Добро пожаловать в КриптоОбменник MOSS PAY\n\n"
            f"💎 *Почему выбирают нас:*\n"
            f"• 🚀 Мгновенные заявки\n"
            f"• 🔒 Безопасные сделки\n"
            f"• 💬 Поддержка 24/7\n"
            f"• 💰 Лучшие курсы\n"
            f"• 🔑 Обмен без KYC\n\n"
            f"👇 *Выберите действие в меню ниже*"
        )
    else:
        welcome_text = (
            f"👋 Hi {message.from_user.first_name}!\n\n"
            f"🏦 Welcome to MOSS PAY Crypto Exchanger\n\n"
            f"💎 *Why choose us:*\n"
            f"• 🚀 Instant orders\n"
            f"• 🔒 Secure transactions\n"
            f"• 💬 24/7 support\n"
            f"• 💰 Best rates\n"
            f"• 🔑 No KYC\n\n"
            f"👇 *Select an action below*"
        )
    
    try:
        await message.answer_photo(photo_url, caption=welcome_text, reply_markup=main_menu(uid))
        await message.answer("🔽 *Дополнительные опции:*", parse_mode="Markdown", reply_markup=reply_menu(uid))
    except:
        await message.answer(welcome_text, reply_markup=main_menu(uid))
        await message.answer("🔽 *Additional options:*", parse_mode="Markdown", reply_markup=reply_menu(uid))

@dp.message(Command("clear_db"))
async def clear_db(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    try:
        cur.execute("DELETE FROM users")
        cur.execute("DELETE FROM orders")
        cur.execute("DELETE FROM referrals")
        conn.commit()
        await message.answer(get_text(ADMIN_ID, 'clear_db_success'), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    await message.answer(get_text(ADMIN_ID, 'admin_panel'), reply_markup=admin_menu())

# ========== ОБРАБОТКА REPLY-КНОПОК ==========
@dp.message(F.text == "📞 Контакты")
async def contacts_reply(message: types.Message):
    uid = message.from_user.id
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    await message.answer(get_text(uid, 'contacts_text'), parse_mode="Markdown", reply_markup=reply_menu(uid))

@dp.message(F.text == "💱 Сменить валюту")
async def change_currency_reply(message: types.Message):
    uid = message.from_user.id
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    await message.answer(get_text(uid, 'select_fiat'), parse_mode="Markdown", reply_markup=fiat_menu())

@dp.message(F.text == "👥 Реферальная система")
async def referral_reply(message: types.Message):
    uid = message.from_user.id
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    referral_link = get_referral_link_sync(uid)
    if referral_link:
        stats = get_referral_stats(uid)
        bonus_percent = get_setting('referral_bonus_percent', 1)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_link_{uid}")],
            [InlineKeyboardButton(text="📤 Поделиться", url=f"https://t.me/share/url?url={referral_link}&text=Привет! Присоединяйся к обменнику MOSS PAY, получи бонус!")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main")]
        ])
        
        await message.answer(
            get_text(uid, 'referral_info', link=referral_link, total=stats['total'], active=stats['active'], earned=stats['earned'], balance=stats['balance'], percent=bonus_percent),
            parse_mode="Markdown",
            reply_markup=kb
        )
    else:
        await message.answer(get_text(uid, 'no_referral_code'), reply_markup=reply_menu(uid))

@dp.message(F.text == "🌐 Сменить язык")
async def change_lang_reply(message: types.Message):
    uid = message.from_user.id
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    await message.answer(get_text(uid, 'select_lang'), parse_mode="Markdown", reply_markup=lang_menu())

@dp.message(Command("setrates"))
async def set_rates(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 4:
            await message.answer(
                f"❌ Неверный формат\n\n"
                f"Используй: /setrates RUB usdt 92.50\n"
                f"/setrates RUB btc 5600000\n"
                f"/setrates RUB eth 230000\n\n"
                f"Доступные валюты: RUB, BYN, UAH, KZT, TRY, AMD\n"
                f"Доступные криптовалюты: usdt, btc, eth"
            )
            return
        
        currency = parts[1].upper()
        crypto = parts[2].lower()
        new_rate = float(parts[3])
        
        if new_rate <= 0:
            await message.answer("❌ Курс должен быть положительным числом")
            return
        
        if currency not in ['RUB', 'BYN', 'UAH', 'KZT', 'TRY', 'AMD']:
            await message.answer("❌ Доступные валюты: RUB, BYN, UAH, KZT, TRY, AMD")
            return
        
        if crypto not in ['usdt', 'btc', 'eth']:
            await message.answer("❌ Доступные криптовалюты: usdt, btc, eth")
            return
        
        set_crypto_rate(currency, crypto, new_rate)
        
        await message.answer(
            f"✅ Курс обновлён!\n\n"
            f"📊 {currency} → {crypto.upper()}: {new_rate:,.2f}"
        )
        
    except ValueError:
        await message.answer("❌ Введи число. Пример: /setrates RUB usdt 92.50")

@dp.message(Command("rates"))
async def show_rates_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    text = "📊 *Текущие курсы:*\n\n"
    for currency in ['RUB', 'BYN', 'UAH', 'KZT', 'TRY', 'AMD']:
        rates = get_all_rates(currency)
        text += f"*{currency}*\n"
        text += f"└ USDT: {rates['usdt']:.2f}\n"
        text += f"└ BTC: {rates['btc']:,.0f}\n"
        text += f"└ ETH: {rates['eth']:,.0f}\n\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("setlimits"))
async def set_limits(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                f"❌ Неверный формат\n\n"
                f"Используй: /setlimits 1000 50000\n"
                f"Текущие лимиты: {get_min_limit()} - {get_max_limit()}"
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
        
        await message.answer(f"✅ Лимиты обновлены!\n\n📊 Новые лимиты: {new_min} - {new_max}")
        
    except ValueError:
        await message.answer("❌ Введи числа. Пример: /setlimits 1000 50000")

@dp.message(Command("limits"))
async def show_limits_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    await message.answer(
        f"📊 Текущие лимиты:\n\n"
        f"💰 Минимальная сумма: {get_min_limit()}\n"
        f"💰 Максимальная сумма: {get_max_limit()}"
    )

@dp.callback_query()
async def handle_callback(call: types.CallbackQuery):
    uid = call.from_user.id
    data = call.data
    
    # Проверяем режим техработ (админ может игнорировать)
    if uid != ADMIN_ID:
        if await check_tech_mode(call=call):
            return
    
    # Копирование реферальной ссылки
    if data.startswith("copy_link_"):
        user_id = int(data.split("_")[2])
        if user_id == uid:
            referral_link = get_referral_link_sync(uid)
            if referral_link:
                await call.answer(f"Ссылка скопирована: {referral_link}", show_alert=True)
                await call.message.answer(f"🔗 Твоя реферальная ссылка:\n`{referral_link}`", parse_mode="Markdown")
            else:
                await call.answer("Ошибка: ссылка не найдена", show_alert=True)
        else:
            await call.answer("Доступ запрещен", show_alert=True)
        return
    
    # Смена языка
    if data.startswith("lang_"):
        lang = 'ru' if data == "lang_ru" else 'en'
        cur.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))
        conn.commit()
        await call.message.edit_reply_markup(reply_markup=main_menu(uid))
        await call.message.answer(get_text(uid, 'lang_selected'))
        await call.answer()
        return
    
    # Выбор фиатной валюты
    if data.startswith("fiat_"):
        currency = data.split("_")[1]
        set_user_fiat(uid, currency)
        await call.message.answer(get_text(uid, 'currency_changed', currency=currency))
        await call.message.answer(get_text(uid, 'welcome'), reply_markup=main_menu(uid))
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
        
        rates = await get_crypto_rates(uid)
        if rates is None:
            await call.message.answer("❌ Не удалось загрузить курсы. Попробуйте позже.")
            await call.answer()
            return

        currency = rates['currency']
        currency_symbol = get_currency_symbol(currency)
        market = rates['market']
        buy = rates['buy']
        sell = rates['sell']

        if get_lang(uid) == 'ru':
            text = (
                f"📊 *Рыночные курсы ({currency}):*\n"
                f"└ USDT: {market['usdt']:.2f} {currency_symbol}\n"
                f"└ BTC: {market['btc']:,.0f} {currency_symbol}\n"
                f"└ ETH: {market['eth']:,.0f} {currency_symbol}\n\n"
                f"📈 *Покупка через MOSS PAY (+10%):*\n"
                f"└ USDT: {buy['usdt']:.2f} {currency_symbol}\n"
                f"└ BTC: {buy['btc']:,.0f} {currency_symbol}\n"
                f"└ ETH: {buy['eth']:,.0f} {currency_symbol}\n\n"
                f"📉 *Продажа через MOSS PAY (-2%):*\n"
                f"└ USDT: {sell['usdt']:.2f} {currency_symbol}\n"
                f"└ BTC: {sell['btc']:,.0f} {currency_symbol}\n"
                f"└ ETH: {sell['eth']:,.0f} {currency_symbol}\n\n"
                f"⚙️ Комиссия MOSS PAY: покупка +10%, продажа -2%"
            )
        else:
            text = (
                f"📊 *Market rates ({currency}):*\n"
                f"└ USDT: {market['usdt']:.2f} {currency_symbol}\n"
                f"└ BTC: {market['btc']:,.0f} {currency_symbol}\n"
                f"└ ETH: {market['eth']:,.0f} {currency_symbol}\n\n"
                f"📈 *Buy via MOSS PAY (+10%):*\n"
                f"└ USDT: {buy['usdt']:.2f} {currency_symbol}\n"
                f"└ BTC: {buy['btc']:,.0f} {currency_symbol}\n"
                f"└ ETH: {buy['eth']:,.0f} {currency_symbol}\n\n"
                f"📉 *Sell via MOSS PAY (-2%):*\n"
                f"└ USDT: {sell['usdt']:.2f} {currency_symbol}\n"
                f"└ BTC: {sell['btc']:,.0f} {currency_symbol}\n"
                f"└ ETH: {sell['eth']:,.0f} {currency_symbol}\n\n"
                f"⚙️ MOSS PAY fee: buy +10%, sell -2%"
            )
        
        await call.message.answer(text, parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # История заявок
    if data == "history":
        cur.execute('SELECT id, type, coin, fiat_currency, amount, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 10', (uid,))
        orders = cur.fetchall()
        
        if not orders:
            await call.message.answer(get_text(uid, 'no_orders'), reply_markup=main_menu(uid))
            await call.answer()
            return
        
        text = get_text(uid, 'orders_title')
        for order in orders:
            order_id, o_type, coin, fiat_currency, amount, status, created_at = order
            type_text = "Покупка" if o_type == "buy" else "Продажа"
            status_emoji = get_status_emoji(status)
            status_text = get_status_text(status, get_lang(uid))
            currency_symbol = get_currency_symbol(fiat_currency)
            date = time.strftime('%d.%m %H:%M', time.localtime(created_at))
            text += f"{status_emoji} #{order_id} | {type_text} {coin}\n   💰 {amount:,.0f} {currency_symbol} | {status_text} | {date}\n\n"
        
        await call.message.answer(text, parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Помощь
    if data == "help":
        await call.message.answer(get_text(uid, 'help_text'), parse_mode="Markdown", reply_markup=main_menu(uid))
        await call.answer()
        return
    
    # Админ панель - список заявок
    if data == "admin_orders":
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        cur.execute('SELECT id, type, coin, fiat_currency, amount, status FROM orders WHERE status != "completed" ORDER BY created_at DESC')
        orders = cur.fetchall()
        if not orders:
            await call.message.answer(get_text(ADMIN_ID, 'no_orders'))
        else:
            for order in orders:
                order_id, o_type, coin, fiat_currency, amount, status = order
                type_text = "Покупка" if o_type == "buy" else "Продажа"
                status_emoji = get_status_emoji(status)
                status_text = get_status_text(status, 'ru')
                currency_symbol = get_currency_symbol(fiat_currency)
                text = f"{status_emoji} Заявка #{order_id}\n\n{type_text} {coin}\n💰 {amount:,.0f} {currency_symbol}\n📊 Статус: {status_text}"
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
            f"🟡 Ожидают: {pending_orders_count or 0} (на {pending_sum or 0:,.0f})\n"
            f"🔵 В обработке: {processing_orders or 0} (на {processing_sum or 0:,.0f})\n"
            f"🟢 Выполнено: {completed_orders or 0} (на {completed_sum or 0:,.0f})\n\n"
            f"📦 Всего заявок: {total_orders or 0}\n"
            f"💵 Общая сумма: {total_sum or 0:,.0f}"
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
    
    # Отклонение заявки
    if data.startswith("reject_") and not data.startswith("reject_reason_"):
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
        cur.execute('SELECT type, coin, fiat_currency, amount, status FROM orders WHERE id = ?', (order_id,))
        order = cur.fetchone()
        if order:
            o_type, coin, fiat_currency, amount, status = order
            type_text = "Покупка" if o_type == "buy" else "Продажа"
            status_emoji = get_status_emoji(status)
            status_text = get_status_text(status, 'ru')
            currency_symbol = get_currency_symbol(fiat_currency)
            text = f"{status_emoji} Заявка #{order_id}\n\n{type_text} {coin}\n💰 {amount:,.0f} {currency_symbol}\n📊 Статус: {status_text}"
            await call.message.edit_text(text, reply_markup=order_buttons(order_id, status))
        await call.answer()
        return
    
    # Выбор валюты для покупки
    if data.startswith("buy_"):
        coin = data.split("_")[1]
        rates = await get_crypto_rates(uid)
        if rates is None:
            await call.message.answer("❌ Ошибка загрузки курсов. Попробуйте позже.")
            await call.answer()
            return
        
        pending_orders[uid] = {"action": "buy", "coin": coin, "rates": rates}
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        currency = rates['currency']
        currency_symbol = get_currency_symbol(currency)
        await call.message.answer(
            get_text(uid, 'select_buy', currency=currency, coin=coin, min=min_limit, max=max_limit, symbol=currency_symbol)
        )
        await call.answer()
        return
    
    # Выбор валюты для продажи
    if data.startswith("sell_"):
        coin = data.split("_")[1]
        rates = await get_crypto_rates(uid)
        if rates is None:
            await call.message.answer("❌ Ошибка загрузки курсов. Попробуйте позже.")
            await call.answer()
            return
        
        pending_orders[uid] = {"action": "sell", "coin": coin, "rates": rates}
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        currency = rates['currency']
        currency_symbol = get_currency_symbol(currency)
        await call.message.answer(
            get_text(uid, 'select_sell', currency=currency, coin=coin, min=min_limit, max=max_limit, symbol=currency_symbol)
        )
        await call.answer()
        return

@dp.message()
async def handle_amount(message: types.Message):
    uid = message.from_user.id
    
    # Проверяем режим техработ
    if await check_tech_mode(message=message):
        return
    
    if uid not in pending_orders:
        return
    
    try:
        rub = float(message.text.replace(",", ".").replace(" ", ""))
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        
        if rub < min_limit or rub > max_limit:
            await message.answer(
                get_text(uid, 'limit_error', min=min_limit, max=max_limit, symbol=get_currency_symbol(get_user_fiat(uid)))
            )
            return
        
        action = pending_orders[uid]["action"]
        coin = pending_orders[uid]["coin"]
        rates = pending_orders[uid]["rates"]
        
        crypto = calculate_crypto_amount(rub, coin, action, rates)
        
        order_id = int(time.time() * 1000)
        pending_orders[order_id] = (action, coin, rub, crypto)
        del pending_orders[uid]
        
        currency = rates['currency']
        currency_symbol = get_currency_symbol(currency)
        await message.answer(
            get_text(uid, 'confirm_order', amount=f"{rub:,.0f}", crypto=crypto, coin=coin, min=min_limit, max=max_limit, symbol=currency_symbol),
            reply_markup=confirm_menu(order_id)
        )
        
    except ValueError:
        min_limit = get_min_limit()
        max_limit = get_max_limit()
        await message.answer(
            get_text(uid, 'limit_error', min=min_limit, max=max_limit, symbol=get_currency_symbol(get_user_fiat(uid)))
        )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook удален")
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
