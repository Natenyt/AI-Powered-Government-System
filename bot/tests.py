from django.test import TestCase
from bot.telegram_bot import MESSAGES, get_main_menu_keyboard, get_message_flow_keyboard

class BotMessagesTest(TestCase):
    def test_messages_structure(self):
        """Verify that MESSAGES dictionary has all required keys for all languages."""
        required_keys = [
            'greeting', 'language_selected', 'ask_phone', 'phone_received',
            'ask_location', 'saving', 'success', 'phone_invalid', 'error', 'back',
            'menu_send_message', 'menu_check_status', 'menu_change_language',
            'menu_website', 'menu_news', 'msg_instruction', 'msg_received',
            'msg_finished', 'msg_cancelled', 'btn_finished', 'btn_cancel',
            'status_empty', 'status_header', 'website_link', 'no_news'
        ]
        
        for lang in ['uz', 'ru', 'en']:
            self.assertIn(lang, MESSAGES)
            for key in required_keys:
                self.assertIn(key, MESSAGES[lang], f"Missing key '{key}' in language '{lang}'")

    def test_keyboards_creation(self):
        """Verify that keyboard functions return valid objects without error."""
        for lang in ['uz', 'ru', 'en']:
            main_menu = get_main_menu_keyboard(lang)
            self.assertIsNotNone(main_menu)
            
            msg_flow = get_message_flow_keyboard(lang)
            self.assertIsNotNone(msg_flow)
