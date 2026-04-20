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

user_choice = {}

# ========== ТЕКСТЫ ==========
TEXTS = {
    'ru': {
        'welcome': "👋 *Привет, {name}!*\n\n🏦 *Добро пожаловать в MOSS PAY*\n\n💎 *Почему выбирают нас:*\n• 🚀 Мгновенные заявки\n• 🔒 Безопасные сделки\n• 💬 Поддержка 24/7\n• 💰 Лучшие курсы\n\n👇 *Выберите действие в меню ниже*",
        'buy_btn': "🟢 Купить",
        'sell_btn': "🔴 Продать",
        'rates_btn': "📊 Курсы",
        'help_btn': "❓ Помощь",
        'contacts_btn': "📞 Контакты",
        'back_btn': "🔙 Назад",
        'select_buy': "💰 *Введи сумму в рублях для покупки {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽",
        'select_sell': "💰 *Введи сумму в рублях для продажи {coin}:*\n📊 *Лимиты:* 1 000 - 50 000 ₽",
        'limit_error': "❌ *Сумма должна быть от 1 000 до 50 000 ₽*",
        'order_created': "✅ *Заявка #{id} создана!*\n\n{type} {coin} на {amount} ₽\n\n📞 *Оператор свяжется с вами*",
        'order_accepted': "✅ *Заявка #{id} принята!*\n\nОператор скоро свяжется с вами для уточнения деталей.",
        'order_rejected': "❌ *Заявка #{id} отклонена!*\n\nК сожалению, оператор не может провести эту сделку.\nВы можете создать новую заявку.",
        'no_orders': "📭 *Нет новых заявок*",
        'orders_title': "📋 *Новые заявки:*\n\n",
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
            "   • Оператор свяжется с тобой\n\n"
            "2️⃣ *Продать криптовалюту*\n"
            "   • Выбери валюту\n"
            "   • Введи сумму в рублях\n"
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
        ),
        'admin_panel': "🔧 *Панель администратора*\n\nВыберите действие:",
        'admin_orders_btn': "📋 Список заявок",
        'admin_stats_btn': "📊 Статистика"
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
        'order_created': "✅ *Order #{id} created!*\n\n{type} {coin} for {amount} RUB\n\n📞 *Operator will contact you*",
        'order_accepted': "✅ *Order #{id} accepted!*\n\nOperator will contact you shortly to discuss details.",
        'order_rejected': "❌ *Order #{id} rejected!*\n\nUnfortunately, the operator cannot process this transaction.\nYou can create a new order.",
        'no_orders': "📭 *No new orders*",
        'orders_title': "📋 *New orders:*\n\n",
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
            "   • Operator will contact you\n\n"
            "2️⃣ *Sell crypto*\n"
            "   • Choose currency\n"
            "   • Enter amount in RUB\n"
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
        ),
        'admin_panel': "🔧 *Admin panel*\n\nSelect action:",
        'admin_orders_btn': "📋 Orders list",
        'admin_stats_btn': "📊 Statistics"
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

