import asyncio
import aiohttp
import json
import os

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, URLInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from states import GenerateState
from keyboards import quality_keyboard, ratio_keyboard
from db import get_user, deduct_credits, log_generation
from texts import t

router = Router()

KIE_API_KEY  = os.getenv("KIE_API_KEY")
KIE_BASE     = "https://api.kie.ai"
KIE_UPLOAD   = "https://kieai.redpandaai.co"

MODEL_MAP = {
    "model_pro": "nano-banana-pro",
    "model_v2":  "google/nano-banana",
}
QUALITY_MAP = {
    "q_1k": "1K",
    "q_2k": "2K",
    "q_4k": "4K",
}
RATIO_MAP = {
    "r_1_1":  "1:1",
    "r_9_16": "9:16",
    "r_16_9": "16:9",
}
CREDIT_COST = {
    ("model_pro", "q_1k"): 12,
    ("model_pro", "q_2k"): 12,
    ("model_pro", "q_4k"): 16,
    ("model_v2",  "q_1k"): 6,
    ("model_v2",  "q_2k"): 8,
    ("model_v2",  "q_4k"): 12,
}

HEADERS = {
    "Authorization": f"Bearer {KIE_API_KEY}",
    "Content-Type": "application/json",
}


SUPPORTS_IMAGE = {"model_pro"}


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


def skip_image_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "skip_image"), callback_data="skip_image")]
    ])


async def upload_image_to_kie(image_bytes: bytes, filename: str = "image.jpg") -> str:
    """Uploads image bytes to KieAI File Upload API, returns fileUrl."""
    upload_headers = {"Authorization": f"Bearer {KIE_API_KEY}"}
    data = aiohttp.FormData()
    data.add_field("file", image_bytes, filename=filename, content_type="image/jpeg")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{KIE_UPLOAD}/api/upload/file-stream",
            headers=upload_headers,
            data=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            result = await resp.json()
            if not result.get("success") and result.get("code") != 200:
                raise Exception(f"Upload failed: {result.get('msg', 'unknown')}")
            return result["data"]["fileUrl"]


async def create_kie_task(model: str, prompt: str, ratio: str,
                          quality: str, image_url: str = None) -> str:
    """Submits generation task, returns taskId."""
    if model == "nano-banana-pro":
        input_body = {
            "prompt": prompt,
            "aspect_ratio": ratio,
            "resolution": quality,
            "output_format": "png",
            "image_input": [image_url] if image_url else [],
        }
    else:
        input_body = {
            "prompt": prompt,
            "image_size": ratio,
            "output_format": "png",
        }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{KIE_BASE}/api/v1/jobs/createTask",
            headers=HEADERS,
            json={"model": model, "input": input_body},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            data = await resp.json()
            if data.get("code") != 200:
                raise Exception(f"KieAI error: {data.get('msg', 'unknown')}")
            return data["data"]["taskId"]


async def poll_kie_task(task_id: str, timeout: int = 300) -> str:

    deadline = asyncio.get_event_loop().time() + timeout
    async with aiohttp.ClientSession() as session:
        while asyncio.get_event_loop().time() < deadline:
            async with session.get(
                f"{KIE_BASE}/api/v1/jobs/recordInfo",
                headers=HEADERS,
                params={"taskId": task_id},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                if data.get("code") != 200:
                    raise Exception(f"Poll error: {data.get('msg')}")
                task  = data.get("data", {})
                state = task.get("state")
                if state == "success":
                    result_json = task.get("resultJson", "{}")
                    result = json.loads(result_json)
                    urls = result.get("resultUrls", [])
                    if urls:
                        return urls[0]
                    raise Exception("Task succeeded but no image URL found")
                elif state == "fail":
                    raise Exception(f"Task failed: {task.get('failMsg', 'unknown')}")
            await asyncio.sleep(3)
    raise Exception("Generation timed out after 5 minutes")


async def do_generate(message: Message, state: FSMContext,
                      model_key: str, quality_key: str, ratio_key: str,
                      prompt: str, lang: str, user_id: int = None,
                      image_url: str = None):
    uid  = user_id or message.from_user.id
    cost = CREDIT_COST.get((model_key, quality_key), 17)

    user = await get_user(uid)
    if not user or user["credits"] < cost:
        balance = user["credits"] if user else 0
        await message.answer(
            t(lang, "no_credits_gen", cost=cost, balance=balance),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "btn_add_credits"), callback_data="go_balance")]
            ])
        )
        await state.set_state(None)
        return

    model   = MODEL_MAP.get(model_key, "google/nano-banana")
    quality = QUALITY_MAP.get(quality_key, "1K")
    ratio   = RATIO_MAP.get(ratio_key, "1:1")

    wait_msg = await message.answer(t(lang, "generating"))

    try:
        task_id   = await create_kie_task(model, prompt, ratio, quality, image_url)
        image_out = await poll_kie_task(task_id)

        new_balance = await deduct_credits(uid, cost)
        await log_generation(uid, model_key, quality_key, ratio_key, prompt, cost)

        try:
            await wait_msg.delete()
        except Exception:
            pass

        caption = t(lang, "done",
                    model=model_key, quality=quality_key,
                    ratio=ratio, cost=cost, balance=new_balance)

        try:
            await message.answer_photo(
                photo=URLInputFile(image_out),
                caption=caption,
                reply_markup=after_gen_keyboard(lang)
            )
        except Exception:
            await message.answer_document(
                document=URLInputFile(image_out, filename="generated.png"),
                caption=caption,
                reply_markup=after_gen_keyboard(lang)
            )
        await state.set_state(None)

    except ValueError:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(t(lang, "no_credits_gen", cost=cost, balance=0))
        await state.set_state(None)
    except Exception as e:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(t(lang, "gen_failed", error=str(e)))
        await state.set_state(None)



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
    lang  = await get_lang(callback.from_user.id)
    data  = await state.get_data()
    await state.update_data(ratio=callback.data)
    cost  = CREDIT_COST.get((data.get("model"), data.get("quality")), 17)
    model_key = data.get("model")

    if model_key in SUPPORTS_IMAGE:

        await callback.message.answer(
            t(lang, "ask_image", cost=cost),
            reply_markup=skip_image_keyboard(lang)
        )
        await state.set_state(GenerateState.waiting_image)
    else:

        await callback.message.answer(t(lang, "prompt_cost", cost=cost))
        await state.set_state(GenerateState.waiting_prompt)

    await callback.answer()



