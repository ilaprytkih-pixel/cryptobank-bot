import os
import sqlite3
import logging
import random
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN', '8475967867:AAERsgs07LHdhHDadjO2t7HJk4ACSG94kIA')
ADMIN_USERNAME = "@venomvwwv"
ADMIN_PASSWORD = "1#4#8#8"

# Криптовалюты с начальными инвестициями по 100 миллионов
CRYPTOCURRENCIES = {
    "NEO": {"name": "NeoCoin", "rate": 50.0, "volatility": 0.08, "total_invested": 100000000},
    "QUAN": {"name": "QuantumToken", "rate": 25.0, "volatility": 0.12, "total_invested": 100000000},
    "ZEN": {"name": "ZenithCoin", "rate": 75.0, "volatility": 0.06, "total_invested": 100000000},
    "VOY": {"name": "VoyagerToken", "rate": 15.0, "volatility": 0.15, "total_invested": 100000000},
    "AXI": {"name": "AxiomCoin", "rate": 40.0, "volatility": 0.09, "total_invested": 100000000}
}

# Инициализация БД
def init_db():
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0,
                  deposit_balance REAL DEFAULT 0, referral_code TEXT, is_subscribed INTEGER DEFAULT 1,
                  registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS cryptocurrencies
                 (symbol TEXT PRIMARY KEY, name TEXT, current_rate REAL, 
                  previous_rate REAL, volatility REAL, total_invested REAL DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS investments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, crypto_symbol TEXT,
                  amount REAL, buy_rate REAL, investment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS deposits
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
                  start_date TIMESTAMP, end_date TIMESTAMP, status TEXT DEFAULT 'active')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS bank
                 (id INTEGER PRIMARY KEY DEFAULT 1, total_balance REAL DEFAULT 0,
                  reserve_balance REAL DEFAULT 0)''')
    
    # Инициализация криптовалют
    for symbol, data in CRYPTOCURRENCIES.items():
        c.execute('''INSERT OR IGNORE INTO cryptocurrencies 
                     (symbol, name, current_rate, previous_rate, volatility, total_invested) 
                     VALUES (?, ?, ?, ?, ?, ?)''',
                 (symbol, data["name"], data["rate"], data["rate"], data["volatility"], data["total_invested"]))
    
    # Инициализация баланса банка (0)
    c.execute("INSERT OR IGNORE INTO bank (id, total_balance, reserve_balance) VALUES (1, 0, 0)")
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# Функции для работы с БД
def get_user_data(user_id):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    referral_code = f"REF{user_id}{random.randint(1000, 9999)}"
    
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, referral_code, balance) 
                 VALUES (?, ?, ?, ?)''',
             (user_id, username, referral_code, 0))
    
    conn.commit()
    conn.close()
    return referral_code

def get_bank_balance():
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT total_balance, reserve_balance FROM bank WHERE id = 1")
    balance = c.fetchone()
    conn.close()
    return balance

def update_bank_balance(amount):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE bank SET total_balance = total_balance + ? WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

def get_crypto_data(symbol):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM cryptocurrencies WHERE symbol = ?", (symbol,))
    crypto = c.fetchone()
    conn.close()
    return crypto

def get_all_cryptos():
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM cryptocurrencies")
    cryptos = c.fetchall()
    conn.close()
    return cryptos

def update_crypto_rates():
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    
    cryptos = get_all_cryptos()
    bank_balance = get_bank_balance()[0]
    
    for crypto in cryptos:
        symbol, name, current_rate, previous_rate, volatility, total_invested = crypto
        c.execute("UPDATE cryptocurrencies SET previous_rate = ? WHERE symbol = ?", 
                 (current_rate, symbol))
    
    for crypto in cryptos:
        symbol, name, current_rate, previous_rate, volatility, total_invested = crypto
        
        base_change = random.uniform(-volatility, volatility)
        demand_factor = min(total_invested / 100000000, 0.3)
        demand_change = demand_factor * random.uniform(0.01, 0.05)
        bank_factor = max(0, (bank_balance - 300000) / 1000000)
        stability_bonus = bank_factor * 0.02
        
        total_change = base_change + demand_change - stability_bonus
        total_change = max(min(total_change, volatility * 1.5), -volatility * 1.5)
        
        new_rate = current_rate * (1 + total_change)
        
        if new_rate < current_rate * 0.3:
            new_rate = current_rate * 0.7

        c.execute("UPDATE cryptocurrencies SET current_rate = ? WHERE symbol = ?", 
                 (round(new_rate, 2), symbol))
    
    conn.commit()
    conn.close()
    logger.info("📊 Курсы криптовалют обновлены")

