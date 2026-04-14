from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def model_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Nano Banana Pro", callback_data="model_pro"),
            InlineKeyboardButton(text="Nano Banana 2", callback_data="model_v2")
        ]
    ])

def quality_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1K", callback_data="q_1k"),
            InlineKeyboardButton(text="2K", callback_data="q_2k"),
            InlineKeyboardButton(text="4K", callback_data="q_4k")
        ]
    ])

def ratio_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1:1", callback_data="r_1_1"),
            InlineKeyboardButton(text="9:16", callback_data="r_9_16"),
            InlineKeyboardButton(text="16:9", callback_data="r_16_9")
        ]
    ])