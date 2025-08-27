"""
OrChat - AI Chat Application powered by OpenRouter

This is the main entry point for OrChat, a feature-rich AI chat interface.
All functionality has been properly organized into modules under the src/ directory.

Usage:
    python main.py [options]

Author: OrChat Team  
License: MIT
"""

import sys
import os

def main():
    """Main entry point that imports and runs the application."""
    try:
        # Add the current directory to Python path for imports
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        # Import the main application class from the refactored code
        from main_refactored import OrChatApplication
        
        # Create and run the application
        app = OrChatApplication()
        app.run()
        
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("Please ensure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting OrChat...")
    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    from src.core.constants import APP_VERSION
    print(f"OrChat v{APP_VERSION} - Starting...")
    main()
