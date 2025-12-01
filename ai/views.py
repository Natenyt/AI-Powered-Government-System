from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .logic import process_message
import logging

logger = logging.getLogger(__name__)

class MessagePrecheckView(APIView):
    """
    API View to handle message precheck and routing.
    Expected payload:
    {
        "message_uuid": "...",
        "user": { ... },
        "message": { "text": "...", ... }
    }
    """
    
    def post(self, request):
        data = request.data
        message_uuid = data.get('message_uuid')
        
        if not message_uuid:
            return Response({"error": "message_uuid is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # We assume the message is already saved in the DB by the time this is called,
            # or we might need to save it here if it's a purely external call.
            # Based on the prompt, "we shoudl ani api call to our microservice... and pass the message".
            # If the message is already in our DB (which it seems to be given we pass UUID), we just process it.
            
            result = process_message(message_uuid)
            
            if not result:
                 return Response({"status": "failed", "reason": "Processing failed or injection detected"}, status=status.HTTP_200_OK)

            return Response({
                "status": "success",
                "suggested_department": result.suggested_department_name,
                "confidence": result.routing_confidence
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing message {message_uuid}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
