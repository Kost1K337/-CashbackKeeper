import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

# ---------------------------
# Загрузка токена
# ---------------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------------------
# Работа с базой
# ---------------------------
DB_PATH = "bot.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bank TEXT,
        name TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER,
        name TEXT,
        cashback INTEGER,
        FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
    )
    """)
    conn.commit()
    conn.close()

def get_or_create_user(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (telegram_id,))
    conn.commit()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    user_id = cursor.fetchone()[0]
    conn.close()
    return user_id

def add_card(user_id, bank, card_name):
    full_name = f"{bank} – {card_name}"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO cards (user_id, bank, name) VALUES (?, ?, ?)", (user_id, bank, full_name))
    conn.commit()
    card_id = cursor.lastrowid
    conn.close()
    return card_id

def get_cards(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM cards WHERE user_id = ?", (user_id,))
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

def add_category(card_id, name, cashback):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (card_id, name, cashback) VALUES (?, ?, ?)", (card_id, name, cashback))
    conn.commit()
    conn.close()

def get_card_id(user_id, card_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM cards WHERE user_id = ? AND name = ?", (user_id, card_name))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def delete_card(user_id, card_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cards WHERE user_id = ? AND name = ?", (user_id, card_name))
    conn.commit()
    conn.close()

def update_category(card_id, category_name, cashback):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE categories SET cashback = ? WHERE card_id = ? AND name = ?", (cashback, card_id, category_name))
    conn.commit()
    conn.close()

def get_categories(card_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, cashback FROM categories WHERE card_id = ?", (card_id,))
    result = cursor.fetchall()
    conn.close()
    return result

# ---------------------------
# FSM
# ---------------------------
class AddCardFSM(StatesGroup):
    waiting_for_bank = State()
    waiting_for_card_name = State()
    waiting_for_category_name = State()
    waiting_for_category_percent = State()
    waiting_for_more_categories = State()

class UpdateCategoryFSM(StatesGroup):
    waiting_for_card = State()
    waiting_for_category = State()
    waiting_for_percent = State()

# ---------------------------
# Кнопки
# ---------------------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗂 Мои карты", callback_data="my_cards")],
        [InlineKeyboardButton(text="💰 Посмотреть все мои кешбеки", callback_data="view_cashback")],
        [InlineKeyboardButton(text="🔜 Подобрать карту под покупку", callback_data="pick_card")],
    ])

def bank_keyboard():
    banks = ["Сбербанк", "ВТБ", "Альфа-Банк", "Т-Банк", "Газпромбанк", "Другой"]
    buttons = [[InlineKeyboardButton(text=b, callback_data=f"bank:{b}")] for b in banks]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_cards_keyboard(user_id):
    cards = get_cards(user_id)
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"card:{c}")] for c in cards]
    buttons.append([InlineKeyboardButton(text="➕ Добавить новую карту", callback_data="add_card")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def card_actions_keyboard(card_name):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить кешбек", callback_data=f"update_cb:{card_name}")],
        [InlineKeyboardButton(text="❌ Удалить карту", callback_data=f"delete_card:{card_name}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="my_cards")],
    ])

def more_categories_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Еще категорию", callback_data="more_category")],
        [InlineKeyboardButton(text="✅ Завершить создание карты", callback_data="finish_card")],
    ])

# ---------------------------
# Бот
# ---------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------------------
# /start
# ---------------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! Я помогу управлять твоими картами 💳",
        reply_markup=main_menu()
    )

# ---------------------------
# Главное меню через кнопки
# ---------------------------
@dp.callback_query(lambda c: c.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu())
    await callback.answer()

# ---------------------------
# Мои карты
# ---------------------------
@dp.callback_query(lambda c: c.data == "my_cards")
async def my_cards(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    user_id = get_or_create_user(telegram_id)
    await callback.message.edit_text("Мои карты:", reply_markup=user_cards_keyboard(user_id))
    await callback.answer()

# ---------------------------
# Действия с картой
# ---------------------------
@dp.callback_query(lambda c: c.data.startswith("card:"))
async def card_actions(callback: types.CallbackQuery):
    card_name = callback.data.split(":", 1)[1]
    await callback.message.edit_text(f"Выбрана карта: {card_name}", reply_markup=card_actions_keyboard(card_name))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_card:"))
async def delete_card_callback(callback: types.CallbackQuery):
    card_name = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    user_id = get_or_create_user(telegram_id)
    delete_card(user_id, card_name)
    await callback.message.edit_text(f"✅ Карта «{card_name}» удалена", reply_markup=user_cards_keyboard(user_id))
    await callback.answer()

# ---------------------------
# Добавление карты
# ---------------------------
@dp.callback_query(lambda c: c.data == "add_card")
async def add_card_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите банк:", reply_markup=bank_keyboard())
    await state.set_state(AddCardFSM.waiting_for_bank)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("bank:"))
async def add_card_bank(callback: types.CallbackQuery, state: FSMContext):
    bank_name = callback.data.split(":",1)[1]
    await state.update_data(bank=bank_name)
    await callback.message.edit_text(f"Выбран банк: {bank_name}\nВведите название карты:")
    await state.set_state(AddCardFSM.waiting_for_card_name)
    await callback.answer()

@dp.message(AddCardFSM.waiting_for_card_name)
async def add_card_name(message: types.Message, state: FSMContext):
    card_name = message.text.strip()
    telegram_id = message.from_user.id
    user_id = get_or_create_user(telegram_id)
    data = await state.get_data()
    bank = data["bank"]
    card_id = add_card(user_id, bank, card_name)
    await state.update_data(card_id=card_id)
    await message.answer("Введите название категории для кешбека:")
    await state.set_state(AddCardFSM.waiting_for_category_name)

@dp.message(AddCardFSM.waiting_for_category_name)
async def add_category_name(message: types.Message, state: FSMContext):
    await state.update_data(category_name=message.text.strip())
    await message.answer("Введите процент кешбека (например 5):")
    await state.set_state(AddCardFSM.waiting_for_category_percent)

@dp.message(AddCardFSM.waiting_for_category_percent)
async def add_category_percent(message: types.Message, state: FSMContext):
    try:
        percent = int(message.text.strip())
        if not (0 <= percent <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 100")
        return
    data = await state.get_data()
    add_category(data["card_id"], data["category_name"], percent)
    await message.answer(f"✅ Категория «{data['category_name']}» с кешбеком {percent}% добавлена", reply_markup=more_categories_keyboard())
    await state.set_state(AddCardFSM.waiting_for_more_categories)

@dp.callback_query(lambda c: c.data == "more_category")
async def more_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название следующей категории:")
    await state.set_state(AddCardFSM.waiting_for_category_name)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "finish_card")
async def finish_card(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Карта создана ✅", reply_markup=main_menu())
    await state.clear()
    await callback.answer()

# ---------------------------
# Просмотр кешбеков
# ---------------------------
@dp.callback_query(lambda c: c.data == "view_cashback")
async def view_cashback(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    user_id = get_or_create_user(telegram_id)
    cards = get_cards(user_id)
    if not cards:
        await callback.message.edit_text("У вас пока нет карт", reply_markup=main_menu())
        await callback.answer()
        return
    text = ""
    for card in cards:
        card_id = get_card_id(user_id, card)
        categories = get_categories(card_id)
        if categories:
            text += f"💳 {card}:\n"
            for name, cb in categories:
                text += f" - {name}: {cb}%\n"
        else:
            text += f"💳 {card}: категории не добавлены\n"
    await callback.message.edit_text(text, reply_markup=main_menu())
    await callback.answer()

# ---------------------------
# Подбор карты (пока анонс)
# ---------------------------
@dp.callback_query(lambda c: c.data == "pick_card")
async def pick_card(callback: types.CallbackQuery):
    await callback.message.edit_text("Функционал подбора карты появится скоро 🔜", reply_markup=main_menu())
    await callback.answer()

# ---------------------------
# Запуск
# ---------------------------
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
