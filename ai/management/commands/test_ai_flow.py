from django.core.management.base import BaseCommand
from departments.models import Department
from users.models import Users
from messages_core.models import Session, Message, MessageContent
from ai.logic import process_message, get_embedding, qdrant_client
from qdrant_client.models import PointStruct, VectorParams, Distance
import uuid
import time

class Command(BaseCommand):
    help = 'Test the full AI flow with real services'

    def handle(self, *args, **options):
        self.stdout.write("Starting AI flow test...")

        # 1. Setup Data
        # dept_name = "Water Department"
        # dept, created = Department.objects.get_or_create(...)
        
        user, _ = Users.objects.get_or_create(phone_number="+998901234567", defaults={"full_name": "Test User"})
        session = Session.objects.create(user=user)
        message = Message.objects.create(session=session, sender_type='user', sender_user=user)
        MessageContent.objects.create(message=message, content_type='text', text="menga tuman hokimi kerak")
        
        self.stdout.write(f"Created test message: {message.message_uuid}")
        
        # Create Admin for Department
        # We need to find the department first. Since we are using existing index, we hope it finds "Poverty Reduction"
        # But for the test to be deterministic about routing to a specific admin, we should probably ensure that department exists in DB
        # The previous test run showed it found "Head of Narpay District Poverty Reduction and Employment Department"
        # Let's find that department and add an admin to it.
        
        try:
            target_dept = Department.objects.filter(name_uz__icontains="Kambag'allikni qisqartirish").first()
            admin, _ = Users.objects.get_or_create(phone_number="+998999999999", defaults={"full_name": "Test Admin"})
            # Wait, Admins model is different from Users
            from departments.models import Admins, TelegramAdmin
            
            admin_obj, _ = Admins.objects.get_or_create(
                full_name="Test Admin",
                defaults={"role": "department_head", "department": target_dept}
            )
            
            # Link Telegram Account
            TelegramAdmin.objects.get_or_create(
                admin=admin_obj,
                telegram_chat_id=123456789, # Dummy ID
                defaults={"username": "test_admin"}
            )
            self.stdout.write(f"Created admin for {target_dept.name_uz}")
            
        except Department.DoesNotExist:
            self.stdout.write(self.style.WARNING("Target department not found in DB. Admin routing test might fail."))

        # 2. Index Department (Skipped - using existing index)
        # ...
        
        # Wait a bit for indexing (not needed if using existing)
        # time.sleep(1)

        # 3. Run Process
        self.stdout.write("Running process_message...")
        ai_result = process_message(message.message_uuid)

        # 4. Report
        if ai_result:
            self.stdout.write(self.style.SUCCESS(f"AI Result Created: ID {ai_result.id}"))
            self.stdout.write(f"Suggested Dept: {ai_result.suggested_department_name}")
            self.stdout.write(f"Confidence: {ai_result.routing_confidence}")
            self.stdout.write(f"Reason: {ai_result.reason}")
            
            session.refresh_from_db()
            if session.assigned_department:
                self.stdout.write(self.style.SUCCESS(f"Session assigned to: {session.assigned_department.name_en}"))
            else:
                self.stdout.write(self.style.ERROR("Session not assigned to any department."))
            
            if ai_result.process_duration_ms:
                self.stdout.write(f"Duration: {ai_result.process_duration_ms}ms")
            else:
                self.stdout.write(self.style.ERROR("Duration not saved!"))
                
            if ai_result.message_raw_embedding and len(ai_result.message_raw_embedding) > 100:
                self.stdout.write(f"Embedding saved (length {len(ai_result.message_raw_embedding)})")
            else:
                self.stdout.write(self.style.ERROR("Embedding not saved or too short!"))
        else:
            self.stdout.write(self.style.ERROR("process_message returned None (failed or injection detected)"))
