import os
import google.generativeai as genai 
from PIL import Image
import traceback
import logging
import datetime
import json
# Imports Google's official Gemini API client library
# google.generativeai = Google's Python package for interacting with generative AI models

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

def log_error(file: str, function: str, operation: str, error: Exception, context: dict = None):
    """
    Helper function to log errors with detailed context for debugging.
    
    Args:
        file: The file where error occurred
        function: The function/method name
        operation: What operation was being performed
        error: The exception object
        context: Additional context data
    """
    error_info = {
        "file": file,
        "function": function,
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "traceback": traceback.format_exc()
    }
    logger.error(f"[{file}.{function}] Error during {operation}: {json.dumps(error_info, indent=2, default=str)}")
    return error_info

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validate API key on startup
if GEMINI_API_KEY:
    logger.info(f"[gemini_service.py] GEMINI_API_KEY loaded successfully (starts with: {GEMINI_API_KEY[:5]}...)")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("[gemini_service.py] Gemini API configured successfully")
    except Exception as config_error:
        log_error("gemini_service.py", "startup", "configuring Gemini API", config_error, {})
else:
    logger.warning("[gemini_service.py] WARNING: GEMINI_API_KEY not found in environment variables!")


async def get_gemini_response(message: str, language: str = "English") -> str:
    """
    Get a text-only response from Gemini in the specified language.
    
    Args:
        message: User's message/query
        language: Target language for response (default: English)
    
    Returns:
        AI response text or error message
    """
    function_name = "get_gemini_response"
    
    # Validate API key
    if not GEMINI_API_KEY:
        logger.error(f"[gemini_service.py.{function_name}] GEMINI_API_KEY not found in environment variables")
        return "Error: GEMINI_API_KEY not found in environment variables. Please configure the API key."

    # Validate input
    if not message or not message.strip():
        logger.warning(f"[gemini_service.py.{function_name}] Empty message received")
        return "I didn't receive any message. Please try again."

    try:
        logger.info(f"[gemini_service.py.{function_name}] Starting request - Language: {language}, Message length: {len(message)}")
        
        # Initialize model
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
        except Exception as model_error:
            log_error("gemini_service.py", function_name, "initializing Gemini model", model_error, {
                "model_name": "gemini-2.5-flash"
            })
            return f"Error: Failed to initialize AI model. Please try again later."
        
        # Add language instruction to the prompt
        prompt = f"Respond in {language}. User query: {message}"
        logger.info(f"[gemini_service.py.{function_name}] Sending prompt to Gemini (length: {len(prompt)})")
        
        # Make API call
        try:
            response = await model.generate_content_async(prompt)
        except Exception as api_error:
            log_error("gemini_service.py", function_name, "calling Gemini API", api_error, {
                "language": language,
                "message_length": len(message)
            })
            return f"Sorry, I encountered an error contacting the AI service. Error: {str(api_error)}"
        
        # Validate response
        if not response or not hasattr(response, 'text'):
            logger.error(f"[gemini_service.py.{function_name}] Invalid response from Gemini - no text attribute")
            return "Sorry, I received an invalid response from the AI. Please try again."
        
        logger.info(f"[gemini_service.py.{function_name}] Response received successfully - Length: {len(response.text)}")
        return response.text
        
    except Exception as e:
        log_error("gemini_service.py", function_name, "get_gemini_response", e, {
            "language": language,
            "message_length": len(message) if message else 0
        })
        return f"Sorry, I encountered an unexpected error while processing your request. Error details: {str(e)}"


async def get_gemini_response_with_image(message: str, image_path: str, language: str = "English") -> str:
    """
    Get a multimodal response from Gemini with both text and image input in the specified language.
    
    Args:
        message: User's message/query (optional, can be empty for image-only analysis)
        image_path: Local file path to the image
        language: Target language for response (default: English)
    
    Returns:
        AI response text or error message
    """
    function_name = "get_gemini_response_with_image"
    
    # Validate API key
    if not GEMINI_API_KEY:
        logger.error(f"[gemini_service.py.{function_name}] GEMINI_API_KEY not found in environment variables")
        return "Error: GEMINI_API_KEY not found in environment variables. Please configure the API key."

    # Validate image path
    if not image_path:
        logger.error(f"[gemini_service.py.{function_name}] No image path provided")
        return "Error: No image path provided for multimodal request."
    
    if not os.path.exists(image_path):
        logger.error(f"[gemini_service.py.{function_name}] Image file not found: {image_path}")
        return f"Error: Image file not found at path: {image_path}"

    try:
        logger.info(f"[gemini_service.py.{function_name}] Starting multimodal request - Image: {image_path}, Language: {language}")
        
        # Load the image using PIL
        try:
            img = Image.open(image_path)
            img_format = img.format
            img_size = img.size
            logger.info(f"[gemini_service.py.{function_name}] Image loaded - Format: {img_format}, Size: {img_size}")
        except FileNotFoundError as fnf_error:
            log_error("gemini_service.py", function_name, "loading image file", fnf_error, {
                "image_path": image_path
            })
            return f"Error: Image file not found: {image_path}"
        except Exception as img_error:
            log_error("gemini_service.py", function_name, "opening image with PIL", img_error, {
                "image_path": image_path
            })
            return f"Error: Could not open image file. The file may be corrupted or in an unsupported format."
        
        # Initialize vision-capable model
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
        except Exception as model_error:
            log_error("gemini_service.py", function_name, "initializing Gemini vision model", model_error, {
                "model_name": "gemini-2.5-flash"
            })
            return f"Error: Failed to initialize AI model for image processing."
        
        # Create multimodal prompt with text, image, and language instruction
        base_text = message if message else "Describe this image in detail."
        prompt_text = f"Respond in {language}. {base_text}"
        logger.info(f"[gemini_service.py.{function_name}] Sending multimodal prompt to Gemini")
        
        # Make API call with image
        try:
            response = await model.generate_content_async([prompt_text, img])
        except Exception as api_error:
            log_error("gemini_service.py", function_name, "calling Gemini multimodal API", api_error, {
                "language": language,
                "image_path": image_path,
                "has_text": bool(message)
            })
            return f"Sorry, I encountered an error processing your image. Error: {str(api_error)}"
        
        # Validate response
        if not response or not hasattr(response, 'text'):
            logger.error(f"[gemini_service.py.{function_name}] Invalid response from Gemini - no text attribute")
            return "Sorry, I received an invalid response from the AI. Please try again."
        
        logger.info(f"[gemini_service.py.{function_name}] Multimodal response received successfully - Length: {len(response.text)}")
        return response.text
        
    except Exception as e:
        log_error("gemini_service.py", function_name, "get_gemini_response_with_image", e, {
            "image_path": image_path,
            "language": language,
            "has_message": bool(message)
        })
        return f"Sorry, I encountered an error processing your image. Error details: {str(e)}"