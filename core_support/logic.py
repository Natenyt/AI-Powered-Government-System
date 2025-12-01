import logging
import requests
import os
from django.conf import settings
from messages_core.models import Session, Message
from departments.models import Department, Admins, TelegramAdmin
from ai.logic import process_message # Direct call for now, simulating microservice
# from ai.views import MessagePrecheckView # Alternative

logger = logging.getLogger(__name__)

def precheck(session_uuid, message_data):
    """
    Checks if the session has an assigned department.
    Returns True if assigned, False otherwise.
    """
    try:
        session = Session.objects.get(session_uuid=session_uuid)
    except Session.DoesNotExist:
        logger.error(f"Session {session_uuid} not found.")
        return False

    if session.assigned_department:
        # Department already assigned, route to it
        message_router(session.assigned_department.id, message_data['message_uuid'])
        return True

    return False

def send_telegram_message(chat_id, text):
    """
    Sends a message to a Telegram chat using the Bot API.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Message sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")

def message_router(department_id, message_uuid):
    """
    Routes the message to the assigned department.
    1. Updates Session assigned_department.
    2. Finds all admins for the department.
    3. Sends message to their Telegram chat_id.
    4. Sends message to Department dashboard (dummy).
    """
    try:
        message = Message.objects.get(message_uuid=message_uuid)
        session = message.session
        department = Department.objects.get(id=department_id)
    except (Message.DoesNotExist, Department.DoesNotExist) as e:
        logger.error(f"Error in message_router: {e}")
        return

    # 1. Update Session
    session.assigned_department = department
    session.save()
    logger.info(f"Session {session.session_uuid} assigned to {department.name_en}")

    # 2. Find Admins
    admins = Admins.objects.filter(department=department)
    telegram_chat_ids = []
    for admin in admins:
        # Assuming admin has linked telegram accounts
        tg_accounts = admin.telegram_accounts.all()
        for tg in tg_accounts:
            telegram_chat_ids.append(tg.telegram_chat_id)
    
    # 3. Send to Telegram
    # Get message text
    text_content = ""
    for content in message.contents.all():
        if content.content_type == 'text':
            text_content += content.text + "\n"
            
    if not text_content:
        text_content = "[Non-text message]"

    final_text = f"New Message for {department.name_en}:\n\n{text_content}"

    for chat_id in telegram_chat_ids:
        send_telegram_message(chat_id, final_text)
        logger.info(f"Sending message to Admin Telegram ID: {chat_id}")

    # 4. Send to Dashboard (Dummy)
    logger.info(f"Sending message to Department {department.name_en} Dashboard")
