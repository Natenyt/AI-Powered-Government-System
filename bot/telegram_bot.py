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
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Contact
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.db import transaction
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MultiGov_version2.settings')
django.setup()

from departments.models import Admins, TelegramAdmin
from core_support.models import Neighborhood
from users.models import Users, TelegramAccount
from core_support.logic import precheck
from ai.logic import process_message


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


class MessageStates(StatesGroup):
    writing = State()


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
        # Menu buttons
        'menu_send_message': '📝 Murojaat yuborish',
        'menu_check_status': '📊 Holatni tekshirish',
        'menu_change_language': '🌐 Tilni o‘zgartirish',
        'menu_website': '🌐 Veb-sayt',
        'menu_news': '📰 Yangiliklar',
        # Message flow
        'msg_instruction': (
            "📝 Iltimos, xabaringizni yozing.\n\n"
            "Siz bir nechta xabar yuborishingiz mumkin. "
            "Yozib bo‘lganingizdan so‘ng '✅ Yakunlash' tugmasini bosing."
        ),
        'msg_received': "✅ Xabar qabul qilindi. Yana yozishingiz mumkin yoki yakunlash uchun tugmani bosing.",
        'msg_finished': "✅ Murojaatingiz qabul qilindi va tegishli bo‘limga yo‘naltirildi.",
        'msg_cancelled': "❌ Murojaat bekor qilindi.",
        'btn_finished': '✅ Yakunlash',
        'btn_cancel': '❌ Bekor qilish',
        'status_empty': "📭 Sizda faol murojaatlar yo‘q.",
        'status_header': "📊 Sizning murojaatlaringiz holati:\n\n",
        'website_link': "Bizning veb-sayt: https://example.com",
        'no_news': "📰 Hozircha yangiliklar yo‘q.",
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
        # Menu buttons
        'menu_send_message': '📝 Отправить обращение',
        'menu_check_status': '📊 Проверить статус',
        'menu_change_language': '🌐 Изменить язык',
        'menu_website': '🌐 Веб-сайт',
        'menu_news': '📰 Новости',
        # Message flow
        'msg_instruction': (
            "📝 Пожалуйста, напишите ваше сообщение.\n\n"
            "Вы можете отправить несколько сообщений. "
            "После завершения нажмите кнопку '✅ Завершить'."
        ),
        'msg_received': "✅ Сообщение принято. Вы можете писать еще или нажать кнопку завершения.",
        'msg_finished': "✅ Ваше обращение принято и направлено в соответствующий отдел.",
        'msg_cancelled': "❌ Обращение отменено.",
        'btn_finished': '✅ Завершить',
        'btn_cancel': '❌ Отменить',
        'status_empty': "📭 У вас нет активных обращений.",
        'status_header': "📊 Статус ваших обращений:\n\n",
        'website_link': "Наш веб-сайт: https://example.com",
        'no_news': "📰 Новостей пока нет.",
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
        # Menu buttons
        'menu_send_message': '📝 Send Message',
        'menu_check_status': '📊 Check Status',
        'menu_change_language': '🌐 Change Language',
        'menu_website': '🌐 Website',
        'menu_news': '📰 News',
        # Message flow
        'msg_instruction': (
            "📝 Please write your message.\n\n"
            "You can send multiple messages. "
            "Press '✅ Finished' when you are done."
        ),
        'msg_received': "✅ Message received. You can write more or press finished.",
        'msg_finished': "✅ Your message has been received and routed to the appropriate department.",
        'msg_cancelled': "❌ Message cancelled.",
        'btn_finished': '✅ Finished',
        'btn_cancel': '❌ Cancel',
        'status_empty': "📭 You have no active messages.",
        'status_header': "📊 Your message status:\n\n",
        'website_link': "Our website: https://example.com",
        'no_news': "📰 No news at the moment.",
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
            # elif language == 'en' and neighborhood.name_en:
            #     name = neighborhood.name_en
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


