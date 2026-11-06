import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions
)

import database as db

# ----------------------------------------------------------------------------
# КОНФИГУРАЦИЯ
# ----------------------------------------------------------------------------
BOT_TOKEN = "9135099122:AAGK0PZcwlERx5DsSwFlyx_i9ayTiR6fna8"  # ← ВСТАВЬТЕ ВАШ ТОКЕН
GUARANTOR_MENTION = "@giftsofferbots"  # Ваш юзернейм

GIFT_URL_RE = re.compile(r"^(https?://t\.me/nft/(?P<name>[A-Za-z]+)-(?P<number>\d+))")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

def format_number(number: str) -> str:
    try:
        return f"{int(number):,}"
    except ValueError:
        return number

# --- КЛАВИАТУРЫ ---
def offer_card_keyboard(deal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Отклонить", callback_data=f"reject:{deal_id}"),
                InlineKeyboardButton(text="Принять", callback_data=f"accept:{deal_id}"),
            ]
        ]
    )

def seller_accepted_keyboard(deal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Как передать", callback_data=f"howto:{deal_id}"),
                InlineKeyboardButton(text="Подтвердить", callback_data=f"confirm:{deal_id}"),
            ]
        ]
    )

# ----------------------------------------------------------------------------
# ИНЛАЙН-РЕЖИМ (Создание карточки)
# ----------------------------------------------------------------------------
@router.inline_query()
async def inline_handler(query: InlineQuery):
    text = query.query.strip()
    
    if not text or len(text.split()) < 2:
        await query.answer([], switch_pm_text="Укажите ссылку и цену", switch_pm_parameter="start")
        return

    parts = text.split()
    gift_url = parts[0]
    price_str = parts[1]

    match = GIFT_URL_RE.match(gift_url)
    if not match or not price_str.isdigit():
        await query.answer([], switch_pm_text="Неверный формат. Пример: https://t.me/nft/Ice-1 2000", switch_pm_parameter="start")
        return

    gift_name_raw = match.group("name")
    gift_number = match.group("number")
    price = int(price_str)

    buyer_id = query.from_user.id
    buyer_name = query.from_user.full_name
    
    deal_id = await db.create_deal(
        seller_id=buyer_id, 
        seller_name=buyer_name,
        gift_url=gift_url,
        gift_name=gift_name_raw,
        gift_number=gift_number,
        price=price,
    )

    gift_number_formatted = format_number(gift_number)
    
    caption = (
        f"Пользователь <b>{buyer_name}</b> предлагает Вам "
        f"<b>{price} ⭐</b> за подарок "
        f"<b>{gift_name_raw} #{gift_number_formatted}</b>.\n\n"
        f"{gift_url}\n\n"
        f"⏳ Предложение действует еще <b>6ч 00м</b>."
    )

    await query.answer(
        results=[
            InlineQueryResultArticle(
                id=str(deal_id),
                title=f"Продать {gift_name_raw} #{gift_number_formatted} за {price} ⭐",
                description="Нажмите, чтобы отправить оффер в чат",
                input_message_content=InputTextMessageContent(
                    message_text=caption,
                    link_preview_options=LinkPreviewOptions(
                        url=gift_url,
                        prefer_large_media=True,
                        show_above_text=False
                    )
                ),
                reply_markup=offer_card_keyboard(deal_id),
            )
        ],
        cache_time=1,
    )

