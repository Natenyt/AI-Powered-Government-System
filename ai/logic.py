import json
import logging
import os
import time
from django.conf import settings
from .models import InjectResult, AIResult
from messages_core.models import Message, Session
from departments.models import Department
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

# Initialize clients
# Initialize clients
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set in environment variables.")

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Initialize Qdrant Client
# Assuming Qdrant is running locally on default port or configured via settings
QDRANT_HOST = getattr(settings, 'QDRANT_HOST', 'localhost')
QDRANT_PORT = getattr(settings, 'QDRANT_PORT', 6333)
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def detect_language(text):
    """
    Detects language based on script.
    Latin characters -> 'uz'
    Cyrillic characters -> 'ru'
    Neither -> None
    """
    has_latin = False
    has_cyrillic = False
    
    for char in text:
        if 'a' <= char.lower() <= 'z':
            has_latin = True
        elif '\u0400' <= char <= '\u04FF': # Basic Cyrillic range
            has_cyrillic = True
            
    if has_latin and not has_cyrillic:
        return 'uz'
    if has_cyrillic:
        return 'ru'
        
    return None

def injection_detector(text):
    """
    Simple injection detection. Returns True if injection detected, False otherwise.
    Stage 1: Simple keyword/pattern check.
    """
    # Placeholder for more advanced logic
    # For now, check for common injection patterns or known malicious keywords
    suspicious_patterns = ["ignore previous instructions", "system prompt", "delete all"]
    for pattern in suspicious_patterns:
        if pattern.lower() in text.lower():
            return True
    return False

def get_embedding(text):
    """
    Get embedding for text using Gemini.
    """
    if not client:
        logger.error("Gemini client not initialized.")
        return [0.0] * 768

    retries = 5
    for attempt in range(retries):
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            # Result should be an EmbedContentResponse
            # Accessing the first embedding
            if result.embeddings:
                return result.embeddings[0].values
            return [0.0] * 768
        except Exception as e:
            if "429" in str(e):
                wait_time = 20 * (attempt + 1) # Linear backoff: 20, 40, 60...
                logger.warning(f"Rate limit hit in get_embedding. Waiting {wait_time}s... (Attempt {attempt+1}/{retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Error getting embedding: {e}")
                return [0.0] * 768
    
    logger.error("Failed to get embedding after retries.")
    return [0.0] * 768

def search_vector_db(vector, language='uz'):
    """
    Search Qdrant for best candidates, filtering by language.
    """
    try:
        # Filter by language if provided
        query_filter = None
        if language:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="lang",
                        match=MatchValue(value=language)
                    )
                ]
            )
        
        result = qdrant_client.query_points(
            collection_name="departments",
            query=vector,
            query_filter=query_filter,
            limit=3
        )
        hits = result.points
        # Return ID as well
        return [{"name": hit.payload.get('name'), "score": hit.score, "description": hit.payload.get('description'), "id": hit.payload.get('dept_id')} for hit in hits]
    except Exception as e:
        logger.error(f"Error searching vector DB: {e}")
        # Fallback if DB fails or is empty
        return []

def analyze_message_with_gemini(message_text, candidates):
    """
    Ask Gemini to analyze the message and candidates to determine the best department.
    """
    if not client:
        logger.error("Gemini client not initialized.")
        return {}

    candidates_str = json.dumps(candidates, indent=2)
    prompt = f"""
    You are an intelligent routing assistant for a government feedback system.
    
    Incoming Message: "{message_text}"
    
    Here are the top 3 candidate departments found by vector search:
    {candidates_str}
    
    Task:
    1. Analyze the message content.
    2. Determine the most appropriate department from the candidates (or suggest 'General' if none fit well).
    3. Classify the message type (complaint, suggestion, inquiry).
    4. Provide a confidence score (0.0 to 1.0).
    5. Explain your reasoning.
    
    Return the result as a valid JSON object with the following keys:
    - message_type: string
    - routing_confidence: float
    - suggested_department_name: string (exact name from candidates if possible)
    - suggested_department_id: integer (ID from candidates if possible, or null)
    - reason: string
    - explanation: string
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        if response.text:
            return json.loads(response.text)
        return {}
    except Exception as e:
        logger.error(f"Error analyzing with Gemini: {e}")
        return {}

def process_message(message_uuid):
    """
    Main orchestration function.
    """
    start_time = time.time()
    try:
        message = Message.objects.get(message_uuid=message_uuid)
    except Message.DoesNotExist:
        logger.error(f"Message {message_uuid} not found.")
        return

    text = ""
    # Extract text from message contents
    for content in message.contents.all():
        if content.content_type == 'text' and content.text:
            text += content.text + " "
    
    text = text.strip()
    if not text:
        logger.warning(f"Message {message_uuid} has no text content.")
        return

    # 1. Injection Detection
    is_injection = injection_detector(text)
    
    InjectResult.objects.create(
        message=message,
        is_injection=is_injection,
        details={"text_length": len(text)}
    )

    if is_injection:
        logger.warning(f"Injection detected for message {message_uuid}. Terminating.")
        AIResult.objects.create(
            session=message.session,
            message=message,
            is_injection=True,
            reason="Injection detected"
        )
        return

    # 1.5 Detect Language
    language = detect_language(text)
    logger.info(f"Detected language: {language}")
    print(f"DEBUG: Detected language: {language}")
    
    if language not in ['uz', 'ru']:
        logger.error(f"Unsupported language detected: {language}. Terminating.")
        print(f"Unsupported language: {language}") # Console output as requested
        AIResult.objects.create(
            session=message.session,
            message=message,
            is_injection=False,
            reason=f"Unsupported language: {language}"
        )
        return

    # 2. Vectorization
    vector = get_embedding(text)
    
    # 3. Vector Search (with language filter)
    candidates = search_vector_db(vector, language=language)
    
    # If no candidates found with filter (maybe wrong lang detection or missing data), try without filter?
    if not candidates:
        logger.info("No candidates found with language filter. Retrying without filter.")
        candidates = search_vector_db(vector, language=None)
    
    # 4. Gemini Analysis
    analysis = analyze_message_with_gemini(text, candidates)
    
    # 5. Save AIResult
    suggested_dept_name = analysis.get("suggested_department_name")
    suggested_dept_id = analysis.get("suggested_department_id")
    
    suggested_dept = None
    if suggested_dept_id:
        try:
            suggested_dept = Department.objects.get(id=suggested_dept_id)
        except Department.DoesNotExist:
            logger.warning(f"Suggested department ID {suggested_dept_id} not found in DB.")
            suggested_dept = None

    ai_result = AIResult.objects.create(
        session=message.session,
        message=message,
        is_injection=False,
        message_type=analysis.get("message_type"),
        routing_confidence=analysis.get("routing_confidence"),
        suggested_department_name=suggested_dept_name,
        suggested_department_id=suggested_dept.id if suggested_dept else None,
        reason=analysis.get("reason"),
        explanation=analysis.get("explanation"),
        vector_similarity_score=candidates[0]['score'] if candidates else 0.0,
        vector_top_candidates=candidates,
        message_raw_embedding=vector,
        process_duration_ms=int((time.time() - start_time) * 1000)
    )
    
    # 6. Auto-route if confidence is high (Optional, but requested in flow)
    # The user said "once all of this done, then we call the message_router function"
    # So we should call it here if we found a department.
    if suggested_dept:
        from core_support.logic import message_router
        message_router(suggested_dept.id, message_uuid)

    return ai_result
