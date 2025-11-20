import os
import re
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from django.utils import timezone
from django.db import transaction

from users.models import Users, TelegramAccount
from departments.models import Admins, TelegramAdmin
from core_support.models import Neighborhood


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher (will be set in setup_bot)
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None


# FSM States for registration flow
class RegistrationStates(StatesGroup):
    choose_language = State()
    ask_fullname = State()
    ask_phone = State()
    ask_neighborhood = State()
    ask_full_location = State()
    saving_to_db = State()


# Multilingual messages
MESSAGES = {
    'uz': {
        'greeting': (
            "Assalomu alaykum!\n\n"
            "Men Asadbek yordamchi botman.\n"
            "Sizga ro'yxatdan o'tishda va kerakli xizmatlarni olishda yordam beraman.\n\n"
            "Davom etishdan oldin, iltimos, tilni tanlang."
        ),
        'language_selected': (
            "Ajoyib! Endi sizni yaxshiroq tanib olishim uchun bir nechta ma'lumot kerak bo'ladi.\n\n"
            "Iltimos, to'liq ismingizni yozing (Familiya Ism Sharif)."
        ),
        'ask_phone': (
            "Rahmat! Endi iltimos, telefon raqamingizni yuboring.\n"
            "Masalan: +998 90 123 45 67"
        ),
        'phone_received': "Qabul qilindi!\n\nEndi mahallangizni tanlang.",
        'ask_location': (
            "Ajoyib! Endi oxirgi qadam — iltimos, manzilingizni to'liq yozib yuboring.\n"
            "Masalan: Yunusobod, 12-daha, 45-uy"
        ),
        'saving': "Rahmat! Barcha ma'lumotlar to'plandi.\n\nBir oz kuting…",
        'success': "🎉 Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\nEndi sizga qanday yordam bera olaman?",
        'phone_invalid': "Iltimos, to'g'ri telefon raqamini kiriting.\nMasalan: +998 90 123 45 67",
        'error': "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
    },
    'ru': {
        'greeting': (
            "Здравствуйте!\n\n"
            "Я помощник-бот Асадбек.\n"
            "Я помогу вам зарегистрироваться и получить необходимые услуги.\n\n"
            "Перед продолжением, пожалуйста, выберите язык."
        ),
        'language_selected': (
            "Отлично! Теперь мне понадобится несколько данных, чтобы лучше узнать вас.\n\n"
            "Пожалуйста, напишите ваше полное имя (Фамилия Имя Отчество)."
        ),
        'ask_phone': (
            "Спасибо! Теперь, пожалуйста, отправьте ваш номер телефона.\n"
            "Например: +998 90 123 45 67"
        ),
        'phone_received': "Принято!\n\nТеперь выберите ваш район.",
        'ask_location': (
            "Отлично! Теперь последний шаг — пожалуйста, напишите ваш полный адрес.\n"
            "Например: Юнусабад, 12-дом, 45-квартира"
        ),
        'saving': "Спасибо! Все данные собраны.\n\nПодождите немного…",
        'success': "🎉 Регистрация успешно завершена!\n\nЧем я могу вам помочь?",
        'phone_invalid': "Пожалуйста, введите правильный номер телефона.\nНапример: +998 90 123 45 67",
        'error': "Произошла ошибка. Пожалуйста, попробуйте снова.",
    },
    'en': {
        'greeting': (
            "Hello!\n\n"
            "I am Asadbek assistant bot.\n"
            "I will help you register and get the services you need.\n\n"
            "Before continuing, please select a language."
        ),
        'language_selected': (
            "Great! Now I need some information to get to know you better.\n\n"
            "Please write your full name (Last Name First Name Middle Name)."
        ),
        'ask_phone': (
            "Thank you! Now please send your phone number.\n"
            "Example: +998 90 123 45 67"
        ),
        'phone_received': "Received!\n\nNow select your neighborhood.",
        'ask_location': (
            "Great! Now the final step — please write your full address.\n"
            "Example: Yunusobod, Building 12, Apartment 45"
        ),
        'saving': "Thank you! All data has been collected.\n\nPlease wait a moment…",
        'success': "🎉 Registration completed successfully!\n\nHow can I help you?",
        'phone_invalid': "Please enter a valid phone number.\nExample: +998 90 123 45 67",
        'error': "An error occurred. Please try again.",
    },
}