def get_main_menu_keyboard(language: str = 'uz'):
    """Create main menu keyboard."""
    msgs = MESSAGES[language]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=msgs['menu_send_message']), KeyboardButton(text=msgs['menu_check_status'])],
            [KeyboardButton(text=msgs['menu_change_language'])],
            [KeyboardButton(text=msgs['menu_website']), KeyboardButton(text=msgs['menu_news'])],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard


def get_message_flow_keyboard(language: str = 'uz'):
    """Create keyboard for message writing flow."""
    msgs = MESSAGES[language]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=msgs['btn_finished']), KeyboardButton(text=msgs['btn_cancel'])],
        ],
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
            telegram_account = TelegramAccount.objects.select_related('user').get(
                telegram_chat_id=telegram_chat_id,
                user__is_deleted=False
            )
            user = telegram_account.user
            
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
            telegram_admin = TelegramAdmin.objects.select_related('admin').get(
                telegram_chat_id=telegram_chat_id
            )
            admin = telegram_admin.admin
            
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
            # Get user's language preference
            telegram_account = await sync_to_async(user.telegram_accounts.get)(telegram_chat_id=message.from_user.id)
            language = telegram_account.language_preference
            
            await message.answer(
                f"Assalomu alaykum, {user.full_name or 'foydalanuvchi'}!\n\n"
                "Sizga qanday yordam bera olaman?",
                reply_markup=get_main_menu_keyboard(language)
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
    
    # Check if this is a language change for existing user
    data = await state.get_data()
    if data.get('is_changing_language'):
        # Update DB
        telegram_user_id = message.from_user.id
        
        @sync_to_async
        def update_language():
            telegram_account = TelegramAccount.objects.get(telegram_chat_id=telegram_user_id)
            telegram_account.language_preference = language
            telegram_account.language_code = language
            telegram_account.save()
            return telegram_account.user
            
        user = await update_language()
        
        # Return to main menu
        await message.answer(
            MESSAGES[language]['success'], # Or a specific "Language changed" message
            reply_markup=get_main_menu_keyboard(language)
        )
        await state.clear()
        return

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
                        verified=False,
                    )
                
                # Create TelegramAccount linked to user
                telegram_chat_id = data.get('telegram_user_id')
                
                # Check if TelegramAccount already exists (edge case)
                telegram_account, created = TelegramAccount.objects.get_or_create(
                    telegram_chat_id=telegram_chat_id,
                    defaults={
                        'user': user,
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
        # Success message
        await message.answer(
            MESSAGES[language]['success'],
            reply_markup=get_main_menu_keyboard(language)
        )
        
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
            if user:
                telegram_account = await sync_to_async(user.telegram_accounts.get)(telegram_chat_id=message.from_user.id)
                language = telegram_account.language_preference
                text = message.text
                msgs = MESSAGES[language]
                
                # Route based on button text
                if text == msgs['menu_send_message']:
                    await start_message_flow(message, state, language)
                elif text == msgs['menu_check_status']:
                    await check_status(message, state, user, language)
                elif text == msgs['menu_change_language']:
                    await start_change_language(message, state, language)
                elif text == msgs['menu_website']:
                    await message.answer(msgs['website_link'])
                elif text == msgs['menu_news']:
                    await message.answer(msgs['no_news'])
                else:
                    # Unknown command, show menu again
                    await message.answer(
                        "Sizga qanday yordam bera olaman?",
                        reply_markup=get_main_menu_keyboard(language)
                    )
            elif admin:
                # Admin logic (placeholder)
                await message.answer("Admin panel")
    else:
        # In a state but message doesn't match - ignore or handle error
        pass


async def start_message_flow(message: Message, state: FSMContext, language: str):
    """Start the message sending flow."""
    await message.answer(
        MESSAGES[language]['msg_instruction'],
        reply_markup=get_message_flow_keyboard(language)
    )
    await state.set_state(MessageStates.writing)
    # Initialize list of messages
    await state.update_data(messages=[], language=language)


async def process_message_writing(message: Message, state: FSMContext):
    """Handle messages being written by user."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    msgs = MESSAGES[language]
    text = message.text
    
    # Check for control buttons
    if text == msgs['btn_finished']:
        await finish_message_flow(message, state)
        return
    elif text == msgs['btn_cancel']:
        await cancel_message_flow(message, state)
        return
    
    # Append message to list
    messages = data.get('messages', [])
    messages.append(text)
    await state.update_data(messages=messages)
    
    await message.answer(msgs['msg_received'])


async def finish_message_flow(message: Message, state: FSMContext):
    """Save messages and finish flow."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    messages_list = data.get('messages', [])
    
    if not messages_list:
        await message.answer(MESSAGES[language]['msg_cancelled'], reply_markup=get_main_menu_keyboard(language))
        await state.clear()
        return

    # Combine messages
    full_content = "\n\n".join(messages_list)
    
    # Save to DB
    telegram_chat_id = message.from_user.id
    
    @sync_to_async
    def save_message():
        from messages_core.models import Session, Message, MessageContent
        telegram_account = TelegramAccount.objects.get(telegram_chat_id=telegram_chat_id)
        user = telegram_account.user
        
        # Find open session or create new one
        session = Session.objects.filter(user=user, status='open').first()
        if not session:
            session = Session.objects.create(
                user=user,
                status='open'
            )
        
        # Create Message
        message_obj = Message.objects.create(
            session=session,
            sender_type='user',
            sender_user=user,
            sender_platform='telegram',
        )
        
        # Create MessageContent
        MessageContent.objects.create(
            message=message_obj,
            content_type='text',
            text=full_content
        )
        return session.session_uuid, message_obj.message_uuid
    
    session_uuid, message_uuid = await save_message()
    
    # Precheck and AI Routing
    # Check if department is assigned
    is_assigned = await sync_to_async(precheck)(session_uuid, {"message_uuid": message_uuid})
    
    if not is_assigned:
        # Call AI Microservice logic
        await sync_to_async(process_message)(message_uuid)
    
    await message.answer(
        MESSAGES[language]['msg_finished'],
        reply_markup=get_main_menu_keyboard(language)
    )
    await state.clear()


async def cancel_message_flow(message: Message, state: FSMContext):
    """Cancel message flow."""
    data = await state.get_data()
    language = data.get('language', 'uz')
    
    await message.answer(
        MESSAGES[language]['msg_cancelled'],
        reply_markup=get_main_menu_keyboard(language)
    )
    await state.clear()


async def check_status(message: Message, state: FSMContext, user: Users, language: str):
    """Check status of active messages."""
    msgs = MESSAGES[language]
    
    @sync_to_async
    def get_active_messages():
        from messages_core.models import Session
        # Filter for sessions that are 'open'
        active_sessions = Session.objects.filter(
            user=user,
            status='open'
        ).order_by('-created_at')[:5]
        return list(active_sessions)
    
    active_messages = await get_active_messages()
    
    if not active_messages:
        await message.answer(msgs['status_empty'])
        return
    
    response = msgs['status_header']
    for session in active_messages:
        # Simple formatting: Date - Status
        date_str = session.created_at.strftime("%Y-%m-%d %H:%M")
        # Translate status if needed, or just show raw
        status_display = "Ochiq" if session.status == 'open' else "Yopiq" # Simple Uzbek translation
        if language == 'ru':
            status_display = "Открыт" if session.status == 'open' else "Закрыт"
        elif language == 'en':
            status_display = "Open" if session.status == 'open' else "Closed"
            
        response += f"📅 {date_str}\nℹ️ {status_display}\n\n"
        
    await message.answer(response)


async def start_change_language(message: Message, state: FSMContext, current_language: str):
    """Start language change flow."""
    # Re-use registration language selection logic but with a different state or flag?
    # Actually, we can just show the language keyboard and set a state to handle it.
    # But we need to update the user's preference in DB.
    
    await message.answer(
        MESSAGES[current_language]['greeting'].split('\n')[-1], # Just "Please select language" part
        reply_markup=get_language_keyboard()
    )
    await state.set_state(RegistrationStates.choose_language)
    # We can use a flag in state to know if this is a change or new registration
    await state.update_data(is_changing_language=True)



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
    
    # Message flow handlers
    dp.message.register(process_message_writing, MessageStates.writing)
    
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

