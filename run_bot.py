import os
import django
import asyncio

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from bot.telegram_bot import start_bot

if __name__ == "__main__":
    asyncio.run(start_bot())
