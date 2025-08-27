"""
User interface components and utilities for OrChat.

This module handles:
- Application information display
- Update checking and management
- Help system and command documentation
- User interaction and feedback
"""

import json
import subprocess
import sys
import urllib.request
import webbrowser
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from packaging import version

from ..core.constants import APP_VERSION, REPO_URL, API_URL

console = Console()


class UIManager:
    """
    Manages user interface operations for OrChat.
    
    This class centralizes UI-related functionality including information
    display, update management, and user interaction helpers.
    """
    
    def __init__(self):
        """Initialize the UI manager."""
        self.console = Console()
    
    def show_about(self) -> None:
        """Display information about OrChat application."""
        self.console.print(Panel.fit(
            f"[bold blue]Or[/bold blue][bold green]Chat[/bold green] [dim]v{APP_VERSION}[/dim]\n\n"
            "A powerful CLI for chatting with AI models through OpenRouter.\n\n"
            f"[link={REPO_URL}]{REPO_URL}[/link]\n\n"
            "Created by OOP7\n"
            "Licensed under MIT License",
            title="ℹ️ About OrChat",
            border_style="blue"
        ))

    def check_for_updates(self, silent: bool = False) -> bool:
        """
        Check GitHub for newer versions of OrChat.
        
        Args:
            silent: If True, suppress status messages during check
            
        Returns:
            True if an update is available, False otherwise
        """
        if not silent:
            self.console.print("[bold cyan]Checking for updates...[/bold cyan]")
        
        try:
            with urllib.request.urlopen(API_URL) as response:
                if response.getcode() == 200:
                    return self._process_update_response(response, silent)
                else:
                    if not silent:
                        self.console.print(
                            f"[yellow]Could not check for updates. Server returned status "
                            f"code {response.getcode()}[/yellow]"
                        )
                    return False
        except Exception as e:
            if not silent:
                self.console.print(f"[yellow]Could not check for updates: {str(e)}[/yellow]")
            return False

    def _process_update_response(self, response, silent: bool) -> bool:
        """
        Process the response from the update check API.
        
        Args:
            response: The HTTP response object
            silent: Whether to suppress non-essential messages
            
        Returns:
            True if update is available, False otherwise
        """
        data = json.loads(response.read().decode('utf-8'))
        latest_version = data.get('tag_name', 'v0.0.0').lstrip('v')

        if version.parse(latest_version) > version.parse(APP_VERSION):
            self._show_update_available(latest_version, silent)
            return True
        else:
            if not silent:
                self.console.print("[green]You are using the latest version of OrChat![/green]")
            return False

    def _show_update_available(self, latest_version: str, silent: bool) -> None:
        """
        Display update available message and handle user response.
        
        Args:
            latest_version: The version number of the latest release
            silent: Whether this is a silent check
        """
        self.console.print(Panel.fit(
            f"[yellow]A new version of OrChat is available![/yellow]\n"
            f"Current version: [cyan]{APP_VERSION}[/cyan]\n"
            f"Latest version: [green]{latest_version}[/green]\n\n"
            f"Update at: {REPO_URL}/releases",
            title="📢 Update Available",
            border_style="yellow"
        ))

        if silent:
            self._handle_update_prompt()
        else:
            self._handle_browser_prompt()

    def _handle_update_prompt(self) -> None:
        """Handle the automatic update prompt during silent checks."""
        update_choice = Prompt.ask("Would you like to update now?", choices=["y", "n"], default="n")
        if update_choice.lower() == "y":
            self._attempt_auto_update()
        else:
            self._handle_browser_prompt()

    def _attempt_auto_update(self) -> None:
        """Attempt to automatically update OrChat via pip."""
        try:
            self.console.print("[cyan]Attempting to update via pip...[/cyan]")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "orchat"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                self.console.print("[green]Update successful! Please restart OrChat.[/green]")
                sys.exit(0)
            else:
                self.console.print(f"[yellow]Update failed: {result.stderr}[/yellow]")
                self._handle_browser_prompt()
        except Exception as e:
            self.console.print(f"[yellow]Auto-update failed: {str(e)}[/yellow]")
            self._handle_browser_prompt()

    def _handle_browser_prompt(self) -> None:
        """Prompt user to open release page in browser."""
        open_browser = Prompt.ask("Open release page in browser?", choices=["y", "n"], default="n")
        if open_browser.lower() == "y":
            webbrowser.open(f"{REPO_URL}/releases")

    def show_help(self) -> None:
        """Display the comprehensive help message with all available commands."""
        help_text = (
            "/exit - Exit the chat\n"
            "/quit - Exit the chat\n"
            "/new - Start a new conversation\n"
            "/clear - Clear conversation history\n"
            "/cls or /clear-screen - Clear terminal screen\n"
            "/save - Save conversation to file\n"
            "/settings - Adjust model settings\n"
            "/tokens - Show token usage statistics\n"
            "/model - Change the AI model\n"
            "/temperature <0.0-2.0> - Adjust temperature\n"
            "/system - View or change system instructions\n"
            "/speed - Show response time statistics\n"
            "/theme <theme> - Change the color theme\n"
            "/about - Show information about OrChat\n"
            "/update - Check for updates\n"
            "/thinking - Show last AI thinking process\n"
            "/thinking-mode - Toggle thinking mode on/off\n"
            "# - Browse and attach files (can be used anywhere in your message)"
        )
        
        self.console.print(Panel.fit(
            help_text, 
            title="Available Commands", 
            border_style="green", 
            padding=(1, 2)
        ))
        
        # Show interactive features if prompt_toolkit is available
        self._show_interactive_features()

    def _show_interactive_features(self) -> None:
        """Display information about interactive features if available."""
        try:
            # Check if completion module is available
            from ...core.completion import HAS_PROMPT_TOOLKIT
            if HAS_PROMPT_TOOLKIT:
                self.console.print(Panel.fit(
                    ("[dim]💡 Interactive Features:[/dim]\n"
                     "[dim]• Command auto-completion: Type '/' and all commands appear instantly[/dim]\n"
                     "[dim]• File picker: Type '#' anywhere to browse and select files[/dim]\n"
                     "[dim]• Continue typing to filter commands/files (e.g., '/c' or '#main'[/dim]\n"
                     "[dim]• Press ↑/↓ arrow keys to navigate through previous prompts[/dim]\n"
                     "[dim]• Press Ctrl+R to search through prompt history[/dim]\n"
                     "[dim]• Press Esc+Enter to toggle multi-line input mode[/dim]\n"
                     "[dim]• Auto-suggestions: Previous prompts appear as grey text while typing[/dim]"),
                    title="Interactive Features",
                    border_style="green",
                    padding=(1, 2)
                ))
        except ImportError:
            # Gracefully handle case where completion module is not available
            pass

    def show_status_message(self, message: str, style: str = "info") -> None:
        """
        Display a styled status message to the user.
        
        Args:
            message: The message to display
            style: The style type ("info", "success", "warning", "error")
        """
        color_map = {
            "info": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red"
        }
        
        color = color_map.get(style, "blue")
        self.console.print(f"[{color}]{message}[/{color}]")

    def confirm_action(self, prompt: str, default: bool = False) -> bool:
        """
        Show a confirmation prompt to the user.
        
        Args:
            prompt: The confirmation message to display
            default: The default choice if user just presses Enter
            
        Returns:
            True if user confirmed, False otherwise
        """
        default_choice = "y" if default else "n"
        choice = Prompt.ask(f"{prompt} (y/n)", choices=["y", "n"], default=default_choice)
        return choice.lower() == "y"

    def show_error_panel(self, title: str, message: str, suggestions: Optional[str] = None) -> None:
        """
        Display an error message in a styled panel.
        
        Args:
            title: The error title
            message: The main error message
            suggestions: Optional suggestions for fixing the error
        """
        content = f"[red]{message}[/red]"
        if suggestions:
            content += f"\n\n[dim]{suggestions}[/dim]"
        
        self.console.print(Panel.fit(
            content,
            title=f"❌ {title}",
            border_style="red",
            padding=(1, 2)
        ))

    def show_success_panel(self, title: str, message: str) -> None:
        """
        Display a success message in a styled panel.
        
        Args:
            title: The success title
            message: The success message
        """
        self.console.print(Panel.fit(
            f"[green]{message}[/green]",
            title=f"✅ {title}",
            border_style="green",
            padding=(1, 2)
        ))


# Global UI manager instance
ui_manager = UIManager()

# Convenience functions for backward compatibility
def show_about() -> None:
    """Show about information using the global UI manager."""
    ui_manager.show_about()

def check_for_updates(silent: bool = False) -> bool:
    """Check for updates using the global UI manager."""
    return ui_manager.check_for_updates(silent)

def show_help() -> None:
    """Show help using the global UI manager."""
    ui_manager.show_help()
