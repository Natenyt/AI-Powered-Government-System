import os
import re
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
# F is a MagicFilter used to filter callback queries by their data
# Example: F.data.startswith("neighborhood_") filters callbacks where data starts with "neighborhood_"
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, ReplyKeyboardRemove, Contact

from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async

from departments.models import Admins, TelegramAdmin
from users.models import Users, TelegramAccount
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
            "👋 Assalomu alaykum!\n\n"
            "Men Asadbek — Napay tumani hokimligi tomonidan yaratilgan sun’iy intellekt yordamchisiman.\n\n"
            "🔤 Iltimos, tilni tanlang:"
        ),
        'language_selected': (
            "✅ Juda yaxshi!\n\n"
            "📝 Iltimos, to‘liq ismingizni kiriting:\n"
            "(Familiya Ism)"
        ),
        'ask_phone': (
            "✅ Rahmat!\n\n"
            "📱 Quyidagi tugmani bosib, telefon raqamingizni yuboring:"
        ),
        'phone_received': (
            "✅ Qabul qilindi!\n\n"
            "📍 Iltimos, mahallangizni tanlang:"
        ),
        'ask_location': (
            "✅ Mahalla tanlandi!\n\n"
            "🏠 Endi esa to‘liq manzilingizni kiriting:\n"
            "Masalan: Yunusobod, 12-mavze, 45-uy"
        ),
        'saving': "⏳ Ma’lumotlar saqlanmoqda. Iltimos, kuting...",
        'success': (
            "🎉 Ro‘yxatdan o‘tish muvaffaqiyatli yakunlandi!\n\n"
            "✅ Sizga qanday yordam bera olaman?"
        ),
        'phone_invalid': (
            "❌ Telefon raqami noto‘g‘ri.\n\n"
            "📱 Iltimos, quyidagi tugma orqali yuboring:"
        ),
        'error': (
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko‘ring."
        ),
        'back': '⬅️ Orqaga',
    },

    'ru': {
        'greeting': (
            "👋 Здравствуйте!\n\n"
            "Я — Asadbek, искусственный интеллект, созданный хокимиятом Напайского района.\n\n"
            "🔤 Пожалуйста, выберите язык:"
        ),
        'language_selected': (
            "✅ Отлично!\n\n"
            "📝 Пожалуйста, введите ваше полное имя:\n"
            "(Фамилия Имя)"
        ),
        'ask_phone': (
            "✅ Спасибо!\n\n"
            "📱 Нажмите кнопку ниже, чтобы отправить свой номер телефона:"
        ),
        'phone_received': (
            "✅ Принято!\n\n"
            "📍 Пожалуйста, выберите ваш махалля/район:"
        ),
        'ask_location': (
            "✅ Район выбран!\n\n"
            "🏠 Теперь введите ваш полный адрес:\n"
            "Например: Юнусабад, 12-дом, 45-квартира"
        ),
        'saving': "⏳ Сохраняем ваши данные. Пожалуйста, подождите...",
        'success': (
            "🎉 Регистрация успешно завершена!\n\n"
            "✅ Чем я могу вам помочь?"
        ),
        'phone_invalid': (
            "❌ Неверный номер телефона.\n\n"
            "📱 Пожалуйста, отправьте через кнопку ниже:"
        ),
        'error': (
            "❌ Произошла ошибка. Пожалуйста, попробуйте снова."
        ),
        'back': '⬅️ Назад',
    },

    'en': {
        'greeting': (
            "👋 Hello!\n\n"
            "I am Asadbek — an AI assistant created by the Napay District Administration.\n\n"
            "🔤 Please select a language:"
        ),
        'language_selected': (
            "✅ Great!\n\n"
            "📝 Please enter your full name:\n"
            "(Last Name - First Name)"
        ),
        'ask_phone': (
            "✅ Thank you!\n\n"
            "📱 Press the button below to share your phone number:"
        ),
        'phone_received': (
            "✅ Received!\n\n"
            "📍 Please select your neighborhood:"
        ),
        'ask_location': (
            "✅ Neighborhood selected!\n\n"
            "🏠 Now enter your full address:\n"
            "Example: Yunusabad, Building 12, Apartment 45"
        ),
        'saving': "⏳ Saving your information, please wait...",
        'success': (
            "🎉 Registration completed successfully!\n\n"
            "✅ How can I assist you today?"
        ),
        'phone_invalid': (
            "❌ Invalid phone number.\n\n"
            "📱 Please send it using the button below:"
        ),
        'error': (
            "❌ An error occurred. Please try again."
        ),
        'back': '⬅️ Back',
    }
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
    """Create language selection keyboard (NO BACK BUTTON)."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇺🇿 Oʻzbek"), KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇬🇧 English")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


def get_back_button_keyboard(language: str = 'uz'):
    """Create keyboard with back button."""
    back_text = MESSAGES[language]['back']
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=back_text)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard


def get_phone_request_keyboard(language: str = 'uz'):
    """Create keyboard with phone number request button and back button."""
    back_text = MESSAGES[language]['back']
    # Phone number request button (Telegram built-in)
    phone_button_text = {
        'uz': '📱 Telefon raqamini yuborish',
        'ru': '📱 Отправить номер телефона',
        'en': '📱 Share Phone Number',
    }
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=phone_button_text[language], request_contact=True)],
            [KeyboardButton(text=back_text)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard


async def get_neighborhood_keyboard(language: str = 'uz'):
    """Create neighborhood selection keyboard with back button at top (Reply Keyboard)."""
    @sync_to_async
    def get_neighborhoods():
        return list(Neighborhood.objects.filter(is_active=True).order_by('name_uz'))
    
    neighborhoods = await get_neighborhoods()
    
    # Back button fills the whole row (full width)
    back_text = MESSAGES[language]['back']
    keyboard_rows = [[KeyboardButton(text=back_text)]]
    
    if neighborhoods:
        # Add 2 buttons per row for neighborhoods
        row = []
        for neighborhood in neighborhoods:
            # Use name based on language
            if language == 'ru' and neighborhood.name_ru:
                name = neighborhood.name_ru
            elif language == 'en' and neighborhood.name_en:
                name = neighborhood.name_en
            else:
                name = neighborhood.name_uz
            
            row.append(KeyboardButton(text=name))
            
            # When we have 2 buttons, add the row and start a new one
            if len(row) == 2:
                keyboard_rows.append(row)
                row = []
        
        # Add remaining button if odd number
        if row:
            keyboard_rows.append(row)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    return keyboard


async def universal_pre_check(message: Message, state: FSMContext) -> tuple[bool, Optional[Users], Optional[Admins]]:
    """
    Universal pre-check: Look up user in Users and Admins tables.
    Returns: (is_new_user, user_instance, admin_instance)
    """
    telegram_chat_id = message.from_user.id
    
    @sync_to_async
    def check_telegram_account():
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
            
            return (False, user, None)  # Existing user
        except TelegramAccount.DoesNotExist:
            return None
    
    @sync_to_async
    def check_telegram_admin():
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
            
            return (False, None, admin)  # Existing admin
        except TelegramAdmin.DoesNotExist:
            return None
    
    # Check in TelegramAccount (linked to Users)
    result = await check_telegram_account()
    if result is not None:
        return result
    
    # Check in TelegramAdmin (linked to Admins)
    result = await check_telegram_admin()
    if result is not None:
        return result
    
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
    
    # Send next message in selected language with back button
    await message.answer(
        MESSAGES[language]['language_selected'],
        reply_markup=get_back_button_keyboard(language)
    )
    await state.set_state(RegistrationStates.ask_fullname)


async def process_fullname(message: Message, state: FSMContext):
    """Handle full name input."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    back_text = MESSAGES[language]['back']
    
    # Check if user pressed back button
    if message.text.strip() == back_text:
        # Go back to language selection
        await message.answer(
            MESSAGES[language]['greeting'],
            reply_markup=get_language_keyboard()
        )
        await state.set_state(RegistrationStates.choose_language)
        return
    
    full_name = message.text.strip()
    
    if len(full_name) < 3:
        await message.answer(
            MESSAGES[language].get('error', MESSAGES['uz']['error'])
        )
        return
    
    # Store full name
    await state.update_data(full_name=full_name)
    
    # Ask for phone with contact request button and back button
    await message.answer(
        MESSAGES[language]['ask_phone'],
        reply_markup=get_phone_request_keyboard(language)
    )
    await state.set_state(RegistrationStates.ask_phone)


