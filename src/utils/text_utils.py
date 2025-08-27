"""
Utility functions and helpers for OrChat.

This module provides various utility functions for:
- Terminal operations and display formatting
- Time and file size formatting
- Token counting for AI models
- Text processing and validation
"""

import os
from typing import Union

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


def clear_terminal() -> None:
    """
    Clear the terminal screen using ANSI escape codes.
    
    This is cross-platform compatible and works in most terminal environments.
    """
    print("\x1b[2J\x1b[H")


def format_time_delta(delta_seconds: float) -> str:
    """
    Format time delta into human-readable string.
    
    Args:
        delta_seconds: Time difference in seconds
        
    Returns:
        Formatted time string (e.g., "250ms", "1.5s", "2m 30.0s")
    """
    if delta_seconds < 1:
        return f"{delta_seconds*1000:.0f}ms"
    elif delta_seconds < 60:
        return f"{delta_seconds:.1f}s"
    else:
        mins, secs = divmod(delta_seconds, 60)
        return f"{int(mins)}m {secs:.1f}s"


def format_file_size(size_bytes: int) -> str:
    """
    Format file size into human-readable string.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted size string (e.g., "1.5 KB", "2.3 MB", "1.0 GB")
    """
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def count_tokens(text: str, model_name: str = "cl100k_base") -> int:
    """
    Count the number of tokens in a given text string using tiktoken.
    
    This function is essential for managing API costs and token limits
    when working with AI models.
    
    Args:
        text: The text to count tokens for
        model_name: The model name to get the appropriate tokenizer for
        
    Returns:
        Number of tokens in the text
    """
    if not HAS_TIKTOKEN:
        # Rough approximation: 1 token ≈ 4 characters for English text
        return len(text) // 4
    
    try:
        # Try to get the encoding for the specific model
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback to a default encoding for unknown models
        # cl100k_base is used by GPT-4, GPT-3.5-turbo, and many other models
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    return len(tokens)


def validate_file_path(file_path: str) -> bool:
    """
    Validate if a file path exists and is accessible.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if the file exists and is readable, False otherwise
    """
    try:
        return os.path.isfile(file_path) and os.access(file_path, os.R_OK)
    except (OSError, TypeError):
        return False


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with an optional suffix.
    
    Args:
        text: The text to truncate
        max_length: Maximum length of the truncated text (including suffix)
        suffix: String to append when text is truncated
        
    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_length:
        return text
    
    # Account for suffix length
    truncate_length = max_length - len(suffix)
    if truncate_length <= 0:
        return suffix[:max_length]
    
    return text[:truncate_length] + suffix


def safe_filename(filename: str) -> str:
    """
    Convert a string to a safe filename by removing/replacing invalid characters.
    
    Args:
        filename: The original filename
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    # Characters that are invalid in filenames on various operating systems
    invalid_chars = '<>:"/\\|?*'
    
    # Replace invalid characters with underscores
    safe_name = ''.join('_' if char in invalid_chars else char for char in filename)
    
    # Remove leading/trailing whitespace and dots
    safe_name = safe_name.strip(' .')
    
    # Ensure the filename isn't empty
    if not safe_name:
        safe_name = "untitled"
    
    return safe_name


def format_model_name(model_id: str) -> str:
    """
    Format a model ID into a more readable display name.
    
    Args:
        model_id: The raw model ID (e.g., "anthropic/claude-3-opus-20240229")
        
    Returns:
        Formatted model name for display
    """
    # Remove provider prefix if present
    if '/' in model_id:
        model_name = model_id.split('/', 1)[1]
    else:
        model_name = model_id
    
    # Replace hyphens with spaces and capitalize words
    formatted = model_name.replace('-', ' ').title()
    
    # Handle special cases for better readability
    formatted = formatted.replace('Gpt', 'GPT')
    formatted = formatted.replace('Api', 'API')
    formatted = formatted.replace('Ai', 'AI')
    
    return formatted


def estimate_cost(prompt_tokens: int, completion_tokens: int, 
                  prompt_price: float, completion_price: float) -> float:
    """
    Estimate the cost of an API call based on token usage and pricing.
    
    Args:
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        prompt_price: Price per token for prompt (usually per 1M tokens)
        completion_price: Price per token for completion (usually per 1M tokens)
        
    Returns:
        Estimated cost in the same currency as the pricing
    """
    # Convert per-million-token pricing to per-token pricing
    prompt_cost = (prompt_tokens * prompt_price) / 1_000_000
    completion_cost = (completion_tokens * completion_price) / 1_000_000
    
    return prompt_cost + completion_cost


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format a currency amount for display.
    
    Args:
        amount: The amount to format
        currency: The currency code (e.g., "USD", "EUR")
        
    Returns:
        Formatted currency string
    """
    if currency == "USD":
        symbol = "$"
    elif currency == "EUR":
        symbol = "€"
    elif currency == "GBP":
        symbol = "£"
    else:
        symbol = f"{currency} "
    
    if amount < 0.01:
        return f"{symbol}{amount:.4f}"
    elif amount < 1:
        return f"{symbol}{amount:.3f}"
    else:
        return f"{symbol}{amount:.2f}"
