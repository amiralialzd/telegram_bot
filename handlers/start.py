from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from states import GenerateState
from keyboards import model_keyboard
from db import get_or_create_user, get_user

router = Router()

def main_menu_keyboard(has_credits: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_credits:
        buttons.append([InlineKeyboardButton(text="🎨 Image Generation", callback_data="go_generate")])
    buttons.append([InlineKeyboardButton(text="💳 Balance", callback_data="go_balance")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username or ""
    )

    credits = user["credits"]

    if credits > 0:
        await message.answer(
            f"Welcome, <b>{message.from_user.full_name}</b>! 👋\n\n"
            f"💰 Your balance: <b>{credits} credits</b>\n\n"
            f"What would you like to do?",
            reply_markup=main_menu_keyboard(has_credits=True)
        )
    else:
        await message.answer(
            f"Welcome back, <b>{message.from_user.full_name}</b>! 👋\n\n"
            f"😔 You have <b>0 credits</b> left.\n"
            f"Top up your balance to continue generating images.",
            reply_markup=main_menu_keyboard(has_credits=False)
        )


@router.callback_query(lambda c: c.data == "go_generate")
async def go_generate(callback, state: FSMContext):
    await callback.message.answer("Choose your model:", reply_markup=model_keyboard())
    await state.set_state(GenerateState.choosing_model)
    await callback.answer()


@router.callback_query(lambda c: c.data == "go_balance")
async def go_balance(callback, state: FSMContext):
    user = await get_user(callback.from_user.id)
    credits = user["credits"] if user else 0
    await callback.message.answer(
        f"💳 <b>Your Balance</b>\n\n"
        f"Credits remaining: <b>{credits}</b>\n\n"
        f"To top up, contact support."
    )
    await callback.answer()