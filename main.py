from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import datetime
import os
import uuid
import traceback
import logging
from database import threads_collection
from gemini_service import get_gemini_response, get_gemini_response_with_image
from chat_data import chat_data

# Configure logging for better debugging
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

# Ensure uploads directory exists
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    logger.info(f"[main.py] Upload directory ready: {UPLOAD_DIR}")
except Exception as e:
    log_error("main.py", "startup", "creating upload directory", e, {"path": UPLOAD_DIR})

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev
    allow_credentials=True, # Allows cookies/authentication headers
    allow_methods=["*"], # Allows all HTTP methods (GET, POST, DELETE, etc.)
    allow_headers=["*"],
)

# Serve uploaded files as static
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Pydantic Models for Response
class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime.datetime] = None

class Thread(BaseModel):
    threadId: str
    title: str
    messages: List[Message]
    updatedAt: Optional[datetime.datetime] = None

# --- Websocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

# --- Image Upload Endpoint ---
@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image file and return its URL."""
    function_name = "upload_image"
    
    try:
        logger.info(f"[main.py.{function_name}] Starting file upload: {file.filename}, content_type: {file.content_type}")
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            logger.warning(f"[main.py.{function_name}] Invalid file type: {file.content_type}")
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, GIF, WebP")
        
        # Generate unique filename
        file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        logger.info(f"[main.py.{function_name}] Saving file to: {file_path}")
        
        # Save file
        try:
            contents = await file.read()
            with open(file_path, "wb") as f:
                f.write(contents)
            logger.info(f"[main.py.{function_name}] File saved successfully: {unique_filename}, size: {len(contents)} bytes")
        except IOError as io_error:
            log_error("main.py", function_name, "writing file to disk", io_error, {
                "file_path": file_path,
                "filename": file.filename
            })
            raise HTTPException(status_code=500, detail=f"Failed to save file to disk: {str(io_error)}")
        except Exception as e:
            log_error("main.py", function_name, "reading/saving file", e, {
                "filename": file.filename,
                "content_type": file.content_type
            })
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
        # Return URL for the uploaded file
        return {"url": f"/uploads/{unique_filename}", "path": file_path}
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        log_error("main.py", function_name, "upload_image", e, {
            "filename": file.filename if file else None,
            "content_type": file.content_type if file else None
        })
        raise HTTPException(status_code=500, detail=f"Unexpected error during file upload: {str(e)}")


# --- WebSocket Endpoint (Multiplexed - Single Connection for All Threads) ---
@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    Single multiplexed WebSocket endpoint that handles all chat threads.
    Protocol:
    - Incoming: {"threadId": "...", "content": "...", "image": "..."}
    - Outgoing: {"threadId": "...", "reply": "..."}
    """
    function_name = "websocket_endpoint"
    client_id = str(uuid.uuid4())[:8]  # Short ID for logging
    
    try:
        await manager.connect(websocket)
        logger.info(f"[main.py.{function_name}] Client {client_id} connected")
    except Exception as e:
        log_error("main.py", function_name, "accepting WebSocket connection", e, {"client_id": client_id})
        return
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[main.py.{function_name}] Client {client_id} received message: {data[:100]}...")
            except WebSocketDisconnect:
                logger.info(f"[main.py.{function_name}] Client {client_id} disconnected normally")
                manager.disconnect(websocket)
                return
            except Exception as recv_error:
                log_error("main.py", function_name, "receiving WebSocket message", recv_error, {"client_id": client_id})
                break
            
            # Parse incoming data - must be JSON with threadId
            thread_id = None
            user_message = ""
            image_path = None
            language = "English"  # Default language
            
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    thread_id = parsed.get("threadId")
                    user_message = parsed.get("content", "")
                    image_url = parsed.get("image", None)
                    language = parsed.get("language", "English")  # Extract language
                    if image_url:
                        # Convert URL to local file path
                        image_path = os.path.join(UPLOAD_DIR, image_url.split("/uploads/")[-1])
                    logger.info(f"[main.py.{function_name}] Parsed message - thread: {thread_id}, language: {language}, has_image: {bool(image_url)}")
                else:
                    logger.warning(f"[main.py.{function_name}] Invalid message format (not a dict): {data[:50]}")
                    continue
            except json.JSONDecodeError as json_error:
                log_error("main.py", function_name, "parsing JSON message", json_error, {
                    "client_id": client_id,
                    "raw_data": data[:100]
                })
                continue
            
            # Validate threadId
            if not thread_id:
                logger.warning(f"[main.py.{function_name}] Missing threadId in message from client {client_id}")
                try:
                    await manager.send_personal_message(
                        json.dumps({"error": "Missing threadId"}), 
                        websocket
                    )
                except Exception as send_error:
                    log_error("main.py", function_name, "sending error response", send_error, {"client_id": client_id})
                continue

            # 1. Save User Message to DB
            try:
                message_doc = {
                    "role": "user",
                    "content": user_message,
                    "timestamp": datetime.datetime.utcnow()
                }
                if image_path:
                    message_doc["image"] = f"/uploads/{os.path.basename(image_path)}"
                
                # Find or Create Thread
                existing_thread = await threads_collection.find_one({"threadId": thread_id})
                
                title_text = user_message[:30] if user_message else "Image message"
                if not existing_thread:
                    logger.info(f"[main.py.{function_name}] Creating new thread: {thread_id}")
                    new_thread = {
                        "threadId": thread_id,
                        "title": title_text,
                        "messages": [message_doc],
                        "createdAt": datetime.datetime.utcnow(),
                        "updatedAt": datetime.datetime.utcnow()
                    }
                    await threads_collection.insert_one(new_thread)
                else:
                    logger.info(f"[main.py.{function_name}] Updating existing thread: {thread_id}")
                    await threads_collection.update_one(
                        {"threadId": thread_id},
                        {"$push": {"messages": message_doc}, "$set": {"updatedAt": datetime.datetime.utcnow()}}
                    )
            except Exception as db_error:
                log_error("main.py", function_name, "saving user message to database", db_error, {
                    "thread_id": thread_id,
                    "client_id": client_id
                })
                # Continue anyway to try to respond

            # 2. Determine Response (Local Data vs Gemini)
            clean_text = user_message.lower().strip() if user_message else ""
            
            # Check local data (case-insensitive keys)
            local_response = None
            if clean_text:
                for key in chat_data:
                    if key.lower() == clean_text:
                        local_response = chat_data[key]
                        logger.info(f"[main.py.{function_name}] Found local response for: {clean_text[:30]}")
                        break
            
            assistant_reply = ""
            try:
                if local_response:
                    assistant_reply = local_response
                elif image_path and os.path.exists(image_path):
                    # Use multimodal Gemini for images with language
                    logger.info(f"[main.py.{function_name}] Calling Gemini with image for thread: {thread_id}")
                    assistant_reply = await get_gemini_response_with_image(user_message, image_path, language)
                else:
                    # Text-only Gemini with language
                    logger.info(f"[main.py.{function_name}] Calling Gemini for text for thread: {thread_id}")
                    assistant_reply = await get_gemini_response(user_message, language)
            except Exception as ai_error:
                log_error("main.py", function_name, "getting AI response", ai_error, {
                    "thread_id": thread_id,
                    "has_image": bool(image_path),
                    "language": language
                })
                assistant_reply = f"Sorry, I encountered an error processing your request. Please try again."

            # 3. Save Assistant Message to DB
            try:
                assistant_doc = {
                    "role": "assistant",
                    "content": assistant_reply,
                    "timestamp": datetime.datetime.utcnow()
                }
                
                await threads_collection.update_one(
                    {"threadId": thread_id},
                    {"$push": {"messages": assistant_doc}, "$set": {"updatedAt": datetime.datetime.utcnow()}}
                )
                logger.info(f"[main.py.{function_name}] Saved assistant response to thread: {thread_id}")
            except Exception as db_error:
                log_error("main.py", function_name, "saving assistant message to database", db_error, {
                    "thread_id": thread_id,
                    "reply_length": len(assistant_reply)
                })

            # 4. Send Response back to Client (include threadId for multiplexing)
            try:
                await manager.send_personal_message(
                    json.dumps({"threadId": thread_id, "reply": assistant_reply}), 
                    websocket
                )
                logger.info(f"[main.py.{function_name}] Sent response to client {client_id} for thread: {thread_id}")
            except Exception as send_error:
                log_error("main.py", function_name, "sending response to client", send_error, {
                    "thread_id": thread_id,
                    "client_id": client_id
                })

    except WebSocketDisconnect:
        logger.info(f"[main.py.{function_name}] Client {client_id} disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        log_error("main.py", function_name, "WebSocket main loop", e, {"client_id": client_id})
        manager.disconnect(websocket)


# --- REST Endpoints for History ---

@app.get("/api/thread")
async def get_threads():
    """Get all threads sorted by last update."""
    function_name = "get_threads"
    
    try:
        logger.info(f"[main.py.{function_name}] Fetching all threads")
        cursor = threads_collection.find({}).sort("updatedAt", -1)
        threads = []
        async for document in cursor:
            # Convert ObjectId to string if needed, or exclude _id
            document["_id"] = str(document["_id"])
            threads.append(document)
        logger.info(f"[main.py.{function_name}] Found {len(threads)} threads")
        return threads
    except Exception as e:
        log_error("main.py", function_name, "fetching threads from database", e, {})
        raise HTTPException(status_code=500, detail=f"Failed to fetch threads: {str(e)}")

@app.get("/api/thread/{thread_id}")
async def get_thread(thread_id: str):
    """Get messages for a specific thread."""
    function_name = "get_thread"
    
    try:
        if not thread_id:
            logger.warning(f"[main.py.{function_name}] Missing thread_id parameter")
            raise HTTPException(status_code=400, detail="thread_id is required")
        
        logger.info(f"[main.py.{function_name}] Fetching thread: {thread_id}")
        thread = await threads_collection.find_one({"threadId": thread_id})
        
        if not thread:
            logger.warning(f"[main.py.{function_name}] Thread not found: {thread_id}")
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")
        
        messages = thread.get("messages", [])
        logger.info(f"[main.py.{function_name}] Found {len(messages)} messages for thread: {thread_id}")
        return messages
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        log_error("main.py", function_name, "fetching thread from database", e, {"thread_id": thread_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch thread: {str(e)}")

@app.delete("/api/thread/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread by ID."""
    function_name = "delete_thread"
    
    try:
        if not thread_id:
            logger.warning(f"[main.py.{function_name}] Missing thread_id parameter")
            raise HTTPException(status_code=400, detail="thread_id is required")
        
        logger.info(f"[main.py.{function_name}] Deleting thread: {thread_id}")
        result = await threads_collection.delete_one({"threadId": thread_id})
        
        if result.deleted_count == 0:
            logger.warning(f"[main.py.{function_name}] Thread not found for deletion: {thread_id}")
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")
        
        logger.info(f"[main.py.{function_name}] Successfully deleted thread: {thread_id}")
        return {"success": "Thread deleted successfully", "thread_id": thread_id}
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        log_error("main.py", function_name, "deleting thread from database", e, {"thread_id": thread_id})
        raise HTTPException(status_code=500, detail=f"Failed to delete thread: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
