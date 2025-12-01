from django.test import TestCase
from messages_core.models import Message, Session, MessageContent
from users.models import Users
from departments.models import Department
from core_support.logic import precheck
from ai.models import AIResult, InjectResult
import uuid

class MessageProcessingTest(TestCase):
    def setUp(self):
        # Create User
        self.user = Users.objects.create(full_name="Test User", phone_number="+123456789")
        
        # Create Session
        self.session = Session.objects.create(user=self.user)
        
        # Create Message
        self.message = Message.objects.create(
            session=self.session,
            sender_type='user',
            sender_user=self.user
        )
        
        # Create Message Content
        MessageContent.objects.create(
            message=self.message,
            content_type='text',
            text="My water meter is broken and leaking."
        )
        
        # Create Department
        self.department = Department.objects.create(
            name_en="Water Department",
            name_uz="Suv",
            description_en="Handles water issues"
        )

    def test_precheck_flow(self):
        print("\n--- Starting Precheck Flow Test ---")
        
        # 1. Run Precheck (Should be False initially)
        message_data = {
            "message_uuid": str(self.message.message_uuid),
            "user": {"uuid": str(self.user.user_uuid)},
            "message": {"text": "My water meter is broken and leaking."}
        }
        
        result = precheck(self.session.session_uuid, message_data)
        self.assertFalse(result, "Precheck should return False when no department is assigned")
        
        # 2. Call AI Process (Simulating what bot does)
        # We need to mock the AI parts or rely on placeholders if real APIs fail
        # For this test, we might want to mock get_embedding/search_vector_db/analyze_message_with_gemini
        # But since we updated logic.py to use real clients, we should probably mock them here
        # or just run it and see if it handles connection errors gracefully (it logs errors).
        
        # To make the test pass without real external services, we can mock the functions in ai.logic
        from unittest.mock import patch
        
        with patch('ai.logic.get_embedding') as mock_embed, \
             patch('ai.logic.search_vector_db') as mock_search, \
             patch('ai.logic.analyze_message_with_gemini') as mock_analyze:
             
            mock_embed.return_value = [0.1] * 768
            mock_search.return_value = [{"name": "Water Department", "score": 0.9, "description": "Water issues"}]
            mock_analyze.return_value = {
                "message_type": "complaint",
                "routing_confidence": 0.95,
                "suggested_department_name": "Water Department",
                "reason": "Water leak",
                "explanation": "Test explanation"
            }
            
            from ai.logic import process_message
            ai_result = process_message(self.message.message_uuid)
            
            # 3. Verify AI Result
            self.assertIsNotNone(ai_result)
            self.assertEqual(ai_result.suggested_department_name, "Water Department")
            
            # 4. Verify Session Update (process_message calls message_router)
            self.session.refresh_from_db()
            self.assertEqual(self.session.assigned_department, self.department, "Session should be assigned to Water Department")
            
            # 5. Verify Precheck is now True
            result_after = precheck(self.session.session_uuid, message_data)
            self.assertTrue(result_after, "Precheck should return True after assignment")
        
        print("--- Test Completed Successfully ---")
