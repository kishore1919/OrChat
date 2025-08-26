# ============================================================================
# APPLICATION CONSTANTS
# ============================================================================

# App metadata
APP_NAME = "OrChat"
APP_VERSION = "1.3.1"
REPO_URL = "https://github.com/oop7/OrChat"
API_URL = "https://api.github.com/repos/oop7/OrChat/releases/latest"

# Security & file constraints
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit
ALLOWED_FILE_EXTENSIONS = {
    # Text files
    '.txt', '.md', '.json', '.xml', '.csv',
    # Code files  
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.swift',
    # Web files
    '.html', '.css',
    # Image files
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'
}
