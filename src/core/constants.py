"""
Application constants and configuration values.

This module contains all the constant values used throughout the OrChat application,
including version information, API endpoints, file constraints, and other static values.
"""

# ============================================================================
# APPLICATION CONSTANTS
# ============================================================================

# App metadata
APP_NAME = "OrChat"
APP_VERSION = "1.3.1"
REPO_URL = "https://github.com/oop7/OrChat"
API_URL = "https://api.github.com/repos/oop7/OrChat/releases/latest"

# Security & file constraints
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit for file uploads
ALLOWED_FILE_EXTENSIONS = {
    # Text files - commonly used document formats
    '.txt', '.md', '.json', '.xml', '.csv',
    
    # Code files - popular programming languages
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.swift',
    
    # Web files - frontend development
    '.html', '.css',
    
    # Image files - common image formats for analysis
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'
}

# Default configuration values
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 0  # 0 means no limit
DEFAULT_AUTOSAVE_INTERVAL = 300  # 5 minutes in seconds
DEFAULT_STREAMING = True
DEFAULT_THINKING_MODE = False

# API Configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODELS_ENDPOINT = f"{OPENROUTER_BASE_URL}/models"
CHAT_ENDPOINT = f"{OPENROUTER_BASE_URL}/chat/completions"

# Session configuration
SESSION_DIRECTORY = "sessions"
CONFIG_FILE = "config.ini"
ENV_FILE = ".env"
KEY_FILE = ".key"