def order_buttons(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{order_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    cur.execute("INSERT OR IGNORE INTO users (user_id, language) VALUES (?, 'ru')", (uid,))
    conn.commit()
    
    photo_url = "https://raw.githubusercontent.com/alexandr956/crypto-bot/main/welcome.jpg"
    
    # Получаем язык пользователя
    lang = get_lang(uid)
    
    # Текст приветствия с именем
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
    
    # Админ панель
    if data == "admin_orders":
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        cur.execute('SELECT id, type, coin, amount, status FROM orders WHERE status = "new" ORDER BY created_at DESC')
        orders = cur.fetchall()
        if not orders:
            await call.message.answer(get_text(ADMIN_ID, 'no_orders'), parse_mode="Markdown")
        else:
            for order in orders:
                order_id, o_type, coin, amount, status = order
                type_text = "Покупка" if o_type == "buy" else "Продажа"
                text = f"📋 *Заявка #{order_id}*\n\n{type_text} {coin}\n💰 {amount:,.0f} ₽\nСтатус: {status}"
                await call.message.answer(text, parse_mode="Markdown", reply_markup=order_buttons(order_id))
        await call.answer()
        return
    
    if data == "admin_stats":
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        cur.execute('SELECT COUNT(*), SUM(amount) FROM orders WHERE status = "new"')
        new_orders, new_sum = cur.fetchone()
        cur.execute('SELECT COUNT(*), SUM(amount) FROM orders')
        total_orders, total_sum = cur.fetchone()
        
        text = (
            "📊 *Статистика:*\n\n"
            f"🆕 Новых заявок: {new_orders or 0}\n"
            f"💰 Сумма новых: {new_sum or 0:,.0f} ₽\n\n"
            f"📦 Всего заявок: {total_orders or 0}\n"
            f"💵 Общая сумма: {total_sum or 0:,.0f} ₽"
        )
        await call.message.answer(text, parse_mode="Markdown", reply_markup=admin_menu())
        await call.answer()
        return
    
    # Обработка принятия/отклонения заявки
    if data.startswith("accept_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[1])
        cur.execute('SELECT user_id, type, coin, amount FROM orders WHERE id = ?', (order_id,))
        order = cur.fetchone()
        if order:
            user_id, o_type, coin, amount = order
            cur.execute('UPDATE orders SET status = "accepted" WHERE id = ?', (order_id,))
            conn.commit()
            
            # Уведомляем пользователя
            user_lang = get_lang(user_id)
            if user_lang == 'ru':
                await bot.send_message(user_id, f"✅ *Ваша заявка #{order_id} принята!*\n\nОператор скоро свяжется с вами.", parse_mode="Markdown")
            else:
                await bot.send_message(user_id, f"✅ *Your order #{order_id} has been accepted!*\n\nOperator will contact you shortly.", parse_mode="Markdown")
            
            await call.message.edit_text(f"✅ Заявка #{order_id} принята!", reply_markup=None)
        await call.answer()
        return
    
    if data.startswith("reject_"):
        if uid != ADMIN_ID:
            await call.answer("Доступ запрещен", show_alert=True)
            return
        order_id = int(data.split("_")[1])
        cur.execute('SELECT user_id, type, coin, amount FROM orders WHERE id = ?', (order_id,))
        order = cur.fetchone()
        if order:
            user_id, o_type, coin, amount = order
            cur.execute('UPDATE orders SET status = "rejected" WHERE id = ?', (order_id,))
            conn.commit()
            
            # Уведомляем пользователя
            user_lang = get_lang(user_id)
            if user_lang == 'ru':
                await bot.send_message(user_id, f"❌ *Ваша заявка #{order_id} отклонена!*\n\nВы можете создать новую заявку.", parse_mode="Markdown")
            else:
                await bot.send_message(user_id, f"❌ *Your order #{order_id} has been rejected!*\n\nYou can create a new order.", parse_mode="Markdown")
            
            await call.message.edit_text(f"❌ Заявка #{order_id} отклонена!", reply_markup=None)
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
        
        # Уведомление админу с кнопками
        username = f"@{message.from_user.username}" if message.from_user.username else "no username"
        await bot.send_message(
            ADMIN_ID,
            f"🆕 *НОВАЯ ЗАЯВКА #{order_id}*\n\n"
            f"📌 {type_text} {coin}\n"
            f"💰 Сумма: {rub:,.0f} ₽\n"
            f"👤 Пользователь: {message.from_user.full_name}\n"
            f"{username}\n"
            f"🆔 ID: {uid}",
            parse_mode="Markdown",
            reply_markup=order_buttons(order_id)
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
    
    for order in orders:
        order_id, o_type, coin, amount, status = order
        type_text = "Покупка" if o_type == "buy" else "Продажа"
        text = f"📋 *Заявка #{order_id}*\n\n{type_text} {coin}\n💰 {amount:,.0f} ₽\nСтатус: {status}"
        await message.answer(text, parse_mode="Markdown", reply_markup=order_buttons(order_id))

async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
