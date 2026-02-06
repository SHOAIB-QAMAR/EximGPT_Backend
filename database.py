import os
import sys
import traceback
import logging
from dotenv import load_dotenv
import motor.motor_asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

def log_error(file: str, function: str, operation: str, error: Exception, context: dict = None):
    """Helper function to log errors with detailed context."""
    error_info = {
        "file": file,
        "function": function,
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
        "traceback": traceback.format_exc()
    }
    logger.error(f"[{file}.{function}] Error during {operation}: {error_info}")
    return error_info

# Load environment variables
try:
    load_dotenv()
    logger.info("[database.py] Environment variables loaded")
except Exception as e:
    log_error("database.py", "startup", "loading .env file", e, {})

# Get MongoDB URI
MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    logger.error("[database.py] CRITICAL: MONGODB_URI is None! Check .env file location and contents.")
    logger.error("[database.py] Expected .env file location: Same directory as database.py")
    logger.error("[database.py] Required format: MONGODB_URI=mongodb://localhost:27017 or mongodb+srv://...")
else:
    # Mask the URI for logging (show only host)
    try:
        # Basic masking - don't show credentials
        if "@" in MONGODB_URI:
            masked_uri = MONGODB_URI.split("@")[-1]
        else:
            masked_uri = MONGODB_URI.replace("mongodb://", "").replace("mongodb+srv://", "")
        logger.info(f"[database.py] SUCCESS: MONGODB_URI loaded (host: {masked_uri[:30]}...)")
    except:
        logger.info("[database.py] SUCCESS: MONGODB_URI loaded")

# Initialize MongoDB client
client = None
db = None
threads_collection = None

try:
    logger.info("[database.py] Initializing MongoDB client...")
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
    db = client.exim_db  # Using a default database name 'exim_db'
    threads_collection = db["threads"]
    logger.info("[database.py] MongoDB client initialized successfully")
    logger.info(f"[database.py] Database: exim_db, Collection: threads")
except Exception as e:
    log_error("database.py", "startup", "initializing MongoDB client", e, {
        "mongodb_uri_exists": bool(MONGODB_URI)
    })
    logger.error("[database.py] CRITICAL: Failed to initialize MongoDB connection!")
    logger.error("[database.py] The application may not function correctly without database connection.")
    # Create placeholder to prevent import errors - will fail on actual use
    threads_collection = None