# ----------------------------------------------------------------------------
# ОБРАБОТКА КНОПОК
# ----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("accept:"))
async def cb_accept(callback: CallbackQuery) -> None:
    deal_id = int(callback.data.split(":")[1])
    deal = await db.get_deal(deal_id)

    if not deal or deal["status"] != "created":
        await callback.answer("Оффер уже неактуален.", show_alert=True)
        return

    # ПРОВЕРКА: создатель оффера не может нажать "Принять"
    if callback.from_user.id == deal["seller_id"]:
        await callback.answer("❌ Вы не можете принять собственный оффер.", show_alert=True)
        return

    await db.accept_deal(deal_id, callback.from_user.id, callback.from_user.full_name)

    gift_number_formatted = format_number(deal["gift_number"])
    
    accepted_text = (
        f"📦 Подарок: <b>{deal['gift_name']} #{gift_number_formatted}</b> успешно продан!\n\n"
        f"Отправьте подарок на официальный аккаунт сделки {GUARANTOR_MENTION}, "
        f"чтобы получить <b>{deal['price']} ⭐</b>.\n\n"
        f"<a href='{deal['gift_url']}'>&#8203;</a>"
    )
    
    try:
        await bot.edit_message_caption(
            inline_message_id=callback.inline_message_id,
            caption=accepted_text,
            reply_markup=seller_accepted_keyboard(deal_id)
        )
    except Exception as e:
        logger.error(f"Ошибка редактирования caption: {e}")

    await callback.answer(
        f"Ваш оффер принят! Передайте подарок на {GUARANTOR_MENTION}, чтобы получить {deal['price']} ⭐.",
        show_alert=True,
    )

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(callback: CallbackQuery) -> None:
    deal_id = int(callback.data.split(":")[1])
    deal = await db.get_deal(deal_id)

    if not deal or deal["status"] != "created":
        await callback.answer("Оффер уже неактуален.", show_alert=True)
        return

    # ПРОВЕРКА: создатель оффера не может нажать "Отклонить"
    if callback.from_user.id == deal["seller_id"]:
        await callback.answer("❌ Вы не можете отклонить собственный оффер.", show_alert=True)
        return

    await db.reject_deal(deal_id)
    reject_text = (
        f"❌ Оффер на подарок <b>{deal['gift_name']} #{format_number(deal['gift_number'])}</b> отклонён.\n\n"
        f"<a href='{deal['gift_url']}'>&#8203;</a>"
    )
    
    try:
        await bot.edit_message_caption(
            inline_message_id=callback.inline_message_id,
            caption=reject_text
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
            
    await callback.answer("Оффер отклонён.", show_alert=True)

@router.callback_query(F.data.startswith("howto:"))
async def cb_howto(callback: CallbackQuery) -> None:
    deal_id = int(callback.data.split(":")[1])
    deal = await db.get_deal(deal_id)

    if not deal:
        await callback.answer("Сделка не найдена.", show_alert=True)
        return

    await db.set_waiting_transfer(deal_id)
    gift_number_formatted = format_number(deal["gift_number"])
    
    howto_text = (
        f"🎁 Сделка #{deal_id} подтверждена.\n\n"
        f"Подарок <b>{deal['gift_name']} #{gift_number_formatted}</b> зарезервирован. "
        f"Чтобы получить <b>{deal['price']} ⭐</b>, отправьте его на официальный аккаунт сделки {GUARANTOR_MENTION}.\n\n"
        f"<b>Как передать подарок:</b>\n"
        f"1. Откройте <i>Профиль → Подарки</i> в Telegram.\n"
        f"2. Выберите <b>{deal['gift_name']} #{gift_number_formatted}</b> в своём списке.\n"
        f"3. Нажмите «Передать», затем укажите получателя {GUARANTOR_MENTION}.\n"
        f"4. Проверьте данные и подтвердите отправку.\n\n"
        f"<b>Автоматическое завершение сделки</b>\n"
        f"После подтверждения передачи NFT-подарка на {GUARANTOR_MENTION} система обновит статус сделки, а сумма <b>{deal['price']} ⭐</b> станет доступна продавцу.\n\n"
        f"<a href='{deal['gift_url']}'>&#8203;</a>"
    )

    try:
        await bot.edit_message_caption(
            inline_message_id=callback.inline_message_id,
            caption=howto_text,
            reply_markup=seller_accepted_keyboard(deal_id)
        )
    except Exception as e:
        logger.error(f"Ошибка при показе инструкции: {e}")

    await callback.answer()

@router.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(callback: CallbackQuery) -> None:
    deal_id = int(callback.data.split(":")[1])
    deal = await db.get_deal(deal_id)

    if not deal:
        await callback.answer("Сделка не найдена.", show_alert=True)
        return

    await callback.answer(
        f"❌ Передача пока не подтверждена.\n\n"
        f"Отправьте подарок на официальный аккаунт сделки {GUARANTOR_MENTION}. "
        f"После подтверждения получения станет доступна оплата {deal['price']} ⭐.",
        show_alert=True,
    )

# ----------------------------------------------------------------------------
# ЗАПУСК
# ----------------------------------------------------------------------------
async def main() -> None:
    await db.init_db()
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")