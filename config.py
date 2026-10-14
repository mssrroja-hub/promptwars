import os

class Config:
    PORT = int(os.environ.get("PORT", 5000))
    HOST = os.environ.get("HOST", "127.0.0.1")
    DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1")
    SECRET_KEY = os.environ.get("SECRET_KEY", "mentinous_prototype_secret_key_change_in_production_32chars")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mentinous.db"))
    
    # Optional external AI API configuration
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