def validate_phone_number(phone: str) -> bool:
    """Validate Uzbek phone number format."""
    # Remove spaces and check if starts with +998
    phone_clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not phone_clean.startswith('+998'):
        return False
    
    # Check if remaining digits are valid (should be 9 digits after +998)
    digits = phone_clean[4:]
    if not digits.isdigit() or len(digits) != 9:
        return False
    
    # Check if first digit after country code is valid (should be 9 for mobile)
    if not digits.startswith('9'):
        return False
    
    return True


def get_language_keyboard():
    """Create language selection keyboard."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿 Oʻzbek"), KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇬🇧 English")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


async def get_neighborhood_keyboard(language: str = 'uz'):
    """Create neighborhood selection keyboard."""
    neighborhoods = Neighborhood.objects.filter(is_active=True).order_by('name_uz')
    
    builder = InlineKeyboardBuilder()
    
    if not neighborhoods.exists():
        # Return empty keyboard if no neighborhoods exist
        return builder.as_markup()
    
    # Add 2 buttons per row
    buttons = []
    for neighborhood in neighborhoods:
        # Use name based on language
        if language == 'ru' and neighborhood.name_ru:
            name = neighborhood.name_ru
        elif language == 'en' and neighborhood.name_en:
            name = neighborhood.name_en
        else:
            name = neighborhood.name_uz
        
        buttons.append(
            InlineKeyboardButton(
                text=name,
                callback_data=f"neighborhood_{neighborhood.neighborhood_uuid}"
            )
        )
    
    # Arrange buttons in rows of 2
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        builder.row(*row)
    
    return builder.as_markup()


async def universal_pre_check(message: Message, state: FSMContext) -> tuple[bool, Optional[Users], Optional[Admins]]:
    """
    Universal pre-check: Look up user in Users and Admins tables.
    Returns: (is_new_user, user_instance, admin_instance)
    """
    telegram_chat_id = message.from_user.id
    
    # Check in TelegramAccount (linked to Users)
    try:
        telegram_account = TelegramAccount.objects.select_related('system_user').get(
            telegram_chat_id=telegram_chat_id,
            system_user__is_deleted=False
        )
        user = telegram_account.system_user
        
        # Update last interaction
        telegram_account.last_interaction = timezone.now()
        telegram_account.save()
        user.telegram_last_interaction = timezone.now()
        user.save()
        
        return False, user, None  # Existing user
    except TelegramAccount.DoesNotExist:
        pass
    
    # Check in TelegramAdmin (linked to Admins)
    try:
        telegram_admin = TelegramAdmin.objects.select_related('system_admin').get(
            telegram_chat_id=telegram_chat_id
        )
        admin = telegram_admin.system_admin
        
        # Update last interaction
        telegram_admin.last_interaction = timezone.now()
        telegram_admin.save()
        admin.last_telegram_interaction = timezone.now()
        admin.save()
        
        return False, None, admin  # Existing admin
    except TelegramAdmin.DoesNotExist:
        pass
    
    # New user - start onboarding
    return True, None, None


async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    is_new, user, admin = await universal_pre_check(message, state)
    
    if not is_new:
        # User or admin exists - show main menu
        if user:
            await message.answer(
                f"Assalomu alaykum, {user.full_name or 'foydalanuvchi'}!\n\n"
                "Sizga qanday yordam bera olaman?",
                reply_markup=ReplyKeyboardRemove()
            )
        elif admin:
            await message.answer(
                f"Assalomu alaykum, {admin.full_name}!\n\n"
                "Admin paneliga xush kelibsiz.",
                reply_markup=ReplyKeyboardRemove()
            )
        await state.clear()
        return
    
    # New user - start registration
    await message.answer(
        MESSAGES['uz']['greeting'],
        reply_markup=get_language_keyboard()
    )
    await state.set_state(RegistrationStates.choose_language)


async def process_language_selection(message: Message, state: FSMContext):
    """Handle language selection."""
    text = message.text.lower()
    
    # Map user input to language codes
    language_map = {
        "🇺🇿 oʻzbek": 'uz',
        "o'zbek": 'uz',
        "uzbek": 'uz',
        "🇷🇺 русский": 'ru',
        "русский": 'ru',
        "russian": 'ru',
        "🇬🇧 english": 'en',
        "english": 'en',
        "ingliz": 'en',
    }
    
    language = None
    for key, lang in language_map.items():
        if key in text:
            language = lang
            break
    
    if not language:
        # Default to Uzbek if unclear
        language = 'uz'
    
    # Store language in FSM
    await state.update_data(language=language)
    
    # Store telegram user info
    await state.update_data(
        telegram_user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name or '',
    )
    
    # Send next message in selected language
    await message.answer(
        MESSAGES[language]['language_selected'],
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(RegistrationStates.ask_fullname)


async def process_fullname(message: Message, state: FSMContext):
    """Handle full name input."""
    full_name = message.text.strip()
    
    if len(full_name) < 3:
        data = await state.get_data()
        language = data.get('language', 'uz')
        await message.answer(
            MESSAGES[language].get('error', MESSAGES['uz']['error'])
        )
        return
    
    # Store full name
    await state.update_data(full_name=full_name)
    
    # Ask for phone
    data = await state.get_data()
    language = data.get('language', 'uz')
    await message.answer(MESSAGES[language]['ask_phone'])
    await state.set_state(RegistrationStates.ask_phone)


async def process_phone(message: Message, state: FSMContext):
    """Handle phone number input."""
    phone = message.text.strip()
    
    # Validate phone number
    if not validate_phone_number(phone):
        data = await state.get_data()
        language = data.get('language', 'uz')
        await message.answer(MESSAGES[language]['phone_invalid'])
        return
    
    # Store phone number
    await state.update_data(phone_number=phone)
    
    # Ask for neighborhood
    data = await state.get_data()
    language = data.get('language', 'uz')
    keyboard = await get_neighborhood_keyboard(language)
    
    await message.answer(
        MESSAGES[language]['phone_received'],
        reply_markup=keyboard
    )
    await state.set_state(RegistrationStates.ask_neighborhood)


async def process_neighborhood(callback: CallbackQuery, state: FSMContext):
    """Handle neighborhood selection."""
    neighborhood_uuid = callback.data.replace("neighborhood_", "")
    
    try:
        neighborhood = Neighborhood.objects.get(neighborhood_uuid=neighborhood_uuid)
    except Neighborhood.DoesNotExist:
        data = await state.get_data()
        language = data.get('language', 'uz')
        await callback.answer(MESSAGES[language]['error'], show_alert=True)
        return
    
    # Store neighborhood UUID and name
    await state.update_data(
        neighborhood_uuid=neighborhood_uuid,
        neighborhood_name=neighborhood.name_uz
    )
    
    # Ask for location
    data = await state.get_data()
    language = data.get('language', 'uz')
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(MESSAGES[language]['ask_location'])
    await callback.answer()
    await state.set_state(RegistrationStates.ask_full_location)


async def process_location(message: Message, state: FSMContext):
    """Handle full location input."""
    location = message.text.strip()
    
    if len(location) < 5:
        data = await state.get_data()
        language = data.get('language', 'uz')
        await message.answer(MESSAGES[language].get('error', MESSAGES['uz']['error']))
        return
    
    # Store location
    await state.update_data(full_location=location)
    
    # Show saving message
    data = await state.get_data()
    language = data.get('language', 'uz')
    await message.answer(MESSAGES[language]['saving'])
    
    # Move to saving state
    await state.set_state(RegistrationStates.saving_to_db)
    
    # Save to database
    await save_user_to_database(message, state)


async def save_user_to_database(message: Message, state: FSMContext):
    """Save all collected data to database."""
    try:
        data = await state.get_data()
        language = data.get('language', 'uz')
        
        with transaction.atomic():
            # Create or get Users record
            phone_number = data.get('phone_number')
            full_name = data.get('full_name')
            
            # Check if user with this phone already exists
            try:
                user = Users.objects.get(phone_number=phone_number, is_deleted=False)
            except Users.DoesNotExist:
                # Create new user
                user = Users.objects.create(
                    full_name=full_name,
                    phone_number=phone_number,
                    is_active=True,
                    verified=False,
                )
            
            # Create TelegramAccount linked to user
            telegram_chat_id = data.get('telegram_user_id')
            
            # Check if TelegramAccount already exists (edge case)
            telegram_account, created = TelegramAccount.objects.get_or_create(
                telegram_chat_id=telegram_chat_id,
                defaults={
                    'system_user': user,
                    'username': data.get('username'),
                    'full_name': f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                    'phone_number': phone_number,
                    'is_bot': False,
                    'neighborhood': data.get('neighborhood_name'),
                    'language_code': language,
                    'language_preference': language,
                    'location': data.get('full_location'),
                    'last_interaction': timezone.now(),
                }
            )
            
            if not created:
                # Update existing account
                telegram_account.username = data.get('username')
                telegram_account.full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                telegram_account.phone_number = phone_number
                telegram_account.neighborhood = data.get('neighborhood_name')
                telegram_account.language_code = language
                telegram_account.language_preference = language
                telegram_account.location = data.get('full_location')
                telegram_account.last_interaction = timezone.now()
                telegram_account.save()
            
            # Update user's telegram_last_interaction
            user.telegram_last_interaction = timezone.now()
            user.save()
        
        # Success message
        await message.answer(MESSAGES[language]['success'])
        
        # Clear FSM state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error saving user to database: {e}", exc_info=True)
        data = await state.get_data()
        language = data.get('language', 'uz')
        await message.answer(MESSAGES[language]['error'])
        await state.clear()


# Handle any message when not in registration flow (for existing users)
async def handle_regular_message(message: Message, state: FSMContext):
    """Handle regular messages - check if user needs registration."""
    current_state = await state.get_state()
    
    # If not in any state, do pre-check
    if current_state is None:
        is_new, user, admin = await universal_pre_check(message, state)
        
        if is_new:
            # New user - start registration
            await message.answer(
                MESSAGES['uz']['greeting'],
                reply_markup=get_language_keyboard()
            )
            await state.set_state(RegistrationStates.choose_language)
        else:
            # Existing user - handle their message normally
            # TODO: Implement main menu handlers
            await message.answer("Sizga qanday yordam bera olaman?")
    else:
        # In a state but message doesn't match - ignore or handle error
        pass


def setup_bot(token: str):
    """Initialize bot and dispatcher with token."""
    global bot, dp
    
    bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Register handlers
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(process_language_selection, RegistrationStates.choose_language)
    dp.message.register(process_fullname, RegistrationStates.ask_fullname)
    dp.message.register(process_phone, RegistrationStates.ask_phone)
    dp.callback_query.register(process_neighborhood, RegistrationStates.ask_neighborhood, F.data.startswith("neighborhood_"))
    dp.message.register(process_location, RegistrationStates.ask_full_location)
    dp.message.register(handle_regular_message)
    
    return bot, dp


async def start_bot():
    """Start the bot."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    
    setup_bot(token)
    
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    import django
    import os
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()
    
    asyncio.run(start_bot())
