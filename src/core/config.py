"""
Configuration management module for OrChat.

This module handles all configuration-related operations including:
- Loading and saving configuration files
- Encrypting and decrypting API keys
- Managing user preferences and settings
- Validating configuration values
"""

import os
import base64
import configparser
import getpass
from typing import Dict, Optional
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from rich.console import Console

from .constants import (
    DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, DEFAULT_AUTOSAVE_INTERVAL,
    DEFAULT_STREAMING, DEFAULT_THINKING_MODE, CONFIG_FILE, ENV_FILE, KEY_FILE
)

console = Console()


class ConfigurationManager:
    """
    Manages all configuration operations for OrChat.
    
    This class provides a centralized way to handle configuration loading,
    saving, encryption, and validation.
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory where config files are stored. 
                       Defaults to the current script directory.
        """
        self.config_dir = config_dir or os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.config_dir, CONFIG_FILE)
        self.key_file = os.path.join(self.config_dir, KEY_FILE)
        
    def generate_key(self) -> bytes:
        """Generate a new encryption key for API key security."""
        return Fernet.generate_key()

    def encrypt_api_key(self, api_key: str, key: bytes) -> bytes:
        """
        Encrypt API key using Fernet symmetric encryption.
        
        Args:
            api_key: The API key to encrypt
            key: The encryption key
            
        Returns:
            Encrypted API key as bytes
        """
        return Fernet(key).encrypt(api_key.encode())

    def decrypt_api_key(self, encrypted_key: bytes, key: bytes) -> Optional[str]:
        """
        Decrypt API key using Fernet symmetric encryption.
        
        Args:
            encrypted_key: The encrypted API key
            key: The decryption key
            
        Returns:
            Decrypted API key as string, or None if decryption fails
        """
        try:
            return Fernet(key).decrypt(encrypted_key).decode()
        except Exception:
            return None

    def get_or_create_master_key(self) -> bytes:
        """
        Get existing master encryption key or create a new one.
        
        Returns:
            The master encryption key as bytes
        """
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        
        # Create new key with secure permissions
        key = self.generate_key()
        with open(self.key_file, 'wb') as f:
            f.write(key)
        
        # Set restrictive permissions on Unix-like systems
        if os.name != 'nt':
            os.chmod(self.key_file, 0o600)
        
        return key

    def validate_api_key_format(self, api_key: str) -> bool:
        """
        Validate API key format and provide user feedback.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            True if the API key appears to be valid, False otherwise
        """
        if not api_key or len(api_key) < 20:
            return False
        
        if not api_key.startswith('sk-or-'):
            console.print("[yellow]Warning: API key doesn't match expected OpenRouter format[/yellow]")
        
        return True

    def secure_input_api_key(self) -> Optional[str]:
        """
        Securely prompt user for API key without echoing to console.
        
        Returns:
            Valid API key or None if input was cancelled/invalid
        """
        try:
            api_key = getpass.getpass("Enter your OpenRouter API key (input hidden): ")
            if not self.validate_api_key_format(api_key):
                console.print("[red]Invalid API key format[/red]")
                return None
            return api_key
        except KeyboardInterrupt:
            console.print("\n[yellow]API key input cancelled[/yellow]")
            return None

    def get_default_config(self) -> Dict:
        """
        Get the default configuration values.
        
        Returns:
            Dictionary with default configuration values
        """
        # Load from environment first
        load_dotenv()
        api_key = os.getenv("OPENROUTER_API_KEY")

        return {
            'api_key': api_key,
            'model': "",
            'temperature': DEFAULT_TEMPERATURE,
            'system_instructions': "",
            'theme': 'default',
            'max_tokens': DEFAULT_MAX_TOKENS,
            'autosave_interval': DEFAULT_AUTOSAVE_INTERVAL,
            'streaming': DEFAULT_STREAMING,
            'thinking_mode': DEFAULT_THINKING_MODE
        }

    def load_config(self) -> Dict:
        """
        Load configuration from .env file and/or config.ini.
        
        Returns:
            Dictionary containing all configuration values
        """
        defaults = self.get_default_config()

        # Return defaults if config file doesn't exist
        if not os.path.exists(self.config_file):
            return defaults

        config = configparser.ConfigParser()
        config.read(self.config_file)

        # Load API key (encrypted or plaintext)
        if 'API' in config:
            api_key = self._load_api_key_from_config(config)
            if api_key:
                defaults['api_key'] = api_key

        # Load settings
        if 'SETTINGS' in config:
            self._load_settings_from_config(config, defaults)

        return defaults

    def _load_api_key_from_config(self, config: configparser.ConfigParser) -> Optional[str]:
        """
        Load and decrypt API key from configuration.
        
        Args:
            config: The configuration parser object
            
        Returns:
            Decrypted API key or None if unable to load
        """
        api_section = config['API']
        
        # Try encrypted key first
        if 'OPENROUTER_API_KEY_ENCRYPTED' in api_section:
            try:
                encrypted_key_b64 = api_section['OPENROUTER_API_KEY_ENCRYPTED']
                encrypted_key = base64.b64decode(encrypted_key_b64)
                master_key = self.get_or_create_master_key()
                decrypted_key = self.decrypt_api_key(encrypted_key, master_key)
                
                if decrypted_key:
                    return decrypted_key
                else:
                    console.print("[yellow]Warning: Could not decrypt API key. Please re-enter it.[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Warning: Error decrypting API key: {e}[/yellow]")
        
        # Fall back to plaintext key
        elif 'OPENROUTER_API_KEY' in api_section and api_section['OPENROUTER_API_KEY']:
            return api_section['OPENROUTER_API_KEY']
        
        return None

    def _load_settings_from_config(self, config: configparser.ConfigParser, defaults: Dict):
        """
        Load settings from configuration file into defaults dictionary.
        
        Args:
            config: The configuration parser object
            defaults: Dictionary to update with loaded settings
        """
        settings = config['SETTINGS']
        defaults.update({
            'model': settings.get('MODEL', ''),
            'temperature': settings.getfloat('TEMPERATURE', DEFAULT_TEMPERATURE),
            'system_instructions': settings.get('SYSTEM_INSTRUCTIONS', ''),
            'theme': settings.get('THEME', 'default'),
            'max_tokens': settings.getint('MAX_TOKENS', DEFAULT_MAX_TOKENS),
            'autosave_interval': settings.getint('AUTOSAVE_INTERVAL', DEFAULT_AUTOSAVE_INTERVAL),
            'streaming': settings.getboolean('STREAMING', DEFAULT_STREAMING),
            'thinking_mode': settings.getboolean('THINKING_MODE', DEFAULT_THINKING_MODE)
        })

    def save_config(self, config_data: Dict) -> None:
        """
        Save configuration to config.ini with encrypted API key.
        
        Args:
            config_data: Dictionary containing configuration values to save
        """
        config = configparser.ConfigParser()
        
        # Handle API key encryption
        self._save_api_key_to_config(config, config_data)
        
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

        try:
            with open(self.config_file, 'w', encoding="utf-8") as f:
                config.write(f)
            
            # Set restrictive permissions on Unix-like systems
            if os.name != 'nt':
                os.chmod(self.config_file, 0o600)
                
            console.print("[green]Configuration saved successfully![/green]")
        except Exception as e:
            console.print(f"[red]Error saving configuration: {str(e)}[/red]")

    def _save_api_key_to_config(self, config: configparser.ConfigParser, config_data: Dict):
        """
        Save API key to configuration with encryption if not in environment.
        
        Args:
            config: The configuration parser object
            config_data: Dictionary containing configuration values
        """
        # Don't save API key if it's in environment variables
        if 'OPENROUTER_API_KEY' in os.environ:
            return
            
        api_key = config_data.get('api_key')
        if not api_key:
            return
            
        try:
            # Try to encrypt the API key
            master_key = self.get_or_create_master_key()
            encrypted_key = self.encrypt_api_key(api_key, master_key)
            encrypted_key_b64 = base64.b64encode(encrypted_key).decode('utf-8')
            config['API'] = {'OPENROUTER_API_KEY_ENCRYPTED': encrypted_key_b64}
        except Exception as e:
            # Fall back to plaintext if encryption fails
            console.print(f"[yellow]Warning: Could not encrypt API key: {e}. Saving in plaintext.[/yellow]")
            config['API'] = {'OPENROUTER_API_KEY': api_key}


# Global configuration manager instance
config_manager = ConfigurationManager()

# Convenience functions for backward compatibility
def load_config() -> Dict:
    """Load configuration using the global configuration manager."""
    return config_manager.load_config()

def save_config(config_data: Dict) -> None:
    """Save configuration using the global configuration manager."""
    config_manager.save_config(config_data)

def secure_input_api_key() -> Optional[str]:
    """Securely input API key using the global configuration manager."""
    return config_manager.secure_input_api_key()
