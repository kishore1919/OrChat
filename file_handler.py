import base64
import datetime
import json
import os
import re

from rich.console import Console

from constants import MAX_FILE_SIZE, ALLOWED_FILE_EXTENSIONS
from utils import format_file_size

console = Console()

def save_conversation(conversation_history, filename, fmt="markdown"):
    """Save conversation to file in various formats"""
    if fmt == "markdown":
        with open(filename, 'w', encoding="utf-8") as f:
            f.write("# OrChat Conversation\n\n")
            f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for msg in conversation_history:
                if msg['role'] == 'system':
                    f.write(f"## System Instructions\n\n{msg['content']}\n\n")
                else:
                    f.write(f"## {msg['role'].capitalize()}\n\n{msg['content']}\n\n")
    elif fmt == "json":
        with open(filename, 'w', encoding="utf-8") as f:
            json.dump(conversation_history, f, indent=2)
    elif fmt == "html":
        with open(filename, 'w', encoding="utf-8") as f:
            f.write("<!DOCTYPE html>\n<html>\n<head>\n")
            f.write("<title>OrChat Conversation</title>\n")
            f.write("<style>\n")
            f.write("body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }\n")
            f.write(".system { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }\n")
            f.write(".user { background-color: #e1f5fe; padding: 10px; border-radius: 5px; margin: 10px 0; }\n")
            f.write(".assistant { background-color: #f1f8e9; padding: 10px; border-radius: 5px; margin: 10px 0; }\n")
            f.write("</style>\n</head>\n<body>\n")
            f.write("<h1>OrChat Conversation</h1>\n")
            f.write(f"<p>Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")

            for msg in conversation_history:
                f.write(f"<div class='{msg['role']}'>\n")
                f.write(f"<h2>{msg['role'].capitalize()}</h2>\n")
                content_html = msg['content'].replace('\n', '<br>')
                f.write(f"<p>{content_html}</p>\n")
                f.write("</div>\n")

            f.write("</body>\n</html>")

    return filename

def validate_file_security(file_path):
    """Validate file for security concerns before processing"""
    try:
        # Check if file exists and is readable
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        if not os.path.isfile(file_path):
            return False, "Path is not a file"
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large ({format_file_size(file_size)}). Maximum allowed: {format_file_size(MAX_FILE_SIZE)}"
        
        # Check file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in ALLOWED_FILE_EXTENSIONS:
            return False, f"File type '{file_ext}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}"
        
        # Basic path traversal prevention
        normalized_path = os.path.normpath(file_path)
        if '..' in normalized_path:
            return False, "Invalid file path detected"
        
        # Check for executable files (additional security)
        dangerous_extensions = {'.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.jar', '.sh'}
        if file_ext in dangerous_extensions:
            return False, f"Executable file type '{file_ext}' not allowed for security reasons"
        
        return True, "File validation passed"
    
    except Exception as e:
        return False, f"File validation error: {str(e)}"

def process_file_upload(file_path, conversation_history):
    """Process a file upload and add its contents to the conversation"""
    try:
        # Validate file security first
        is_valid, validation_message = validate_file_security(file_path)
        if not is_valid:
            return False, f"Security validation failed: {validation_message}"

        # Read file with proper encoding handling
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding for non-UTF8 files
            with open(file_path, 'r', encoding="latin-1") as f:
                content = f.read()
        
        # Limit content size for processing
        max_content_length = 50000  # 50KB of text content
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[Content truncated due to size limit]"

        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)

        # Sanitize file name to prevent issues
        safe_file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)

        # Determine file type and create appropriate message
        if file_ext in ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.ts', '.swift']:
            file_type = "code"
            message = f"I'm uploading a code file named '{safe_file_name}'. Please analyze it:\n\n```{file_ext[1:]}\n{content}\n```"
        elif file_ext in ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.css']:
            file_type = "text"
            message = f"I'm uploading a text file named '{safe_file_name}'. Here are its contents:\n\n{content}"
        else:
            file_type = "unknown"
            message = f"I'm uploading a file named '{safe_file_name}'. Here are its contents:\n\n{content}"

        # Add to conversation history
        conversation_history.append({"role": "user", "content": message})
        return True, f"File '{safe_file_name}' uploaded successfully as {file_type}."
    except Exception as e:
        console.print(f"[red]File processing error: {str(e)}[/red]")
        return False, f"Error processing file: {str(e)}"

def handle_attachment(file_path, conversation_history):
    """Enhanced file attachment handling with preview and metadata"""
    try:
        # Validate file security first
        is_valid, validation_message = validate_file_security(file_path)
        if not is_valid:
            return False, f"Security validation failed: {validation_message}"

        # Get file information
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        file_size = os.path.getsize(file_path)
        file_size_formatted = format_file_size(file_size)

        # Sanitize file name
        safe_file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)

        # Determine file type and create appropriate message
        file_type, content = extract_file_content(file_path, file_ext)

        # Create a message that includes metadata about the attachment
        message = f"I'm sharing a file: **{safe_file_name}** ({file_type}, {file_size_formatted})\n\n"

        if file_type == "image":
            # For images, validate and process safely
            if file_size > 5 * 1024 * 1024:  # 5MB limit for images
                return False, "Image file too large (max 5MB)"
            
            try:
                with open(file_path, 'rb') as img_file:
                    image_data = img_file.read()
                    # Basic image validation (check for image headers)
                    if not (image_data.startswith(b'\xff\xd8') or  # JPEG
                           image_data.startswith(b'\x89PNG') or  # PNG
                           image_data.startswith(b'GIF8') or     # GIF
                           image_data.startswith(b'RIFF')):
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
        else:
            # For other file types, add content to the message
            message += content
            conversation_history.append({"role": "user", "content": message})
            return True, f"File '{safe_file_name}' attached successfully as {file_type}."

    except Exception as e:
        console.print(f"[red]Attachment processing error: {str(e)}[/red]")
        return False, f"Error processing attachment: {str(e)}"

def extract_file_content(file_path, file_ext):
    """Extract and format content from different file types"""
    # Determine file type based on extension
    if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
        return "image", ""

    elif file_ext in ['.pdf']:
        # Basic PDF handling - just mention it's a PDF
        return "PDF document", "[PDF content not displayed in chat, but AI can analyze the document]"

    elif file_ext in ['.py', '.js', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.php', '.ts', '.swift']:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return "code", f"```{file_ext[1:]}\n{content}\n```"

    elif file_ext in ['.txt', '.md', '.csv']:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return "text", content

    elif file_ext in ['.json', '.xml']:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return "data", f"```{file_ext[1:]}\n{content}\n```"

    elif file_ext in ['.html', '.css']:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return "web", f"```{file_ext[1:]}\n{content}\n```"

    elif file_ext in ['.zip', '.tar', '.gz', '.rar']:
        return "archive", "[Archive content not displayed in chat]"

    else:
        # Try to read as text, but handle binary files
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return "unknown", content
        except:
            return "binary", "[Binary content not displayed in chat]"