async def process_phone(message: Message, state: FSMContext):
    """Handle phone number input via Telegram contact sharing."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    back_text = MESSAGES[language]['back']
    
    # Check if user shared contact (priority - contact sharing)
    if message.contact:
        # Extract phone number from contact
        phone = message.contact.phone_number
        
        # Format phone number to include + if not present
        if not phone.startswith('+'):
            phone = '+' + phone
        
        # Validate phone number format
        if not validate_phone_number(phone):
            await message.answer(MESSAGES[language]['phone_invalid'])
            return
        
        # Store phone number
        await state.update_data(phone_number=phone)
        
        # Ask for neighborhood with keyboard
        keyboard = await get_neighborhood_keyboard(language)
        
        await message.answer(
            MESSAGES[language]['phone_received'],
            reply_markup=keyboard
        )
        await state.set_state(RegistrationStates.ask_neighborhood)
        return
    
    # Check if user pressed back button (text message)
    if message.text and message.text.strip() == back_text:
        # Go back to fullname step - regenerate message
        await message.answer(
            MESSAGES[language]['language_selected'],
            reply_markup=get_back_button_keyboard(language)
        )
        await state.set_state(RegistrationStates.ask_fullname)
        return
    
    # If neither contact nor back button, remind user to use the button
    await message.answer(
        MESSAGES[language].get('phone_invalid', MESSAGES['uz']['phone_invalid']),
        reply_markup=get_phone_request_keyboard(language)
    )


async def process_neighborhood(message: Message, state: FSMContext):
    """Handle neighborhood selection and back button."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    back_text = MESSAGES[language]['back']
    
    # Check if back button was pressed
    if message.text and message.text.strip() == back_text:
        # Go back to phone step - regenerate message with contact request button
        await message.answer(
            MESSAGES[language]['ask_phone'],
            reply_markup=get_phone_request_keyboard(language)
        )
        await state.set_state(RegistrationStates.ask_phone)
        return
    
    # Handle neighborhood selection by name
    selected_name = message.text.strip()
    
    @sync_to_async
    def get_neighborhood_by_name():
        """Find neighborhood by name in selected language."""
        try:
            # Try to find by name_uz first (always exists)
            neighborhood = Neighborhood.objects.filter(
                is_active=True,
                name_uz__iexact=selected_name
            ).first()
            
            if neighborhood:
                return neighborhood
            
            # Try name_ru if language is Russian
            if language == 'ru':
                neighborhood = Neighborhood.objects.filter(
                    is_active=True,
                    name_ru__iexact=selected_name
                ).first()
                if neighborhood:
                    return neighborhood
            
            # Try name_en if language is English
            if language == 'en':
                neighborhood = Neighborhood.objects.filter(
                    is_active=True,
                    name_en__iexact=selected_name
                ).first()
                if neighborhood:
                    return neighborhood
            
            return None
        except Exception:
            return None
    
    neighborhood = await get_neighborhood_by_name()
    
    if neighborhood is None:
        await message.answer(MESSAGES[language]['error'])
        return
    
    # Store neighborhood ID and name
    await state.update_data(
        neighborhood_id=neighborhood.id,
        neighborhood_name=neighborhood.name_uz
    )
    
    # Ask for location with back button
    await message.answer(
        MESSAGES[language]['ask_location'],
        reply_markup=get_back_button_keyboard(language)
    )
    await state.set_state(RegistrationStates.ask_full_location)


