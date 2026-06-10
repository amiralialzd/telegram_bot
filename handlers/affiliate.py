import os
from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db import get_user
from db_referral import generate_referral_code, get_referral_stats, set_referred_by
from texts import t

router = Router()

BOT_USERNAME = os.getenv("BOT_USERNAME")

CONTACT_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="💬 @amiralialzd",   url="https://t.me/amiralialzd"),
        InlineKeyboardButton(text="💬 @skachanouski", url="https://t.me/skachanouski"),
    ]
])


def affiliate_keyboard(lang: str) -> InlineKeyboardMarkup:
    labels = {
        "tr": "🔄 Yenile",
        "en": "🔄 Refresh",
        "ru": "🔄 Обновить",
        "fa": "🔄 بروزرسانی",
    }
    withdraw_labels = {
        "tr": "💸 Para Çek",
        "en": "💸 Withdraw",
        "ru": "💸 Вывести",
        "fa": "💸 برداشت",
    }
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels.get(lang, "🔄 Refresh"), callback_data="affiliate_refresh")],
        [InlineKeyboardButton(text=withdraw_labels.get(lang, "💸 Withdraw"), callback_data="affiliate_withdraw")],
    ])


def format_affiliate_message(lang: str, stats: dict, ref_link: str) -> str:
    if lang == "tr":
        return (
            f"🤝 <b>Bizimle Kazan</b>\n\n"
            f"Kişisel bağlantını arkadaşlarınla paylaş. "
            f"Biri bağlantın üzerinden kredi satın aldığında ödemenin <b>%30'unu</b> kazanırsın!\n\n"
            f"👥 Davet edilen kullanıcılar: <b>{stats['invited']}</b>\n"
            f"⭐ Kredi satın alanlar: <b>{stats['buyers']} kişi</b>\n"
            f"💰 Toplam kazanılan: <b>{stats['earned']} ⭐</b>\n\n"
            f"📤 Ödenen: <b>{stats['paid_out']} ⭐</b>\n"
            f"💎 Çekilebilir: <b>{stats['available']} ⭐</b>\n\n"
            f"🔗 <b>Referans bağlantın:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"Bağlantını arkadaşlarına, gruplara veya sosyal medyaya gönder!"
        )
    elif lang == "ru":
        return (
            f"🤝 <b>Зарабатывай с нами</b>\n\n"
            f"Делись своей персональной ссылкой. "
            f"Когда кто-то по твоей ссылке купит кредиты — ты получишь <b>30%</b> от суммы!\n\n"
            f"👥 Приглашено пользователей: <b>{stats['invited']}</b>\n"
            f"⭐ Купили кредиты: <b>{stats['buyers']} чел</b>\n"
            f"💰 Заработано: <b>{stats['earned']} ⭐</b>\n\n"
            f"📤 Выплачено: <b>{stats['paid_out']} ⭐</b>\n"
            f"💎 Доступно к выводу: <b>{stats['available']} ⭐</b>\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"Отправьте её друзьям, в чаты, сторис или канал!"
        )
    elif lang == "fa":
        return (
            f"🤝 <b>با ما کسب درآمد کن</b>\n\n"
            f"لینک شخصی خود را به اشتراک بگذار. "
            f"هر بار که کسی از طریق لینک تو اعتبار بخرد، <b>۳۰٪</b> از مبلغ را دریافت می‌کنی!\n\n"
            f"👥 کاربران دعوت شده: <b>{stats['invited']}</b>\n"
            f"⭐ خریداران اعتبار: <b>{stats['buyers']} نفر</b>\n"
            f"💰 مجموع درآمد: <b>{stats['earned']} ⭐</b>\n\n"
            f"📤 پرداخت شده: <b>{stats['paid_out']} ⭐</b>\n"
            f"💎 قابل برداشت: <b>{stats['available']} ⭐</b>\n\n"
            f"🔗 <b>لینک رفرال شما:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"آن را با دوستان، گروه‌ها یا شبکه‌های اجتماعی به اشتراک بگذار!"
        )
    else:  # en
        return (
            f"🤝 <b>Earn With Us</b>\n\n"
            f"Share your personal link. "
            f"When someone buys credits through your link, you earn <b>30%</b> of the purchase!\n\n"
            f"👥 Invited users: <b>{stats['invited']}</b>\n"
            f"⭐ Users who purchased: <b>{stats['buyers']} people</b>\n"
            f"💰 Total earned: <b>{stats['earned']} ⭐</b>\n\n"
            f"📤 Paid out: <b>{stats['paid_out']} ⭐</b>\n"
            f"💎 Available to withdraw: <b>{stats['available']} ⭐</b>\n\n"
            f"🔗 <b>Your referral link:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"Share it with friends, groups, or social media!"
        )


