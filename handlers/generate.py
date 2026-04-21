import urllib.parse
import aiohttp

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, URLInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import GenerateState
from keyboards import quality_keyboard, ratio_keyboard
from db import get_user, deduct_credits, log_generation
from texts import t

router = Router()

MODEL_MAP  = {"model_pro": "flux", "model_v2": "turbo"}
QUALITY_MAP = {"q_1k": 1024, "q_2k": 2048, "q_4k": 4096}
RATIO_MAP  = {"r_1_1": "1:1", "r_9_16": "9:16", "r_16_9": "16:9"}

CREDIT_COST = {
    ("model_pro", "q_1k"): 17,
    ("model_pro", "q_2k"): 17,
    ("model_pro", "q_4k"): 21,
    ("model_v2",  "q_1k"): 7,
    ("model_v2",  "q_2k"): 10,
    ("model_v2",  "q_4k"): 10,
}

async def get_lang(telegram_id: int) -> str:
    user = await get_user(telegram_id)
    return user.get("language", "tr") if user else "tr"

def after_gen_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_repeat"),  callback_data="repeat_gen"),
            InlineKeyboardButton(text=t(lang, "btn_restart"), callback_data="go_generate"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_show_balance"), callback_data="go_balance"),
        ]
    ])


async def do_generate(message: Message, state: FSMContext,
                      model_key: str, quality_key: str, ratio_key: str,
                      prompt: str, lang: str):
    """Core generation logic, reused by both first-time and repeat."""
    cost = CREDIT_COST.get((model_key, quality_key), 17)

    user = await get_user(message.from_user.id)
    if not user or user["credits"] < cost:
        balance = user["credits"] if user else 0
        await message.answer(
            t(lang, "no_credits_gen", cost=cost, balance=balance),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "btn_add_credits"), callback_data="go_balance")]
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

    wait_msg = await message.answer(t(lang, "generating"))

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}")

        new_balance = await deduct_credits(message.from_user.id, cost)
        await log_generation(message.from_user.id, model_key, quality_key, ratio_key, prompt, cost)

        await wait_msg.delete()
        await message.answer_photo(
            photo=URLInputFile(image_url),
            caption=t(lang, "done",
                      model=model_key, quality=quality_key,
                      ratio=ratio, prompt=prompt,
                      cost=cost, balance=new_balance),
            reply_markup=after_gen_keyboard(lang)
        )

    except ValueError:
        await wait_msg.delete()
        await message.answer(t(lang, "no_credits_gen", cost=cost, balance=0))
    except Exception as e:
        await wait_msg.delete()
        await message.answer(t(lang, "gen_failed", error=str(e)))
    finally:
        await state.clear()




@router.callback_query(GenerateState.choosing_model, F.data.startswith("model"))
async def choose_model(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    await state.update_data(model=callback.data)
    await callback.message.answer(t(lang, "choose_quality"), reply_markup=quality_keyboard())
    await state.set_state(GenerateState.choosing_quality)
    await callback.answer()


@router.callback_query(GenerateState.choosing_quality, F.data.startswith("q_"))
async def choose_quality(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    await state.update_data(quality=callback.data)
    await callback.message.answer(t(lang, "choose_ratio"), reply_markup=ratio_keyboard())
    await state.set_state(GenerateState.choosing_ratio)
    await callback.answer()


@router.callback_query(GenerateState.choosing_ratio, F.data.startswith("r_"))
async def choose_ratio(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    data = await state.get_data()
    await state.update_data(ratio=callback.data)
    cost = CREDIT_COST.get((data.get("model"), data.get("quality")), 17)
    await callback.message.answer(t(lang, "prompt_cost", cost=cost))
    await state.set_state(GenerateState.waiting_prompt)
    await callback.answer()


@router.message(GenerateState.waiting_prompt)
async def get_prompt(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    # Save last generation data for repeat
    await state.update_data(last_prompt=message.text)
    await do_generate(
        message, state,
        model_key=data.get("model"),
        quality_key=data.get("quality"),
        ratio_key=data.get("ratio"),
        prompt=message.text,
        lang=lang
    )




@router.callback_query(lambda c: c.data == "repeat_gen")
async def repeat_generation(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    data = await state.get_data()

    model_key   = data.get("model")
    quality_key = data.get("quality")
    ratio_key   = data.get("ratio")
    prompt      = data.get("last_prompt")

    if not all([model_key, quality_key, ratio_key, prompt]):
        await callback.answer("Session expired. Please start over.", show_alert=True)
        return

    await callback.answer()
    await do_generate(callback.message, state, model_key, quality_key, ratio_key, prompt, lang)