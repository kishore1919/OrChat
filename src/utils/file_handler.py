"""
File handling module for OrChat.

This module handles all file operations including:
- Conversation saving in multiple formats (markdown, JSON, HTML)
- File upload processing and security validation
- File attachment handling for multimodal models
- Content extraction and formatting for different file types
"""

import base64
import datetime
import json
import os
import re
from typing import Dict, List, Tuple, Any
from rich.console import Console

from ..core.constants import MAX_FILE_SIZE, ALLOWED_FILE_EXTENSIONS
from ..utils.text_utils import format_file_size, safe_filename

console = Console()


class FileHandler:
    """
    Handles file operations for OrChat.
    
    This class provides comprehensive file handling capabilities including
    security validation, content extraction, and conversation persistence.
    """
    
    def __init__(self):
        """Initialize the file handler."""
        self.console = Console()
        
    def save_conversation(self, conversation_history: List[Dict], 
                         filename: str, fmt: str = "markdown") -> str:
        """
        Save conversation to file in various formats.
        
        Args:
            conversation_history: List of conversation message dictionaries
            filename: Output filename
            fmt: Format to save in ("markdown", "json", "html")
            
        Returns:
            The filename that was saved to
        """
        # Ensure the filename is safe
        safe_name = safe_filename(filename)
        
        if fmt == "markdown":
            return self._save_as_markdown(conversation_history, safe_name)
        elif fmt == "json":
            return self._save_as_json(conversation_history, safe_name)
        elif fmt == "html":
            return self._save_as_html(conversation_history, safe_name)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    def _save_as_markdown(self, conversation_history: List[Dict], filename: str) -> str:
        """Save conversation as Markdown format."""
        with open(filename, 'w', encoding="utf-8") as f:
            f.write("# OrChat Conversation\n\n")
            f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for msg in conversation_history:
                if msg['role'] == 'system':
                    f.write(f"## System Instructions\n\n{msg['content']}\n\n")
                else:
                    f.write(f"## {msg['role'].capitalize()}\n\n{msg['content']}\n\n")
        
        return filename

    def _save_as_json(self, conversation_history: List[Dict], filename: str) -> str:
        """Save conversation as JSON format."""
        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(conversation_history, f, indent=2, ensure_ascii=False)
        
        return filename

    def _save_as_html(self, conversation_history: List[Dict], filename: str) -> str:
        """Save conversation as HTML format."""
        with open(filename, 'w', encoding="utf-8") as f:
            f.write(self._generate_html_template())
            f.write("<h1>OrChat Conversation</h1>\n")
            f.write(f"<p>Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")

            for msg in conversation_history:
                f.write(f"<div class='{msg['role']}'>\n")
                f.write(f"<h2>{msg['role'].capitalize()}</h2>\n")
                content_html = self._escape_html(msg['content']).replace('\n', '<br>')
                f.write(f"<p>{content_html}</p>\n")
                f.write("</div>\n")

            f.write("</body>\n</html>")
        
        return filename

    def _generate_html_template(self) -> str:
        """Generate HTML template with CSS styling."""
        return """<!DOCTYPE html>
<html>
<head>
<title>OrChat Conversation</title>
<style>
body { 
    font-family: Arial, sans-serif; 
    max-width: 800px; 
    margin: 0 auto; 
    padding: 20px; 
    line-height: 1.6;
}
.system { 
    background-color: #f0f0f0; 
    padding: 15px; 
    border-radius: 8px; 
    border-left: 4px solid #666;
    margin: 10px 0;
}
.user { 
    background-color: #e1f5fe; 
    padding: 15px; 
    border-radius: 8px; 
    border-left: 4px solid #2196f3;
    margin: 10px 0; 
}
.assistant { 
    background-color: #f1f8e9; 
    padding: 15px; 
    border-radius: 8px; 
    border-left: 4px solid #4caf50;
    margin: 10px 0; 
}
h1 { color: #333; text-align: center; }
h2 { margin-top: 0; color: #555; }
</style>
</head>
<body>
"""

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        return text

    def validate_file_security(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate file for security concerns before processing.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                return False, "File does not exist"
            
            if not os.path.isfile(file_path):
                return False, "Path is not a file"
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                return False, (f"File too large ({format_file_size(file_size)}). "
                              f"Maximum allowed: {format_file_size(MAX_FILE_SIZE)}")
            
            # Check file extension
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in ALLOWED_FILE_EXTENSIONS:
                return False, (f"File type '{file_ext}' not allowed. "
                              f"Allowed types: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}")
            
            # Basic path traversal prevention
            normalized_path = os.path.normpath(file_path)
            if '..' in normalized_path:
                return False, "Invalid file path detected"
            
            # Check for executable files (additional security)
            dangerous_extensions = {'.exe', '.bat', '.cmd', '.com', '.scr', 
                                  '.pif', '.vbs', '.jar', '.sh'}
            if file_ext in dangerous_extensions:
                return False, f"Executable file type '{file_ext}' not allowed for security reasons"
            
            return True, "File validation passed"
        
        except Exception as e:
            return False, f"File validation error: {str(e)}"

    def process_file_upload(self, file_path: str, conversation_history: List[Dict]) -> Tuple[bool, str]:
        """
        Process a file upload and add its contents to the conversation.
        
        Args:
            file_path: Path to the file to process
            conversation_history: List to append the file content to
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate file security first
            is_valid, validation_message = self.validate_file_security(file_path)
            if not is_valid:
                return False, f"Security validation failed: {validation_message}"

            # Read file with proper encoding handling
            content = self._read_file_content(file_path)
            
            # Limit content size for processing
            max_content_length = 50000  # 50KB of text content
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n\n[Content truncated due to size limit]"

            file_ext = os.path.splitext(file_path)[1].lower()
            file_name = os.path.basename(file_path)
            safe_file_name = safe_filename(file_name)

            # Determine file type and create appropriate message
            message = self._format_file_message(safe_file_name, file_ext, content)

            # Add to conversation history
            conversation_history.append({"role": "user", "content": message})
            
            file_type = self._get_file_type_description(file_ext)
            return True, f"File '{safe_file_name}' uploaded successfully as {file_type}."
            
        except Exception as e:
            console.print(f"[red]File processing error: {str(e)}[/red]")
            return False, f"Error processing file: {str(e)}"

    def _read_file_content(self, file_path: str) -> str:
        """Read file content with proper encoding handling."""
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding for non-UTF8 files
            try:
                with open(file_path, 'r', encoding="latin-1") as f:
                    return f.read()
            except Exception:
                # Last resort: read as binary and decode with errors replaced
                with open(file_path, 'rb') as f:
                    return f.read().decode('utf-8', errors='replace')

    def _format_file_message(self, file_name: str, file_ext: str, content: str) -> str:
        """Format file content into an appropriate message."""
        if file_ext in ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.ts', '.swift']:
            return f"I'm uploading a code file named '{file_name}'. Please analyze it:\n\n```{file_ext[1:]}\n{content}\n```"
        elif file_ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.css']:
            return f"I'm uploading a text file named '{file_name}'. Here are its contents:\n\n{content}"
        else:
            return f"I'm uploading a file named '{file_name}'. Here are its contents:\n\n{content}"

    def _get_file_type_description(self, file_ext: str) -> str:
        """Get a human-readable description of the file type."""
        type_map = {
            '.py': 'Python code', '.js': 'JavaScript code', '.ts': 'TypeScript code',
            '.java': 'Java code', '.cpp': 'C++ code', '.c': 'C code',
            '.cs': 'C# code', '.go': 'Go code', '.rb': 'Ruby code',
            '.php': 'PHP code', '.swift': 'Swift code',
            '.txt': 'text file', '.md': 'Markdown document', '.csv': 'CSV data',
            '.json': 'JSON data', '.xml': 'XML document',
            '.html': 'HTML document', '.css': 'CSS stylesheet'
        }
        return type_map.get(file_ext, 'file')

    def handle_attachment(self, file_path: str, conversation_history: List[Dict]) -> Tuple[bool, str]:
        """
        Enhanced file attachment handling with preview and metadata.
        
        This method handles both text files and images, formatting them
        appropriately for multimodal AI models.
        
        Args:
            file_path: Path to the file to attach
            conversation_history: List to append the attachment to
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate file security first
            is_valid, validation_message = self.validate_file_security(file_path)
            if not is_valid:
                return False, f"Security validation failed: {validation_message}"

            # Get file information
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            file_size = os.path.getsize(file_path)
            file_size_formatted = format_file_size(file_size)
            safe_file_name = safe_filename(file_name)

            # Determine file type and extract content
            file_type, content = self._extract_file_content(file_path, file_ext)

            # Create a message that includes metadata about the attachment
            message = f"I'm sharing a file: **{safe_file_name}** ({file_type}, {file_size_formatted})\n\n"

            if file_type == "image":
                return self._handle_image_attachment(file_path, file_size, file_ext, 
                                                   safe_file_name, message, conversation_history)
            else:
                # For other file types, add content to the message
                message += content
                conversation_history.append({"role": "user", "content": message})
                return True, f"File '{safe_file_name}' attached successfully as {file_type}."

        except Exception as e:
            console.print(f"[red]Attachment processing error: {str(e)}[/red]")
            return False, f"Error processing attachment: {str(e)}"

    def _handle_image_attachment(self, file_path: str, file_size: int, file_ext: str,
                               safe_file_name: str, message: str, 
                               conversation_history: List[Dict]) -> Tuple[bool, str]:
        """Handle image file attachments."""
        # Image size limit (5MB)
        if file_size > 5 * 1024 * 1024:
            return False, "Image file too large (max 5MB)"
        
        try:
            with open(file_path, 'rb') as img_file:
                image_data = img_file.read()
                
                # Basic image validation (check for image headers)
                if not self._is_valid_image(image_data):
                    return False, "Invalid or corrupted image file"
                
                base64_image = base64.b64encode(image_data).decode('utf-8')

            # Add to messages with proper format for multimodal models
            conversation_history.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": f"data:image/{file_ext[1:]};base64,{base64_image}"}}
                ]
            })
            return True, f"Image '{safe_file_name}' attached successfully."
            
        except Exception as e:
            return False, f"Error processing image: {str(e)}"

    def _is_valid_image(self, image_data: bytes) -> bool:
        """Validate image data by checking file headers."""
        return (image_data.startswith(b'\xff\xd8') or  # JPEG
                image_data.startswith(b'\x89PNG') or  # PNG
                image_data.startswith(b'GIF8') or     # GIF
                image_data.startswith(b'RIFF'))       # WebP

    def _extract_file_content(self, file_path: str, file_ext: str) -> Tuple[str, str]:
        """
        Extract and format content from different file types.
        
        Args:
            file_path: Path to the file
            file_ext: File extension
            
        Returns:
            Tuple of (file_type_description, formatted_content)
        """
        # Image files
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            return "image", ""

        # PDF files (placeholder for future PDF processing)
        elif file_ext in ['.pdf']:
            return "PDF document", "[PDF content not displayed in chat, but AI can analyze the document]"

        # Code files
        elif file_ext in ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.ts', '.swift']:
            content = self._read_file_content(file_path)
            return "code", f"```{file_ext[1:]}\n{content}\n```"

        # Text files
        elif file_ext in ['.txt', '.md', '.csv']:
            content = self._read_file_content(file_path)
            return "text", content

        # Data files
        elif file_ext in ['.json', '.xml']:
            content = self._read_file_content(file_path)
            return "data", f"```{file_ext[1:]}\n{content}\n```"

        # Web files
        elif file_ext in ['.html', '.css']:
            content = self._read_file_content(file_path)
            return "web", f"```{file_ext[1:]}\n{content}\n```"

        # Archive files
        elif file_ext in ['.zip', '.tar', '.gz', '.rar']:
            return "archive", "[Archive content not displayed in chat]"

        # Unknown files
        else:
            try:
                content = self._read_file_content(file_path)
                return "text", content
            except:
                return "binary", "[Binary content not displayed in chat]"


# Global file handler instance
file_handler = FileHandler()

# Convenience functions for backward compatibility
def save_conversation(conversation_history: List[Dict], filename: str, fmt: str = "markdown") -> str:
    """Save conversation using the global file handler."""
    return file_handler.save_conversation(conversation_history, filename, fmt)

def validate_file_security(file_path: str) -> Tuple[bool, str]:
    """Validate file security using the global file handler."""
    return file_handler.validate_file_security(file_path)

def process_file_upload(file_path: str, conversation_history: List[Dict]) -> Tuple[bool, str]:
    """Process file upload using the global file handler."""
    return file_handler.process_file_upload(file_path, conversation_history)

def handle_attachment(file_path: str, conversation_history: List[Dict]) -> Tuple[bool, str]:
    """Handle file attachment using the global file handler."""
    return file_handler.handle_attachment(file_path, conversation_history)