def referral_notification(lang: str, stars_paid: int, reward: int) -> str:
    if lang == "tr":
        return f"🎉 Bağlantın üzerinden biri <b>{stars_paid} ⭐</b> değerinde kredi satın aldı!\nKazancın: <b>+{reward} ⭐</b>"
    elif lang == "ru":
        return f"🎉 По твоей ссылке кто-то купил кредиты на <b>{stars_paid} ⭐</b>!\nТвой заработок: <b>+{reward} ⭐</b>"
    elif lang == "fa":
        return f"🎉 کسی از طریق لینک تو <b>{stars_paid} ⭐</b> اعتبار خرید!\nدرآمد تو: <b>+{reward} ⭐</b>"
    else:
        return f"🎉 Someone bought <b>{stars_paid} ⭐</b> worth of credits through your link!\nYou earned: <b>+{reward} ⭐</b>"


async def notify_referrer(bot: Bot, referrer_id: int, stars_paid: int, reward: int):
    """Send notification to referrer when someone buys through their link."""
    try:
        user = await get_user(referrer_id)
        lang = user.get("language", "tr") if user else "tr"
        await bot.send_message(
            referrer_id,
            referral_notification(lang, stars_paid, reward)
        )
    except Exception:
        pass  # Don't crash if notification fails


@router.callback_query(lambda c: c.data == "go_affiliate")
async def show_affiliate(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get("language", "tr") if user else "tr"

    ref_code = await generate_referral_code(callback.from_user.id)
    ref_link = f"t.me/{BOT_USERNAME}?start=ref_{ref_code}"
    stats    = await get_referral_stats(callback.from_user.id)

    await callback.message.answer(
        format_affiliate_message(lang, stats, ref_link),
        reply_markup=affiliate_keyboard(lang)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "affiliate_refresh")
async def refresh_affiliate(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get("language", "tr") if user else "tr"

    ref_code = await generate_referral_code(callback.from_user.id)
    ref_link = f"t.me/{BOT_USERNAME}?start=ref_{ref_code}"
    stats    = await get_referral_stats(callback.from_user.id)

    try:
        await callback.message.edit_text(
            format_affiliate_message(lang, stats, ref_link),
            reply_markup=affiliate_keyboard(lang)
        )
    except Exception:
        await callback.message.answer(
            format_affiliate_message(lang, stats, ref_link),
            reply_markup=affiliate_keyboard(lang)
        )
    await callback.answer()


@router.callback_query(lambda c: c.data == "affiliate_withdraw")
async def withdraw_request(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    lang = user.get("language", "tr") if user else "tr"

    messages = {
        "tr": "💸 Para çekmek için aşağıdaki kişilerden biriyle iletişime geç:",
        "en": "💸 To withdraw your earnings, contact one of us:",
        "ru": "💸 Для вывода средств свяжитесь с нами:",
        "fa": "💸 برای برداشت درآمد با ما تماس بگیرید:",
    }
    await callback.message.answer(
        messages.get(lang, messages["en"]),
        reply_markup=CONTACT_KEYBOARD
    )
    await callback.answer()