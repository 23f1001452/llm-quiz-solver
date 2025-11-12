# ============================================================================
# config.py - Configuration Management
# ============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Student credentials
    STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
    SECRET_KEY = os.getenv("SECRET_KEY")
    
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    AI21_API_KEY = os.getenv("AI21_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # App settings
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "180"))
    
    # LLM settings
    DEFAULT_MODEL = "llama-3.3-70b-versatile"  # Updated Groq model
    MAX_TOKENS = 4000
    TEMPERATURE = 0.1  # Low temperature for more consistent results
    
    @classmethod
    def validate(cls):
        """Validate that required config is present"""
        required = ["STUDENT_EMAIL", "SECRET_KEY"]
        missing = [key for key in required if not getattr(cls, key)]
        
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")
        
        # Check that at least one LLM API key is present
        if not any([cls.GROQ_API_KEY, cls.AI21_API_KEY, cls.OPENAI_API_KEY]):
            raise ValueError("At least one LLM API key is required")
        
        return True