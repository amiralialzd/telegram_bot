from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from states import GenerateState
from keyboards import model_keyboard
from db import get_or_create_user, set_language
from texts import t

router = Router()


def main_menu_keyboard(lang: str, has_credits: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_credits:
        buttons.append([InlineKeyboardButton(text=t(lang, "btn_generate"), callback_data="go_generate")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_balance"), callback_data="go_balance")])
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="toggle_lang")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username or ""
    )

    lang = user.get("language", "tr")
    credits = user["credits"]

    if credits > 0:
        text = t(lang, "welcome_new", name=message.from_user.full_name, credits=credits)
    else:
        text = t(lang, "no_credits", name=message.from_user.full_name)

    await message.answer(text, reply_markup=main_menu_keyboard(lang, credits > 0))


@router.callback_query(lambda c: c.data == "toggle_lang")
async def toggle_language(callback: CallbackQuery):
    from db import get_user
    user = await get_user(callback.from_user.id)
    current_lang = user.get("language", "tr") if user else "tr"
    new_lang = "en" if current_lang == "tr" else "tr"
    await set_language(callback.from_user.id, new_lang)

    credits = user["credits"] if user else 0
    await callback.message.edit_text(
        t(new_lang, "welcome_back", name=callback.from_user.full_name, credits=credits),
        reply_markup=main_menu_keyboard(new_lang, credits > 0)
    )
    await callback.answer(t(new_lang, "lang_changed"))


@router.callback_query(lambda c: c.data == "go_generate")
async def go_generate(callback: CallbackQuery, state: FSMContext):
    from db import get_user
    user = await get_user(callback.from_user.id)
    lang = user.get("language", "tr") if user else "tr"
    await callback.message.answer(t(lang, "choose_model"), reply_markup=model_keyboard())
    await state.set_state(GenerateState.choosing_model)
    await callback.answer()