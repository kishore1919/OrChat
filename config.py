import os
import base64
import configparser
import getpass
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from rich.console import Console

console = Console()

def generate_key() -> bytes:
    """Generate a key for encryption."""
    return Fernet.generate_key()

def encrypt_api_key(api_key: str, key: bytes) -> bytes:
    """Encrypt API key using Fernet symmetric encryption."""
    return Fernet(key).encrypt(api_key.encode())

def decrypt_api_key(encrypted_key: bytes, key: bytes) -> str:
    """Decrypt API key using Fernet symmetric encryption."""
    try:
        return Fernet(key).decrypt(encrypted_key).decode()
    except Exception:
        return None

def get_or_create_master_key() -> bytes:
    """Get or create master encryption key with secure file permissions."""
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.key')
    
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    
    # Create new key with secure permissions
    key = generate_key()
    with open(key_file, 'wb') as f:
        f.write(key)
    
    # Set restrictive permissions on Unix-like systems
    if os.name != 'nt':
        os.chmod(key_file, 0o600)
    
    return key

def validate_api_key_format(api_key: str) -> bool:
    """Validate API key format and warn about incorrect format."""
    if not api_key or len(api_key) < 20:
        return False
    
    if not api_key.startswith('sk-or-'):
        console.print("[yellow]Warning: API key doesn't match expected OpenRouter format[/yellow]")
    
    return True

def secure_input_api_key() -> str:
    """Securely input API key without echoing to console."""
    try:
        api_key = getpass.getpass("Enter your OpenRouter API key (input hidden): ")
        if not validate_api_key_format(api_key):
            console.print("[red]Invalid API key format[/red]")
            return None
        return api_key
    except KeyboardInterrupt:
        console.print("\n[yellow]API key input cancelled[/yellow]")
        return None

def load_config() -> dict:
    """Load configuration from .env file and/or config.ini with optimized handling."""
    # Load from environment first
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")

    # Default configuration
    defaults = {
        'api_key': api_key,
        'model': "",
        'temperature': 0.7,
        'system_instructions': "",
        'theme': 'default',
        'max_tokens': 0,
        'autosave_interval': 300,
        'streaming': True,
        'thinking_mode': False
    }

    # Try to load from config.ini
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    if not os.path.exists(config_file):
        return defaults

    config = configparser.ConfigParser()
    config.read(config_file)

    # Load API key (encrypted or plaintext)
    if 'API' in config:
        if 'OPENROUTER_API_KEY_ENCRYPTED' in config['API']:
            try:
                encrypted_key_b64 = config['API']['OPENROUTER_API_KEY_ENCRYPTED']
                encrypted_key = base64.b64decode(encrypted_key_b64)
                master_key = get_or_create_master_key()
                decrypted_key = decrypt_api_key(encrypted_key, master_key)
                if decrypted_key:
                    defaults['api_key'] = decrypted_key
                else:
                    console.print("[yellow]Warning: Could not decrypt API key. Please re-enter it.[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Warning: Error decrypting API key: {e}[/yellow]")
        elif 'OPENROUTER_API_KEY' in config['API'] and config['API']['OPENROUTER_API_KEY']:
            defaults['api_key'] = config['API']['OPENROUTER_API_KEY']

    # Load settings
    if 'SETTINGS' in config:
        settings = config['SETTINGS']
        defaults.update({
            'model': settings.get('MODEL', ''),
            'temperature': settings.getfloat('TEMPERATURE', 0.7),
            'system_instructions': settings.get('SYSTEM_INSTRUCTIONS', ''),
            'theme': settings.get('THEME', 'default'),
            'max_tokens': settings.getint('MAX_TOKENS', 0),
            'autosave_interval': settings.getint('AUTOSAVE_INTERVAL', 300),
            'streaming': settings.getboolean('STREAMING', True),
            'thinking_mode': settings.getboolean('THINKING_MODE', False)
        })

    return defaults

def save_config(config_data: dict) -> None:
    """Save configuration to config.ini with encrypted API key."""
    config = configparser.ConfigParser()
    
    # Handle API key encryption
    if 'OPENROUTER_API_KEY' not in os.environ and config_data.get('api_key'):
        try:
            master_key = get_or_create_master_key()
            encrypted_key = encrypt_api_key(config_data['api_key'], master_key)
            encrypted_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
            config['API'] = {'OPENROUTER_API_KEY_ENCRYPTED': encrypted_key_b64}
        except Exception as e:
            console.print(f"[yellow]Warning: Could not encrypt API key: {e}. Saving in plaintext.[/yellow]")
            config['API'] = {'OPENROUTER_API_KEY': config_data['api_key']}
    elif 'OPENROUTER_API_KEY' not in os.environ:
        config['API'] = {'OPENROUTER_API_KEY': config_data['api_key']}
    
    # Save settings
    config['SETTINGS'] = {
        'MODEL': config_data['model'],
        'TEMPERATURE': str(config_data['temperature']),
        'SYSTEM_INSTRUCTIONS': config_data['system_instructions'],
        'THEME': config_data['theme'],
        'MAX_TOKENS': str(config_data['max_tokens']),
        'AUTOSAVE_INTERVAL': str(config_data['autosave_interval']),
        'STREAMING': str(config_data['streaming']),
        'THINKING_MODE': str(config_data['thinking_mode'])
    }

    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    
    try:
        with open(config_file, 'w', encoding="utf-8") as f:
            config.write(f)
        
        # Set restrictive permissions on Unix-like systems
        if os.name != 'nt':
            os.chmod(config_file, 0o600)
            
    except Exception as e:
        console.print(f"[red]Error saving configuration: {e}[/red]")
        
        console.print("[green]Configuration saved successfully![/green]")
    except Exception as e:
        console.print(f"[red]Error saving configuration: {str(e)}[/red]")
