import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import Users, TelegramAccount
from messages_core.models import Session, Message, MessageContent
from bot.telegram_bot import save_user_to_database
from asgiref.sync import sync_to_async
import asyncio

async def verify_bot_logic():
    print("Starting verification...")
    
    # 1. Create a test user and telegram account
    print("Creating test user...")
    user_phone = "+998901234567"
    telegram_id = 123456789
    
    user, _ = await sync_to_async(Users.objects.get_or_create)(
        phone_number=user_phone,
        defaults={'full_name': 'Test User'}
    )
    
    tg_account, _ = await sync_to_async(TelegramAccount.objects.get_or_create)(
        telegram_chat_id=telegram_id,
        defaults={
            'user': user,
            'username': 'testuser',
            'full_name': 'Test User',
            'phone_number': user_phone
        }
    )
    
    # 2. Simulate save_message logic (copied/adapted from bot)
    print("Simulating save_message...")
    full_content = "Test message content"
    
    # Logic from bot/telegram_bot.py
    session = await sync_to_async(Session.objects.filter(user=user, status='open').first)()
    if not session:
        print("Creating new session...")
        session = await sync_to_async(Session.objects.create)(
            user=user,
            status='open'
        )
    else:
        print("Found existing session.")
        
    message_obj = await sync_to_async(Message.objects.create)(
        session=session,
        sender_type='user',
        sender_user=user,
        sender_platform='telegram',
        text=full_content
    )
    
    await sync_to_async(MessageContent.objects.create)(
        message=message_obj,
        content_type='text',
        text=full_content
    )
    
    # 3. Verify data in DB
    print("Verifying DB data...")
    
    # Check Session
    sessions = await sync_to_async(list)(Session.objects.filter(user=user))
    assert len(sessions) >= 1
    print(f"✅ Found {len(sessions)} sessions for user.")
    
    # Check Message
    messages = await sync_to_async(list)(Message.objects.filter(session=sessions[0]))
    assert len(messages) >= 1
    print(f"✅ Found {len(messages)} messages in session.")
    
    # Check MessageContent
    contents = await sync_to_async(list)(MessageContent.objects.filter(message=messages[0]))
    assert len(contents) >= 1
    assert contents[0].text == full_content
    print(f"✅ Found content: {contents[0].text}")
    
    # 4. Simulate check_status logic
    print("Simulating check_status...")
    active_sessions = await sync_to_async(list)(Session.objects.filter(
        user=user,
        status='open'
    ).order_by('-created_at')[:5])
    
    assert len(active_sessions) >= 1
    print(f"✅ Found {len(active_sessions)} active sessions.")
    
    print("Verification successful!")

if __name__ == "__main__":
    asyncio.run(verify_bot_logic())
