from aiogram import Router
from aiogram.types import (
    CallbackQuery, Message,
    LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from db import get_user, add_credits
from texts import t

router = Router()

PACKAGES = [
    {"stars": 100,  "credits": 100},
    {"stars": 250,  "credits": 250},
    {"stars": 1000, "credits": 1000},
]

def shop_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"⭐ {p['stars']} Stars → {p['credits']} Kredi" if lang == "tr"
                 else f"⭐ {p['stars']} Stars → {p['credits']} Credits",
            callback_data=f"buy_{p['stars']}"
        )]
        for p in PACKAGES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(lambda c: c.data == "go_balance")
async def show_balance(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get("language", "tr") if user else "tr"
    credits = user["credits"] if user else 0
    await callback.message.answer(
        t(lang, "balance_msg", credits=credits),
        reply_markup=shop_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("buy_"))
async def send_invoice(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get("language", "tr") if user else "tr"

    try:
        stars = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Hata." if lang == "tr" else "Error.", show_alert=True)
        return

    package = next((p for p in PACKAGES if p["stars"] == stars), None)
    if not package:
        await callback.answer(
            "Geçersiz paket." if lang == "tr" else "Invalid package.",
            show_alert=True
        )
        return

    title = f"{package['credits']} Kredi" if lang == "tr" else f"{package['credits']} Credits"
    desc  = (f"Nano Banana bakiyene {package['credits']} kredi ekle."
             if lang == "tr" else
             f"Add {package['credits']} credits to your Nano Banana balance.")

    await callback.message.answer_invoice(
        title=title,
        description=desc,
        payload=f"credits_{package['credits']}",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=package["stars"])],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(lambda m: m.successful_payment is not None)
async def successful_payment(message: Message):
    payment = message.successful_payment
    try:
        credits_to_add = int(payment.invoice_payload.split("_")[1])
    except (IndexError, ValueError):
        await message.answer("Ödeme alındı ama bir hata oluştu. Destek ile iletişime geç.")
        return

    new_balance = await add_credits(message.from_user.id, credits_to_add)
    user = await get_user(message.from_user.id)
    lang = user.get("language", "tr") if user else "tr"
    await message.answer(t(lang, "payment_success", credits=credits_to_add, balance=new_balance))