def create_investment(user_id, crypto_symbol, amount):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT current_rate FROM cryptocurrencies WHERE symbol = ?", (crypto_symbol,))
    current_rate = c.fetchone()[0]
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance = c.fetchone()[0]
    
    if user_balance >= amount:
        c.execute('''INSERT INTO investments 
                     (user_id, crypto_symbol, amount, buy_rate) 
                     VALUES (?, ?, ?, ?)''',
                 (user_id, crypto_symbol, amount, current_rate))
        
        c.execute("UPDATE cryptocurrencies SET total_invested = total_invested + ? WHERE symbol = ?",
                 (amount, crypto_symbol))
        
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", 
                 (amount, user_id))
        
        conn.commit()
        conn.close()
        return True, current_rate
    else:
        conn.close()
        return False, 0

def get_user_investments(user_id):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''SELECT i.*, c.current_rate, c.name 
                 FROM investments i 
                 JOIN cryptocurrencies c ON i.crypto_symbol = c.symbol 
                 WHERE i.user_id = ?''', (user_id,))
    investments = c.fetchall()
    conn.close()
    return investments

def create_deposit(user_id, amount, days):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user_balance = c.fetchone()[0]
    
    if user_balance >= amount and days <= 10:
        start_date = datetime.now()
        end_date = start_date + timedelta(days=days)
        
        c.execute('''INSERT INTO deposits 
                     (user_id, amount, start_date, end_date) 
                     VALUES (?, ?, ?, ?)''',
                 (user_id, amount, start_date, end_date))
        
        c.execute("UPDATE users SET balance = balance - ?, deposit_balance = deposit_balance + ? WHERE user_id = ?", 
                 (amount, amount, user_id))
        
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

def get_user_deposits(user_id):
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM deposits WHERE user_id = ? AND status = 'active'", (user_id,))
    deposits = c.fetchall()
    conn.close()
    return deposits

def process_deposits():
    conn = sqlite3.connect('bank.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT * FROM deposits WHERE status = 'active'")
    deposits = c.fetchall()
    
    for deposit in deposits:
        deposit_id, user_id, amount, start_date, end_date, status = deposit
        end_date = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
        
        if datetime.now() >= end_date:
            start_date = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
            days = (end_date - start_date).days
            total_return = amount * (1 + 0.05 * days)
            
            c.execute("UPDATE users SET balance = balance + ?, deposit_balance = deposit_balance - ? WHERE user_id = ?", 
                     (total_return, amount, user_id))
            c.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (deposit_id,))
    
    conn.commit()
    conn.close()

# Состояния пользователей
user_states = {}

# Команды бота
def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or "Пользователь"
    
    referral_code = create_user(user_id, username)

    welcome_text = f"""
👋 Добро пожаловать в <b>CryptoBank</b>, {username}!

💰 <b>Ваш баланс:</b> 0 монет
🔗 <b>Реферальный код:</b> <code>{referral_code}</code>

📊 <b>Доступные функции:</b>
• 💰 Баланс - /balance
• 📈 Инвестиции - /invest  
• 🏦 Депозиты - /deposit
• 📊 Курсы - /rates
• 💼 Мои инвестиции - /myinvest
• 🏦 Мои депозиты - /mydeposits

💡 <b>Пополнение баланса:</b> Напишите {ADMIN_USERNAME}
    """

    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data='balance'),
         InlineKeyboardButton("📊 Курсы", callback_data='rates')],
        [InlineKeyboardButton("💼 Инвестиции", callback_data='invest'),
         InlineKeyboardButton("🏦 Депозиты", callback_data='deposit')],
        [InlineKeyboardButton("👤 Мой профиль", callback_data='profile')]
    ]

    update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

def balance(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if user_data:
        balance = user_data[2] or 0
        deposit_balance = user_data[3] or 0

        response = f"""
💰 <b>Ваш финансовый статус:</b>

💵 <b>Доступный баланс:</b> {balance:,.2f} монет
🏦 <b>В депозитах:</b> {deposit_balance:,.2f} монет
💎 <b>Общий капитал:</b> {balance + deposit_balance:,.2f} монет

💳 <b>Пополнение баланса:</b> Напишите {ADMIN_USERNAME}
        """
        update.message.reply_text(response, parse_mode='HTML')

def invest(update: Update, context: CallbackContext) -> None:
    cryptos = get_all_cryptos()
    
    buttons = []
    for crypto in cryptos:
        symbol, name, current_rate, previous_rate, volatility, total_invested = crypto
        buttons.append([InlineKeyboardButton(f"📈 {name} (${current_rate:.2f})", callback_data=f'invest_{symbol}')])

    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data='main_menu')])
    
    update.message.reply_text(
        "💼 <b>Выберите криптовалюту для инвестирования:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='HTML'
    )

def deposit(update: Update, context: CallbackContext) -> None:
    warning_text = """
🏦 <b>Банковские депозиты</b>

📈 <b>Доходность:</b> 5% в день
⏰ <b>Максимальный срок:</b> 10 дней
💰 <b>Минимальная сумма:</b> 100 монет

⚠️ <b>Внимание:</b> Депозит работает максимум 10 дней!
После окончания срока проценты не начисляются.

Выберите срок депозита:
    """

    keyboard = [
        [InlineKeyboardButton("1 день (+5%)", callback_data='deposit_1'),
         InlineKeyboardButton("3 дня (+15%)", callback_data='deposit_3')],
        [InlineKeyboardButton("7 дней (+35%)", callback_data='deposit_7'),
         InlineKeyboardButton("10 дней (+50%)", callback_data='deposit_10')],
        [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
    ]

    update.message.reply_text(warning_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

def rates(update: Update, context: CallbackContext) -> None:
    cryptos = get_all_cryptos()
    bank_balance = get_bank_balance()[0]

    rates_text = "📊 <b>Текущие курсы криптовалют:</b>\n\n"

    for crypto in cryptos:
        symbol, name, current, previous, volatility, invested = crypto
        change = ((current - previous) / previous) * 100
        arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"

        rates_text += f"<b>{name} ({symbol})</b>\n"
        rates_text += f"💵 <b>Курс:</b> ${current:.2f} {arrow} {change:+.2f}%\n"
        rates_text += f"💰 <b>Объем инвестиций:</b> {invested:,.0f} монет\n\n"

    rates_text += f"🏦 <b>Баланс банка:</b> {bank_balance:,.0f} монет\n"
    rates_text += "🔄 Курсы обновляются каждые 5 минут"

    keyboard = [[
        InlineKeyboardButton("🔄 Обновить", callback_data='rates'),
        InlineKeyboardButton("🔙 Назад", callback_data='main_menu')
    ]]

    update.message.reply_text(rates_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

def myinvest(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    investments = get_user_investments(user_id)

    if not investments:
        update.message.reply_text("💼 <b>У вас пока нет инвестиций</b>\n\nИспользуйте /invest чтобы начать инвестировать!", parse_mode='HTML')
        return

    investments_text = "💼 <b>Ваши инвестиции:</b>\n\n"
    total_value = 0

    for inv in investments:
        inv_id, user_id, symbol, amount, buy_rate, date, current_rate, name = inv
        current_value = amount * (current_rate / buy_rate)
        profit = current_value - amount
        profit_percent = (profit / amount) * 100

        investments_text += f"<b>{name} ({symbol})</b>\n"
        investments_text += f"💰 <b>Инвестировано:</b> {amount:,.0f} монет\n"
        investments_text += f"📈 <b>Текущая стоимость:</b> {current_value:,.0f} монет\n"
        investments_text += f"💵 <b>Прибыль:</b> {profit:+.0f} монет ({profit_percent:+.1f}%)\n"
        investments_text += f"📅 <b>Дата:</b> {date[:10]}\n\n"

        total_value += current_value

    investments_text += f"💎 <b>Общая стоимость портфеля:</b> {total_value:,.0f} монет"

    update.message.reply_text(investments_text, parse_mode='HTML')

def mydeposits(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    deposits = get_user_deposits(user_id)

    if not deposits:
        update.message.reply_text("🏦 <b>У вас нет активных депозитов</b>\n\nИспользуйте /deposit чтобы открыть депозит!", parse_mode='HTML')
        return

    deposits_text = "🏦 <b>Ваши активные депозиты:</b>\n\n"

    for dep in deposits:
        dep_id, user_id, amount, start_date, end_date, status = dep
        end_date_obj = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
        start_date_obj = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        days_passed = (datetime.now() - start_date_obj).days
        total_days = (end_date_obj - start_date_obj).days
        expected_return = amount * (1 + 0.05 * total_days)

        deposits_text += f"<b>Депозит #{dep_id}</b>\n"
        deposits_text += f"💰 <b>Сумма:</b> {amount:,.0f} монет\n"
        deposits_text += f"📅 <b>Начало:</b> {start_date_obj.strftime('%d.%m.%Y')}\n"
        deposits_text += f"⏰ <b>Окончание:</b> {end_date_obj.strftime('%d.%m.%Y')}\n"
        deposits_text += f"⏳ <b>Прошло дней:</b> {days_passed}/{total_days}\n"
        deposits_text += f"💵 <b>Ожидаемый возврат:</b> {expected_return:,.0f} монет\n\n"

    update.message.reply_text(deposits_text, parse_mode='HTML')

def admin(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    text = update.message.text

    if text == f"/admin {ADMIN_PASSWORD}":
        admin_text = f"""
🔧 <b>Панель администратора</b>

👤 <b>Админ:</b> {username}

<b>Команды:</b>
• /add_balance [сумма] - Пополнить казну
• /bank_stats - Статистика банка

<b>Пополнение пользователей:</b>
Напишите: <code>пополнить @username 1000</code>
        """
        update.message.reply_text(admin_text, parse_mode='HTML')
    else:
        update.message.reply_text("❌ Неверный пароль админа")

def add_balance(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    
    if ADMIN_USERNAME not in username:
        update.message.reply_text("❌ У вас нет прав для этой команды!")
        return

    if not context.args:
        update.message.reply_text("❌ Использование: /add_balance [сумма]")
        return

    try:
        amount = float(context.args[0])
        update_bank_balance(amount)
        update.message.reply_text(f"✅ В казну банка добавлено {amount:,.0f} монет!")
    except ValueError:
        update.message.reply_text("❌ Неверная сумма!")

# Обработка кнопок
def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    query.answer()

    if data == 'main_menu':
        welcome_text = """
👋 Добро пожаловать в <b>CryptoBank</b>!

Выберите действие:
        """
        keyboard = [
            [InlineKeyboardButton("💰 Баланс", callback_data='balance'),
             InlineKeyboardButton("📊 Курсы", callback_data='rates')],
            [InlineKeyboardButton("💼 Инвестиции", callback_data='invest'),
             InlineKeyboardButton("🏦 Депозиты", callback_data='deposit')],
            [InlineKeyboardButton("👤 Мой профиль", callback_data='profile')]
        ]
        query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    elif data == 'balance':
        user_data = get_user_data(user_id)
        if user_data:
            response = f"""
💰 <b>Ваш финансовый статус:</b>

💵 <b>Доступный баланс:</b> {user_data[2]:,.2f} монет
🏦 <b>В депозитах:</b> {user_data[3]:,.2f} монет
💎 <b>Общий капитал:</b> {user_data[2] + user_data[3]:,.2f} монет

💳 <b>Пополнение баланса:</b> Напишите {ADMIN_USERNAME}
            """
            query.edit_message_text(response, parse_mode='HTML')
    
    elif data == 'rates':
        cryptos = get_all_cryptos()
        bank_balance = get_bank_balance()[0]

        rates_text = "📊 <b>Текущие курсы криптовалют:</b>\n\n"

        for crypto in cryptos:
            symbol, name, current, previous, volatility, invested = crypto
            change = ((current - previous) / previous) * 100
            arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"

            rates_text += f"<b>{name} ({symbol})</b>\n"
            rates_text += f"💵 <b>Курс:</b> ${current:.2f} {arrow} {change:+.2f}%\n"
            rates_text += f"💰 <b>Объем инвестиций:</b> {invested:,.0f} монет\n\n"

        rates_text += f"🏦 <b>Баланс банка:</b> {bank_balance:,.0f} монет\n"
        rates_text += "🔄 Курсы обновляются каждые 5 минут"

        keyboard = [[
            InlineKeyboardButton("🔄 Обновить", callback_data='rates'),
            InlineKeyboardButton("🔙 Назад", callback_data='main_menu')
        ]]
        query.edit_message_text(rates_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    elif data == 'invest':
        cryptos = get_all_cryptos()
        buttons = []
        for crypto in cryptos:
            symbol, name, current_rate, previous_rate, volatility, total_invested = crypto
            buttons.append([InlineKeyboardButton(f"📈 {name} (${current_rate:.2f})", callback_data=f'invest_{symbol}')])
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data='main_menu')])
        query.edit_message_text(
            '💼 <b>Выберите криптовалюту для инвестирования:</b>',
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
    
    elif data == 'deposit':
        warning_text = """
🏦 <b>Банковские депозиты</b>

📈 <b>Доходность:</b> 5% в день
⏰ <b>Максимальный срок:</b> 10 дней
💰 <b>Минимальная сумма:</b> 100 монет

⚠️ <b>Внимание:</b> Депозит работает максимум 10 дней!
После окончания срока проценты не начисляются.

Выберите срок депозита:
        """
        keyboard = [
            [InlineKeyboardButton("1 день (+5%)", callback_data='deposit_1'),
             InlineKeyboardButton("3 дня (+15%)", callback_data='deposit_3')],
            [InlineKeyboardButton("7 дней (+35%)", callback_data='deposit_7'),
             InlineKeyboardButton("10 дней (+50%)", callback_data='deposit_10')],
            [InlineKeyboardButton("🔙 Назад", callback_data='main_menu')]
        ]
        query.edit_message_text(warning_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    elif data == 'profile':
        user_data = get_user_data(user_id)
        if user_data:
            profile_text = f"""
👤 <b>Ваш профиль</b>

🆔 <b>ID:</b> {user_id}
👤 <b>Username:</b> @{user_data[1]}
💰 <b>Баланс:</b> {user_data[2]:,.0f} монет
🏦 <b>В депозитах:</b> {user_data[3]:,.0f} монет
🔗 <b>Реферальный код:</b> <code>{user_data[4]}</code>
📅 <b>Регистрация:</b> {user_data[6][:10]}
            """
            query.edit_message_text(profile_text, parse_mode='HTML')
    
    elif data.startswith('invest_'):
        crypto_symbol = data.split('_')[1]
        crypto_data = get_crypto_data(crypto_symbol)
        if crypto_data:
            response = f"""
💼 <b>Инвестиция в {crypto_data[1]} ({crypto_symbol})</b>

💵 <b>Текущий курс:</b> ${crypto_data[2]:.2f}
📈 <b>Волатильность:</b> {crypto_data[4] * 100:.1f}%
💰 <b>Общий объем инвестиций:</b> {crypto_data[5]:,.0f} монet

Введите сумму для инвестиции (мин. 100 монет):
            """
            user_states[user_id] = {'type': 'waiting_investment_amount', 'crypto_symbol': crypto_symbol}
            query.edit_message_text(response, parse_mode='HTML')
    
    elif data.startswith('deposit_'):
        days = int(data.split('_')[1])
        response = f"""
🏦 <b>Открытие депозита на {days} дней</b>

📈 <b>Доходность:</b> {5 * days}%
💰 <b>Минимальная сумма:</b> 100 монет
⏰ <b>Срок:</b> {days} дней

⚠️ <b>Внимание:</b> Максимальный срок депозита - 10 дней!

Введите сумму для депозита:
        """
        user_states[user_id] = {'type': 'waiting_deposit_amount', 'days': days}
        query.edit_message_text(response, parse_mode='HTML')

# Обработка текстовых сообщений (суммы)
def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in user_states and not text.startswith('/'):
        state = user_states[user_id]
        amount = float(text) if text.isdigit() else 0
        
        if amount < 100:
            update.message.reply_text("❌ Минимальная сумма - 100 монет!")
            return
            
        if state['type'] == 'waiting_investment_amount':
            success, buy_rate = create_investment(user_id, state['crypto_symbol'], amount)
            if success:
                crypto_data = get_crypto_data(state['crypto_symbol'])
                response = f"""
✅ <b>Инвестиция создана!</b>

💼 <b>Актив:</b> {crypto_data[1]} ({state['crypto_symbol']})
💰 <b>Сумма:</b> {amount:,.0f} монет
💵 <b>Курс покупки:</b> ${buy_rate:.2f}
📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

📊 Следите за изменением курса в разделе "Мои инвестиции"
                """
                del user_states[user_id]
            else:
                user_data = get_user_data(user_id)
                response = f"❌ Недостаточно средств! Ваш баланс: {user_data[2] if user_data else 0:,.0f} монет"
            
            update.message.reply_text(response, parse_mode='HTML')
            
        elif state['type'] == 'waiting_deposit_amount':
            success = create_deposit(user_id, amount, state['days'])
            if success:
                total_return = amount * (1 + 0.05 * state['days'])
                response = f"""
✅ <b>Депозит открыт!</b>

💰 <b>Сумма:</b> {amount:,.0f} монет
⏰ <b>Срок:</b> {state['days']} дней
📈 <b>Доходность:</b> {5 * state['days']}%
💵 <b>Ожидаемый возврат:</b> {total_return:,.0f} монет
📅 <b>Окончание:</b> {(datetime.now() + timedelta(days=state['days'])).strftime('%d.%m.%Y')}

⚠️ <b>Внимание:</b> Максимальный срок депозита - 10 дней!
                """
                del user_states[user_id]
            else:
                user_data = get_user_data(user_id)
                response = f"❌ Недостаточно средств! Ваш баланс: {user_data[2] if user_data else 0:,.0f} монет"
            
            update.message.reply_text(response, parse_mode='HTML')

# Веб-сервер для Railway
@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>CryptoBank Bot</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f0f2f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .status { color: green; font-weight: bold; font-size: 18px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 CryptoBank Bot</h1>
                <p class="status">✅ Бот работает в Telegram!</p>
                <p>Бот активен и готов принимать команды.</p>
                <p>Перейдите в Telegram и напишите боту команду /start</p>
            </div>
        </body>
    </html>
    """

# Фоновая задача для обновления курсов
def background_tasks():
    while True:
        try:
            update_crypto_rates()
            process_deposits()
            time.sleep(300)  # 5 минут
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче: {e}")
            time.sleep(60)

def run_bot():
    # Инициализация базы данных
    init_db()
    
    # Создание updater
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Добавление обработчиков команд
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("balance", balance))
    dispatcher.add_handler(CommandHandler("invest", invest))
    dispatcher.add_handler(CommandHandler("deposit", deposit))
    dispatcher.add_handler(CommandHandler("rates", rates))
    dispatcher.add_handler(CommandHandler("myinvest", myinvest))
    dispatcher.add_handler(CommandHandler("mydeposits", mydeposits))
    dispatcher.add_handler(CommandHandler("admin", admin))
    dispatcher.add_handler(CommandHandler("add_balance", add_balance))
    
    # Обработчики кнопок и сообщений
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Запуск фоновых задач
    bg_thread = Thread(target=background_tasks)
    bg_thread.daemon = True
    bg_thread.start()

    # Запуск бота
    updater.start_polling()
    logger.info("🤖 Бот запущен и готов к работе!")
    
    # Запуск веб-сервера для Railway
    port = int(os.environ.get('PORT', 3000))
    web_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False))
    web_thread.daemon = True
    web_thread.start()

if __name__ == '__main__':
    run_bot()
