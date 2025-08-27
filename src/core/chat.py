"""
Chat interface module for OrChat.

This module handles:
- Real-time streaming responses from AI models
- Conversation management and history
- Command processing and special actions
- Token counting and session statistics
- File attachments and multimodal interactions
"""

import datetime
import json
import os
import re
import time
import requests
from typing import Dict, List, Optional, Any, Tuple
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from ..core.config import save_config, load_config
from ..core.constants import APP_VERSION, CHAT_ENDPOINT, SESSION_DIRECTORY
from ..core.model_selection import select_model, get_model_pricing_info, calculate_session_cost
from ..ui.interface import show_about, show_help, check_for_updates
from ..utils.text_utils import count_tokens, format_time_delta, format_file_size, clear_terminal
from ..utils.file_handler import save_conversation, handle_attachment

# Try to import completion module for enhanced input
try:
    from ..core.completion import get_user_input_with_completion, HAS_PROMPT_TOOLKIT
except ImportError:
    HAS_PROMPT_TOOLKIT = False
    def get_user_input_with_completion(prompt_text: str, **kwargs) -> str:
        return input(prompt_text)

console = Console()
last_thinking_content = ""


class ChatInterface:
    """
    Main chat interface for interacting with AI models.
    
    This class manages the conversation flow, handles user commands,
    and provides a rich interactive experience for chatting with AI models.
    """
    
    def __init__(self):
        """Initialize the chat interface."""
        self.console = Console()
        self.conversation_history = []
        self.session_stats = {
            'messages_sent': 0,
            'total_tokens': 0,
            'session_start': time.time()
        }
        
    def chat_with_model(self, config: Dict, initial_history: Optional[List[Dict]] = None) -> None:
        """
        Start the main chat interface.
        
        Args:
            config: Configuration dictionary containing model settings
            initial_history: Optional initial conversation history
        """
        # Initialize conversation history
        if initial_history:
            self.conversation_history = initial_history.copy()
        else:
            self.conversation_history = [
                {"role": "system", "content": config['system_instructions']}
            ]
        
        # Display welcome message
        self._show_welcome_message(config)
        
        # Main chat loop
        while True:
            try:
                # Get user input
                user_input = self._get_user_input()
                
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    command_result = self._handle_command(user_input, config)
                    if command_result == "exit":
                        break
                    elif command_result == "continue":
                        continue
                
                # Process regular message
                self._process_user_message(user_input, config)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Chat interrupted. Use /exit to quit.[/yellow]")
                continue
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
                continue

    def _show_welcome_message(self, config: Dict) -> None:
        """Display welcome message with current settings."""
        model_name = config.get('model', 'Unknown')
        temperature = config.get('temperature', 0.7)
        thinking_mode = config.get('thinking_mode', False)
        
        welcome_text = (
            f"[bold green]Chat started with {model_name}[/bold green]\n"
            f"Temperature: {temperature}\n"
            f"Thinking mode: {'Enabled' if thinking_mode else 'Disabled'}\n\n"
            f"Type your message or use /help for commands."
        )
        
        self.console.print(Panel.fit(
            welcome_text,
            title="💬 OrChat",
            border_style="green",
            padding=(1, 2)
        ))

    def _get_user_input(self) -> str:
        """Get user input with enhanced completion if available."""
        try:
            if HAS_PROMPT_TOOLKIT:
                return get_user_input_with_completion("[bold blue]You[/bold blue]: ")
            else:
                self.console.print("[bold blue]You[/bold blue]: ", end="")
                return input()
        except (EOFError, KeyboardInterrupt):
            return "/exit"

    def _handle_command(self, command: str, config: Dict) -> str:
        """
        Handle special commands.
        
        Args:
            command: The command string
            config: Configuration dictionary
            
        Returns:
            Command result ("exit", "continue", or "processed")
        """
        cmd = command.lower().strip()
        
        # Exit commands
        if cmd in ['/exit', '/quit']:
            self._show_session_stats()
            self.console.print("[yellow]Goodbye![/yellow]")
            return "exit"
        
        # Help command
        elif cmd == '/help':
            show_help()
            return "continue"
        
        # About command
        elif cmd == '/about':
            show_about()
            return "continue"
        
        # Update command
        elif cmd == '/update':
            check_for_updates()
            return "continue"
        
        # Clear conversation
        elif cmd in ['/clear', '/new']:
            self.conversation_history = [
                {"role": "system", "content": config['system_instructions']}
            ]
            self.console.print("[green]Conversation history cleared.[/green]")
            return "continue"
        
        # Clear screen
        elif cmd in ['/cls', '/clear-screen']:
            clear_terminal()
            return "continue"
        
        # Save conversation
        elif cmd == '/save':
            self._save_current_conversation()
            return "continue"
        
        # Show statistics
        elif cmd == '/stats':
            self._show_session_stats()
            return "continue"
        
        # Change model
        elif cmd == '/model':
            new_model = select_model(config)
            if new_model:
                config['model'] = new_model
                save_config(config)
                self.console.print(f"[green]Model changed to: {new_model}[/green]")
            return "continue"
        
        # Change temperature
        elif cmd.startswith('/temperature'):
            self._handle_temperature_change(cmd, config)
            return "continue"
        
        # Toggle thinking mode
        elif cmd == '/thinking-mode':
            self._toggle_thinking_mode(config)
            return "continue"
        
        # Show system instructions
        elif cmd == '/system':
            self._show_system_instructions(config)
            return "continue"
        
        # Unknown command
        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
            self.console.print("Type /help for available commands.")
            return "continue"

    def _process_user_message(self, user_input: str, config: Dict) -> None:
        """
        Process a regular user message and get AI response.
        
        Args:
            user_input: The user's message
            config: Configuration dictionary
        """
        # Handle file attachments (# symbol)
        if '#' in user_input:
            # This is a simplified version - the full implementation would handle file selection
            self.console.print("[yellow]File attachment feature will be implemented in a future update.[/yellow]")
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Get AI response
        try:
            response_content = self._get_ai_response(config)
            if response_content:
                self.conversation_history.append({"role": "assistant", "content": response_content})
                self.session_stats['messages_sent'] += 1
        except Exception as e:
            self.console.print(f"[red]Error getting AI response: {str(e)}[/red]")

    def _get_ai_response(self, config: Dict) -> Optional[str]:
        """
        Get response from the AI model.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            AI response content or None if failed
        """
        try:
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/oop7/OrChat",
                "X-Title": f"OrChat v{APP_VERSION}"
            }
            
            payload = {
                "model": config['model'],
                "messages": self.conversation_history,
                "temperature": config['temperature'],
                "stream": config.get('streaming', True)
            }
            
            # Add max_tokens if specified
            if config.get('max_tokens', 0) > 0:
                payload['max_tokens'] = config['max_tokens']
            
            start_time = time.time()
            
            with self.console.status("[bold green]Thinking..."):
                response = requests.post(
                    CHAT_ENDPOINT,
                    headers=headers,
                    json=payload,
                    stream=payload['stream'],
                    timeout=60
                )
            
            if response.status_code != 200:
                error_msg = f"API Error {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f": {error_data.get('error', {}).get('message', 'Unknown error')}"
                except:
                    pass
                self.console.print(f"[red]{error_msg}[/red]")
                return None
            
            if payload['stream']:
                return self._stream_response(response, start_time, config.get('thinking_mode', False))
            else:
                response_data = response.json()
                content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                self._display_response(content, time.time() - start_time)
                return content
                
        except requests.exceptions.RequestException as e:
            self.console.print(f"[red]Network error: {str(e)}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]Unexpected error: {str(e)}[/red]")
            return None

    def _stream_response(self, response, start_time: float, thinking_mode: bool = False) -> str:
        """
        Stream the response from the API with proper formatting.
        
        Args:
            response: The streaming response object
            start_time: When the request started
            thinking_mode: Whether thinking mode is enabled
            
        Returns:
            Complete response content
        """
        self.console.print("[bold green]Assistant[/bold green]")
        
        full_content = ""
        thinking_content = ""
        in_thinking = False
        
        try:
            for chunk in response.iter_lines():
                if not chunk:
                    continue
                
                chunk_text = chunk.decode('utf-8', errors='replace')
                
                if "OPENROUTER PROCESSING" in chunk_text:
                    continue
                
                if chunk_text.startswith('data: '):
                    chunk_text = chunk_text[6:]
                
                if chunk_text.strip() == '[DONE]':
                    break
                
                try:
                    chunk_data = json.loads(chunk_text)
                    delta = chunk_data.get('choices', [{}])[0].get('delta', {})
                    content = delta.get('content', '')
                    
                    if content:
                        full_content += content
                        
                        # Handle thinking mode
                        if thinking_mode:
                            content = self._process_thinking_content(content, thinking_content, in_thinking)
                        
                        # Display content
                        if content:
                            print(content, end='', flush=True)
                            
                except json.JSONDecodeError:
                    continue
            
            # Add newline after response
            print()
            
            # Calculate and show response time
            response_time = time.time() - start_time
            self.console.print(f"[dim]Response time: {format_time_delta(response_time)}[/dim]")
            
            return full_content
            
        except Exception as e:
            self.console.print(f"\n[red]Error streaming response: {str(e)}[/red]")
            return full_content

    def _process_thinking_content(self, content: str, thinking_content: str, in_thinking: bool) -> str:
        """Process content for thinking mode display."""
        # This is a simplified version - the full implementation would handle thinking tags
        return content

    def _display_response(self, content: str, response_time: float) -> None:
        """Display a non-streaming response."""
        self.console.print("[bold green]Assistant[/bold green]")
        
        # Try to render as markdown if possible
        try:
            md = Markdown(content)
            self.console.print(md)
        except:
            self.console.print(content)
        
        self.console.print(f"[dim]Response time: {format_time_delta(response_time)}[/dim]")

    def _save_current_conversation(self) -> None:
        """Save the current conversation to a file."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(SESSION_DIRECTORY, exist_ok=True)
            
            filename = f"{SESSION_DIRECTORY}/conversation_{timestamp}.md"
            save_conversation(self.conversation_history, filename, "markdown")
            
            self.console.print(f"[green]Conversation saved to: {filename}[/green]")
        except Exception as e:
            self.console.print(f"[red]Error saving conversation: {str(e)}[/red]")

    def _show_session_stats(self) -> None:
        """Display session statistics."""
        session_duration = time.time() - self.session_stats['session_start']
        
        stats_text = (
            f"Messages sent: {self.session_stats['messages_sent']}\n"
            f"Session duration: {format_time_delta(session_duration)}\n"
            f"Total messages in history: {len(self.conversation_history)}"
        )
        
        self.console.print(Panel.fit(
            stats_text,
            title="📊 Session Statistics",
            border_style="blue",
            padding=(1, 2)
        ))

    def _handle_temperature_change(self, cmd: str, config: Dict) -> None:
        """Handle temperature change command."""
        try:
            # Extract temperature value from command
            parts = cmd.split()
            if len(parts) > 1:
                new_temp = float(parts[1])
                if 0.0 <= new_temp <= 2.0:
                    config['temperature'] = new_temp
                    save_config(config)
                    self.console.print(f"[green]Temperature set to: {new_temp}[/green]")
                else:
                    self.console.print("[red]Temperature must be between 0.0 and 2.0[/red]")
            else:
                current_temp = config.get('temperature', 0.7)
                self.console.print(f"Current temperature: {current_temp}")
                new_temp = float(Prompt.ask("Enter new temperature (0.0-2.0)", default=str(current_temp)))
                if 0.0 <= new_temp <= 2.0:
                    config['temperature'] = new_temp
                    save_config(config)
                    self.console.print(f"[green]Temperature set to: {new_temp}[/green]")
                else:
                    self.console.print("[red]Temperature must be between 0.0 and 2.0[/red]")
        except ValueError:
            self.console.print("[red]Invalid temperature value. Please enter a number between 0.0 and 2.0[/red]")

    def _toggle_thinking_mode(self, config: Dict) -> None:
        """Toggle thinking mode on/off."""
        current_mode = config.get('thinking_mode', False)
        config['thinking_mode'] = not current_mode
        save_config(config)
        
        status = "enabled" if config['thinking_mode'] else "disabled"
        self.console.print(f"[green]Thinking mode {status}[/green]")

    def _show_system_instructions(self, config: Dict) -> None:
        """Show current system instructions."""
        instructions = config.get('system_instructions', 'None set')
        
        self.console.print(Panel.fit(
            instructions,
            title="🔧 System Instructions",
            border_style="blue",
            padding=(1, 2)
        ))
        
        if Prompt.ask("Would you like to change the system instructions? (y/n)", default="n").lower() == 'y':
            new_instructions = Prompt.ask("Enter new system instructions")
            if new_instructions.strip():
                config['system_instructions'] = new_instructions
                save_config(config)
                # Update conversation history
                if self.conversation_history and self.conversation_history[0]['role'] == 'system':
                    self.conversation_history[0]['content'] = new_instructions
                self.console.print("[green]System instructions updated[/green]")


# Global chat interface instance
chat_interface = ChatInterface()

# Convenience function for backward compatibility
def chat_with_model(config: Dict, initial_history: Optional[List[Dict]] = None) -> None:
    """Start chat using the global chat interface."""
    chat_interface.chat_with_model(config, initial_history)