@router.message(GenerateState.waiting_image, F.photo)
async def receive_image(message: Message, state: FSMContext, bot: Bot):
    lang = await get_lang(message.from_user.id)

    upload_msg = await message.answer(t(lang, "uploading_image"))

    try:

        photo = message.photo[-1]
        file  = await bot.get_file(photo.file_id)
        # Download as bytes
        file_bytes = await bot.download_file(file.file_path)
        image_bytes = file_bytes.read()


        kie_image_url = await upload_image_to_kie(image_bytes)
        await state.update_data(image_url=kie_image_url)

        try:
            await upload_msg.delete()
        except Exception:
            pass

        await message.answer(t(lang, "image_received"))
        await state.set_state(GenerateState.waiting_prompt)

    except Exception as e:
        try:
            await upload_msg.delete()
        except Exception:
            pass
        await message.answer(f"❌ {'Fotoğraf yüklenemedi' if lang == 'tr' else 'Failed to upload photo'}: {e}")
        await state.set_state(GenerateState.waiting_prompt)



@router.callback_query(lambda c: c.data == "skip_image")
async def skip_image(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    await state.update_data(image_url=None)
    data = await state.get_data()
    cost = CREDIT_COST.get((data.get("model"), data.get("quality")), 17)
    await callback.message.answer(t(lang, "prompt_cost", cost=cost))
    await state.set_state(GenerateState.waiting_prompt)
    await callback.answer()



@router.message(GenerateState.waiting_image, F.text)
async def image_state_text(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    await state.update_data(image_url=None, last_prompt=message.text)
    await do_generate(
        message, state,
        model_key=data.get("model"),
        quality_key=data.get("quality"),
        ratio_key=data.get("ratio"),
        prompt=message.text,
        lang=lang,
        user_id=message.from_user.id,
        image_url=None
    )


@router.message(GenerateState.waiting_prompt)
async def get_prompt(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    data = await state.get_data()
    await state.update_data(last_prompt=message.text)
    await do_generate(
        message, state,
        model_key=data.get("model"),
        quality_key=data.get("quality"),
        ratio_key=data.get("ratio"),
        prompt=message.text,
        lang=lang,
        user_id=message.from_user.id,
        image_url=data.get("image_url")
    )




@router.callback_query(lambda c: c.data == "repeat_gen")
async def repeat_generation(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    data = await state.get_data()

    model_key   = data.get("model")
    quality_key = data.get("quality")
    ratio_key   = data.get("ratio")
    prompt      = data.get("last_prompt")
    image_url   = data.get("image_url")

    if not all([model_key, quality_key, ratio_key, prompt]):
        await callback.answer(
            "Oturum süresi doldu, lütfen baştan başla." if lang == "tr"
            else "Session expired, please start over.",
            show_alert=True
        )
        return

    await callback.answer()
    await do_generate(
        callback.message, state,
        model_key, quality_key, ratio_key,
        prompt, lang,
        user_id=callback.from_user.id,
        image_url=image_url
    )


@router.callback_query(lambda c: c.data == "go_generate")
async def go_generate(callback: CallbackQuery, state: FSMContext):
    lang = await get_lang(callback.from_user.id)
    from keyboards import model_keyboard
    await state.clear()
    await callback.message.answer(t(lang, "choose_model"), reply_markup=model_keyboard())
    await state.set_state(GenerateState.choosing_model)
    await callback.answer()