async def process_location(message: Message, state: FSMContext):
    """Handle full location input."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    back_text = MESSAGES[language]['back']
    
    # Check if user pressed back button
    if message.text.strip() == back_text:
        # Go back to neighborhood step - regenerate keyboard
        keyboard = await get_neighborhood_keyboard(language)
        await message.answer(
            MESSAGES[language]['phone_received'],
            reply_markup=keyboard
        )
        await state.set_state(RegistrationStates.ask_neighborhood)
        return
    
    location = message.text.strip()
    
    if len(location) < 5:
        await message.answer(MESSAGES[language].get('error', MESSAGES['uz']['error']))
        return
    
    # Store location
    await state.update_data(full_location=location)
    
    # Show saving message (NO BACK BUTTON at this step)
    await message.answer(
        MESSAGES[language]['saving'],
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Move to saving state
    await state.set_state(RegistrationStates.saving_to_db)
    
    # Save to database
    await save_user_to_database(message, state)


async def save_user_to_database(message: Message, state: FSMContext):
    """Save all collected data to database."""
    try:
        data = await state.get_data()
        language = data.get('language', 'uz')
        
        @sync_to_async
        def save_user():
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
        
        await save_user()
        
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
    dp.message.register(process_neighborhood, RegistrationStates.ask_neighborhood)
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

