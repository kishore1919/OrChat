import json
import subprocess
import sys
import urllib.request
import webbrowser
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from packaging import version

from constants import APP_VERSION, REPO_URL, API_URL

console = Console()

def show_about():
    """Display information about OrChat"""
    console.print(Panel.fit(
        f"[bold blue]Or[/bold blue][bold green]Chat[/bold green] [dim]v{APP_VERSION}[/dim]\n\n"
        "A powerful CLI for chatting with AI models through OpenRouter.\n\n"
        f"[link={REPO_URL}]{REPO_URL}[/link]\n\n"
        "Created by OOP7\n"
        "Licensed under MIT License",
        title="ℹ️ About OrChat",
        border_style="blue"
    ))

def check_for_updates(silent=False):
    """Check GitHub for newer versions of OrChat"""
    if not silent:
        console.print("[bold cyan]Checking for updates...[/bold cyan]")
    try:
        with urllib.request.urlopen(API_URL) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get('tag_name', 'v0.0.0').lstrip('v')

                if version.parse(latest_version) > version.parse(APP_VERSION):
                    console.print(Panel.fit(
                        f"[yellow]A new version of OrChat is available![/yellow]\n"
                        f"Current version: [cyan]{APP_VERSION}[/cyan]\n"
                        f"Latest version: [green]{latest_version}[/green]\n\n"
                        f"Update at: {REPO_URL}/releases",
                        title="📢 Update Available",
                        border_style="yellow"
                    ))

                    if silent:
                        update_choice = Prompt.ask("Would you like to update now?", choices=["y", "n"], default="n")
                        if update_choice.lower() == "y":
                            try:
                                console.print("[cyan]Attempting to update via pip...[/cyan]")
                                result = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "orchat"], 
                                                      capture_output=True, text=True)
                                if result.returncode == 0:
                                    console.print("[green]Update successful! Please restart OrChat.[/green]")
                                    sys.exit(0)
                                else:
                                    console.print(f"[yellow]Update failed: {result.stderr}[/yellow]")
                                    open_browser = Prompt.ask("Open release page for manual update?", choices=["y", "n"], default="y")
                                    if open_browser.lower() == "y":
                                        webbrowser.open(f"{REPO_URL}/releases")
                            except Exception as e:
                                console.print(f"[yellow]Auto-update failed: {str(e)}[/yellow]")
                                open_browser = Prompt.ask("Open release page for manual update?", choices=["y", "n"], default="y")
                                if open_browser.lower() == "y":
                                    webbrowser.open(f"{REPO_URL}/releases")
                    else:
                        open_browser = Prompt.ask("Open release page in browser?", choices=["y", "n"], default="n")
                        if open_browser.lower() == "y":
                            webbrowser.open(f"{REPO_URL}/releases")
                    return True  # Update available
                else:
                    if not silent:
                        console.print("[green]You are using the latest version of OrChat![/green]")
                    return False  # No update available
            else:
                if not silent:
                    console.print(f"[yellow]Could not check for updates. Server returned status "
                                f"code {response.getcode()}[/yellow]")
                return False
    except Exception as e:
        if not silent:
            console.print(f"[yellow]Could not check for updates: {str(e)}[/yellow]")
        return False

def create_chat_ui():
    """Creates a modern, attractive CLI interface using rich components"""
    console.print(Panel.fit(
        f"[bold blue]Or[/bold blue][bold green]Chat[/bold green] [dim]v{APP_VERSION}[/dim]\n"
        "[dim]A powerful CLI for AI models via OpenRouter[/dim]",
        title="🚀 Welcome",
        border_style="green",
        padding=(1, 2)
    ))

    # Display a starting tip
    console.print(Panel(
        "Type [bold green]/help[/bold green] for commands\n"
        "[bold cyan]/model[/bold cyan] to change AI models\n"
        "[bold yellow]/theme[/bold yellow] to customize appearance",
        title="Quick Tips",
        border_style="blue",
        width=40
    ))

def show_help():
    """Display the help message"""
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
    console.print(Panel.fit(help_text, title="Available Commands"))
    try:
        from completion import HAS_PROMPT_TOOLKIT
        if HAS_PROMPT_TOOLKIT:
            console.print(Panel.fit(
                ("[dim]💡 Interactive Features:[/dim]\n"
                 "[dim]• Command auto-completion: Type '/' and all commands appear instantly[/dim]\n"
                 "[dim]• File picker: Type '#' anywhere to browse and select files[/dim]\n"
                 "[dim]• Continue typing to filter commands/files (e.g., '/c' or '#main'[/dim]\n"
                 "[dim]• Press ↑/↓ arrow keys to navigate through previous prompts[/dim]\n"
                 "[dim]• Press Ctrl+R to search through prompt history[/dim]\n"
                 "[dim]• Press Esc+Enter to toggle multi-line input mode[/dim]\n"
                 "[dim]• Auto-suggestions: Previous prompts appear as grey text while typing[/dim]"),
                title="Interactive Features"
            ))
    except ImportError:
        pass
