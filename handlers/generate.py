import urllib.parse
import aiohttp

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, URLInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import GenerateState
from keyboards import quality_keyboard, ratio_keyboard
from db import get_user, deduct_credits, log_generation

router = Router()

MODEL_MAP = {
    "model_pro": "flux",
    "model_v2":  "turbo",
}
QUALITY_MAP = {
    "q_1k": 1024,
    "q_2k": 2048,
    "q_4k": 4096,
}
RATIO_MAP = {
    "r_1_1":  "1:1",
    "r_9_16": "9:16",
    "r_16_9": "16:9",
}


CREDIT_COST = {
    ("model_pro", "q_1k"): 17,
    ("model_pro", "q_2k"): 17,
    ("model_pro", "q_4k"): 21,
    ("model_v2",  "q_1k"): 7,
    ("model_v2",  "q_2k"): 10,
    ("model_v2",  "q_4k"): 10,
}

def after_generation_keyboard(prompt: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔁 Repeat Prompt", callback_data="repeat_prompt"),
            InlineKeyboardButton(text="🔄 Start Over", callback_data="go_generate"),
        ]
    ])


@router.callback_query(GenerateState.choosing_model, F.data.startswith("model"))
async def choose_model(callback: CallbackQuery, state: FSMContext):
    await state.update_data(model=callback.data)
    await callback.message.answer("Choose quality:", reply_markup=quality_keyboard())
    await state.set_state(GenerateState.choosing_quality)
    await callback.answer()


@router.callback_query(GenerateState.choosing_quality, F.data.startswith("q_"))
async def choose_quality(callback: CallbackQuery, state: FSMContext):
    await state.update_data(quality=callback.data)
    await callback.message.answer("Choose aspect ratio:", reply_markup=ratio_keyboard())
    await state.set_state(GenerateState.choosing_ratio)
    await callback.answer()


@router.callback_query(GenerateState.choosing_ratio, F.data.startswith("r_"))
async def choose_ratio(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    model_key   = data.get("model")
    quality_key = callback.data.replace("r_", "q_")  # temp trick — we store ratio separately
    ratio_key   = callback.data
    await state.update_data(ratio=ratio_key)


    quality_stored = data.get("quality")
    cost = CREDIT_COST.get((model_key, quality_stored), 17)

    await callback.message.answer(
        f"✏️ Alright, write your prompt.\n"
        f"💰 This generation will cost <b>{cost} credits</b>."
    )
    await state.set_state(GenerateState.waiting_prompt)
    await callback.answer()


@router.message(GenerateState.waiting_prompt)
async def get_prompt(message: Message, state: FSMContext):
    data = await state.get_data()

    model_key   = data.get("model")
    quality_key = data.get("quality")
    ratio_key   = data.get("ratio")
    prompt      = message.text

    cost = CREDIT_COST.get((model_key, quality_key), 17)

    # Check credits BEFORE generating
    user = await get_user(message.from_user.id)
    if not user or user["credits"] < cost:
        await message.answer(
            f"❌ <b>Insufficient credits!</b>\n\n"
            f"This generation costs <b>{cost} credits</b>.\n"
            f"Your balance: <b>{user['credits'] if user else 0} credits</b>.\n\n"
            f"Please top up your balance to continue.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Top Up Balance", callback_data="go_balance")]
            ])
        )
        await state.clear()
        return

    model  = MODEL_MAP.get(model_key, "flux")
    size   = QUALITY_MAP.get(quality_key, 1024)
    ratio  = RATIO_MAP.get(ratio_key, "1:1")

    if ratio == "1:1":
        width, height = size, size
    elif ratio == "16:9":
        width, height = size, int(size * 9 / 16)
    elif ratio == "9:16":
        width, height = int(size * 9 / 16), size
    else:
        width, height = size, size

    encoded_prompt = urllib.parse.quote(prompt)
    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?model={model}&width={width}&height={height}&nologo=true&seed={hash(prompt) % 99999}"
    )

    wait_msg = await message.answer("⏳ Generating your image, please wait...")

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    raise Exception(f"Service returned status {resp.status}")

        # Deduct credits only after successful generation
        new_balance = await deduct_credits(message.from_user.id, cost)

        # Log to DB
        await log_generation(
            telegram_id=message.from_user.id,
            model=model_key,
            quality=quality_key,
            ratio=ratio_key,
            prompt=prompt,
            credits_spent=cost
        )

        await wait_msg.delete()
        await message.answer_photo(
            photo=URLInputFile(image_url),
            caption=(
                f"✅ <b>Done!</b>\n"
                f"<b>Model:</b> {model_key}\n"
                f"<b>Quality:</b> {quality_key}\n"
                f"<b>Ratio:</b> {ratio}\n"
                f"<b>Prompt:</b> {prompt}\n\n"
                f"💰 Credits spent: <b>{cost}</b> | Remaining: <b>{new_balance}</b>"
            ),
            reply_markup=after_generation_keyboard(prompt)
        )

    except ValueError:
        await wait_msg.delete()
        await message.answer("❌ Insufficient credits. Please top up your balance.")

    except Exception as e:
        await wait_msg.delete()
        await message.answer(f"❌ Generation failed: {e}\n\nTry again with /start")

    finally:
        await state.clear()


@router.callback_query(lambda c: c.data == "repeat_prompt")
async def repeat_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Choose your model:", reply_markup=__import__('keyboards').model_keyboard())
    await state.set_state(GenerateState.choosing_model)
    await callback.answer()