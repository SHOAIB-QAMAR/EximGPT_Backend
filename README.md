# SigmaGPT Backend API

A FastAPI-based backend for the SigmaGPT chat application with Google Gemini AI integration.

## 🚀 Features

- **WebSocket Chat**: Real-time multiplexed chat with AI responses
- **Image Upload**: Support for image-based conversations
- **MongoDB Storage**: Persistent chat thread storage
- **Gemini AI**: Integration with Google's Gemini AI model
- **Multi-language Support**: Responses in user's preferred language

## 📋 Prerequisites

- Python 3.9+
- MongoDB Atlas account (or local MongoDB)
- Google Gemini API key

## 🛠️ Local Development Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Backend_FastAPI
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
MONGODB_URI=mongodb+srv://your_username:your_password@cluster.mongodb.net/your_database
GEMINI_API_KEY=your_gemini_api_key
```

### 5. Run the Server

```bash
uvicorn main:app --reload --port 8080
```

The API will be available at `http://localhost:8080`

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/thread` | Get all chat threads |
| `GET` | `/api/thread/{thread_id}` | Get messages for a thread |
| `DELETE` | `/api/thread/{thread_id}` | Delete a thread |
| `POST` | `/api/upload` | Upload an image |
| `WS` | `/ws/chat` | WebSocket for real-time chat |

## ☁️ Deployment Options

### Option 1: Railway

1. Connect your GitHub repository to [Railway](https://railway.app)
2. Add environment variables in Railway dashboard
3. Railway will auto-detect the Procfile and deploy

### Option 2: Render

1. Create a new Web Service on [Render](https://render.com)
2. Connect your GitHub repository
3. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in Render dashboard

### Option 3: Heroku

1. Install Heroku CLI: `brew install heroku/brew/heroku`
2. Login and create app:
   ```bash
   heroku login
   heroku create your-app-name
   ```
3. Set environment variables:
   ```bash
   heroku config:set MONGODB_URI=your_mongodb_uri
   heroku config:set GEMINI_API_KEY=your_gemini_key
   ```
4. Deploy:
   ```bash
   git push heroku main
   ```

### Option 4: DigitalOcean App Platform

1. Create a new App from GitHub repository
2. Configure as Python app
3. Set run command: `uvicorn main:app --host 0.0.0.0 --port 8080`
4. Add environment variables in the dashboard

### Option 5: VPS (Ubuntu/Debian)

```bash
# Install Python and pip
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Clone and setup
git clone <your-repo-url>
cd Backend_FastAPI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file with your credentials
nano .env

# Run with gunicorn for production
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

## 🔒 Security Notes

- **Never commit `.env` file** - it contains secrets!
- Use environment variables on your hosting platform
- The `.gitignore` file is configured to exclude sensitive files
- Consider using a secrets manager for production

## 📁 Project Structure

```
Backend_FastAPI/
├── main.py              # FastAPI application entry point
├── database.py          # MongoDB connection and setup
├── gemini_service.py    # Google Gemini AI integration
├── chat_data.py         # Predefined chat responses
├── requirements.txt     # Python dependencies
├── Procfile             # For Heroku/Railway deployment
├── .env.example         # Environment variables template
├── .gitignore           # Git ignore rules
├── uploads/             # User uploaded images
│   └── .gitkeep
└── README.md            # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is private and proprietary.
