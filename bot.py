import asyncio
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    init_db,
    get_or_create_user,
    add_card,
    get_cards,
    get_card_id,
    add_category,
    get_best_cashback,
)

# ---------------- config ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- FSM ----------------
class AddCardFSM(StatesGroup):
    waiting_for_card_name = State()


class FillCashbackFSM(StatesGroup):
    waiting_for_card = State()
    waiting_for_category = State()
    waiting_for_cashback = State()

# ---------------- keyboards ----------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить карту", callback_data="add_card")],
        [InlineKeyboardButton(text="🧾 Заполнить кешбеки моих карт", callback_data="fill_cashback")],
        [InlineKeyboardButton(text="💰 Посмотреть мой кешбек", callback_data="show_cashback")]
    ])


def cards_keyboard(user_id: int):
    cards = get_cards(user_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"card:{name}")]
        for _, name in cards
    ])


def continue_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё категорию", callback_data="add_more")],
        [InlineKeyboardButton(text="✅ Закончить", callback_data="finish")]
    ])

# ---------------- start ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    get_or_create_user(message.from_user.id)
    await message.answer(
        "Привет! Я помогу тебе следить за кешбеком 💳",
        reply_markup=main_menu()
    )

# ---------------- add card ----------------
@dp.callback_query(lambda c: c.data == "add_card")
async def add_card_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название карты:")
    await state.set_state(AddCardFSM.waiting_for_card_name)
    await callback.answer()


@dp.message(AddCardFSM.waiting_for_card_name)
async def add_card_finish(message: types.Message, state: FSMContext):
    user_id = get_or_create_user(message.from_user.id)
    card_name = message.text.strip()

    if card_name in [name for _, name in get_cards(user_id)]:
        await message.answer("❌ Такая карта уже есть.")
        return

    add_card(user_id, card_name)
    await message.answer(f"✅ Карта «{card_name}» добавлена", reply_markup=main_menu())
    await state.clear()

# ---------------- fill cashback ----------------
@dp.callback_query(lambda c: c.data == "fill_cashback")
async def fill_cashback_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = get_or_create_user(callback.from_user.id)
    if not get_cards(user_id):
        await callback.message.answer("❌ Сначала добавьте карту.")
        await callback.answer()
        return

    await callback.message.answer(
        "Выберите карту:",
        reply_markup=cards_keyboard(user_id)
    )
    await state.set_state(FillCashbackFSM.waiting_for_card)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("card:"))
async def choose_card(callback: types.CallbackQuery, state: FSMContext):
    card_name = callback.data.split(":", 1)[1]
    await state.update_data(card_name=card_name)
    await callback.message.answer("Введите название категории:")
    await state.set_state(FillCashbackFSM.waiting_for_category)
    await callback.answer()


@dp.message(FillCashbackFSM.waiting_for_category)
async def input_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text.strip())
    await message.answer("Введите кешбек в процентах:")
    await state.set_state(FillCashbackFSM.waiting_for_cashback)


@dp.message(FillCashbackFSM.waiting_for_cashback)
async def input_cashback(message: types.Message, state: FSMContext):
    try:
        cashback = int(message.text)
        if not 0 <= cashback <= 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 100")
        return

    data = await state.get_data()
    user_id = get_or_create_user(message.from_user.id)
    card_id = get_card_id(user_id, data["card_name"])

    add_category(card_id, data["category"], cashback)

    await message.answer(
        f"✅ Категория «{data['category']}» добавлена",
        reply_markup=continue_keyboard()
    )

    await state.set_state(FillCashbackFSM.waiting_for_category)

# ---------------- continue / finish ----------------
@dp.callback_query(lambda c: c.data == "add_more")
async def add_more(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название следующей категории:")
    await state.set_state(FillCashbackFSM.waiting_for_category)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "finish")
async def finish(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("✅ Кешбеки сохранены", reply_markup=main_menu())
    await callback.answer()

# ---------------- show cashback ----------------
@dp.callback_query(lambda c: c.data == "show_cashback")
async def show_cashback(callback: types.CallbackQuery):
    user_id = get_or_create_user(callback.from_user.id)
    rows = get_best_cashback(user_id)

    if not rows:
        await callback.message.answer("❌ Кешбеки ещё не заполнены.")
        await callback.answer()
        return

    text = "💰 *Ваш максимальный кешбек:*\n\n"
    for category, cashback, card in rows:
        text += f"• {category} — *{cashback}%* (карта: {card})\n"

    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# ---------------- run ----------------
async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
