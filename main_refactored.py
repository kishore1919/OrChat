"""
OrChat - AI Chat Application powered by OpenRouter

This is the main entry point for OrChat, a feature-rich AI chat interface
that supports multiple models through OpenRouter. This module serves as
the single source of truth and coordinates all application functionality.

Usage:
    python main.py [options]
    
Options:
    --setup         Run the setup wizard
    --model MODEL   Specify model to use
    --task TASK     Optimize for specific task type (creative, coding, analysis, chat)
    --image PATH    Path to image file to analyze

Author: OrChat Team
License: MIT
"""

import argparse
import os
import sys
import time
from typing import Optional, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Import all core functionality from the organized modules
from src.core.constants import APP_VERSION, SESSION_DIRECTORY
from src.core.config import load_config, save_config, secure_input_api_key
from src.core.api_client import get_available_models, get_dynamic_task_categories
from src.core.model_selection import select_model
from src.core.chat import chat_with_model
from src.ui.interface import show_about, show_help, check_for_updates
from src.utils.text_utils import clear_terminal
from src.utils.file_handler import handle_attachment

console = Console()


class OrChatApplication:
    """
    Main application class for OrChat.
    
    This class serves as the central coordinator for all OrChat functionality,
    managing the application lifecycle, configuration, and user interactions.
    """
    
    def __init__(self):
        """Initialize the OrChat application."""
        self.console = Console()
        self.config: Optional[Dict] = None
        self.conversation_history: Optional[List] = None
        
    def run(self) -> None:
        """
        Main entry point for the OrChat application.
        
        This method handles argument parsing, configuration loading,
        and starts the main application loop.
        """
        try:
            # Parse command line arguments
            args = self._parse_arguments()
            
            # Initialize configuration
            self.config = self._initialize_configuration(args)
            if not self.config:
                sys.exit(1)
            
            # Check for updates on startup
            self._check_for_updates()
            
            # Validate configuration
            if not self._validate_configuration(args):
                sys.exit(1)
            
            # Handle command-line specific operations
            self._handle_command_line_options(args)
            
            # Start the main chat interface
            self._start_chat_interface()
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Exiting application...[/yellow]")
        except Exception as e:
            self.console.print(f"[red]Critical error: {str(e)}[/red]")
            sys.exit(1)

    def _parse_arguments(self) -> argparse.Namespace:
        """
        Parse command line arguments.
        
        Returns:
            Parsed arguments namespace
        """
        parser = argparse.ArgumentParser(
            description="OrChat - AI chat powered by OpenRouter",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=f"""
Examples:
  {sys.argv[0]} --setup              # Run initial setup
  {sys.argv[0]} --model claude-3-opus # Use specific model
  {sys.argv[0]} --task coding        # Optimize for coding tasks
  {sys.argv[0]} --image photo.jpg    # Analyze an image
            """
        )
        
        parser.add_argument(
            "--setup", 
            action="store_true", 
            help="Run the setup wizard"
        )
        parser.add_argument(
            "--model", 
            type=str, 
            help="Specify model to use"
        )
        parser.add_argument(
            "--task", 
            type=str, 
            choices=["creative", "coding", "analysis", "chat"],
            help="Optimize for specific task type"
        )
        parser.add_argument(
            "--image", 
            type=str, 
            help="Path to image file to analyze"
        )
        parser.add_argument(
            "--version", 
            action="version", 
            version=f"OrChat {APP_VERSION}"
        )
        
        return parser.parse_args()

    def _initialize_configuration(self, args: argparse.Namespace) -> Optional[Dict]:
        """
        Initialize application configuration.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Configuration dictionary or None if initialization failed
        """
        # Check if configuration files exist
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

        # Run setup wizard if needed or requested
        if args.setup or (not os.path.exists(config_file) and not os.path.exists(env_file)):
            return self._run_setup_wizard()
        else:
            return load_config()

    def _run_setup_wizard(self) -> Optional[Dict]:
        """
        Run the interactive setup wizard for first-time users.
        
        Returns:
            Configuration dictionary or None if setup was cancelled
        """
        self.console.print(Panel.fit(
            "[bold blue]Welcome to the OrChat Setup Wizard![/bold blue]\n" 
            "Let's configure your chat settings.",
            title="Setup Wizard",
            border_style="blue",
            padding=(1, 2)
        ))

        # Get API key
        api_key = self._setup_api_key()
        if not api_key:
            return None

        # Set up temporary config for model selection
        temp_config = {'api_key': api_key, 'thinking_mode': False}

        # Select AI model
        model, thinking_mode = self._setup_model_selection(temp_config)

        # Get other configuration settings
        temperature = self._setup_temperature()
        system_instructions = self._setup_system_instructions()
        theme_choice = self._setup_theme()

        # Create final configuration
        config_data = {
            'api_key': api_key,
            'model': model,
            'temperature': temperature,
            'system_instructions': system_instructions,
            'theme': theme_choice,
            'max_tokens': 0,
            'autosave_interval': 300,
            'streaming': True,
            'thinking_mode': thinking_mode
        }

        save_config(config_data)
        return config_data

    def _setup_api_key(self) -> Optional[str]:
        """
        Handle API key setup during wizard.
        
        Returns:
            Valid API key or None if setup was cancelled
        """
        if "OPENROUTER_API_KEY" not in os.environ:
            self.console.print(Panel.fit(
                "[bold yellow]🔐 API Key Setup[/bold yellow]\n"
                "[dim]Your API key will be encrypted and stored securely[/dim]",
                border_style="yellow",
                padding=(0, 2)
            ))
            
            # Loop until we get a valid API key or user cancels
            while True:
                api_key = secure_input_api_key()
                if not api_key:
                    self.console.print(Panel.fit(
                        "[red]Invalid API key provided.[/red]",
                        border_style="red",
                        padding=(0, 1)
                    ))
                    retry = Prompt.ask("Would you like to try again? (y/n)", default="y")
                    if retry.lower() != 'y':
                        self.console.print(Panel.fit(
                            "[red]Setup cancelled - no valid API key provided[/red]",
                            border_style="red",
                            padding=(0, 1)
                        ))
                        return None
                    continue
                else:
                    return api_key
        else:
            return os.getenv("OPENROUTER_API_KEY")

    def _setup_model_selection(self, temp_config: Dict) -> tuple:
        """
        Handle model selection during setup.
        
        Args:
            temp_config: Temporary configuration with API key
            
        Returns:
            Tuple of (model_id, thinking_mode)
        """
        self.console.print("[bold]Select an AI model to use:[/bold]")
        model = ""
        thinking_mode = False  # Default value

        try:
            with self.console.status("[bold green]Connecting to OpenRouter...[/bold green]"):
                time.sleep(1)  # Small delay to ensure API key is registered

            # Use the model selection module
            selected_model = select_model(temp_config)
            
            if selected_model:
                model = selected_model
                thinking_mode = temp_config.get('thinking_mode', False)
            else:
                self.console.print(Panel.fit(
                    "[yellow]Model selection cancelled. You can set a model later.[/yellow]",
                    border_style="yellow",
                    padding=(0, 1)
                ))
        except Exception as e:
            self.console.print(Panel.fit(
                f"[yellow]Error during model selection: {str(e)}. You can set a model later.[/yellow]",
                border_style="yellow",
                padding=(0, 1)
            ))

        return model, thinking_mode

    def _setup_temperature(self) -> float:
        """
        Handle temperature setup during wizard.
        
        Returns:
            Temperature value between 0.0 and 2.0
        """
        temperature = float(Prompt.ask("Set temperature (0.0-2.0)", default="0.7"))
        
        if temperature > 1.0:
            self.console.print(Panel.fit(
                "[yellow]Warning: High temperature values (>1.0) may cause erratic or nonsensical responses.[/yellow]",
                border_style="yellow",
                padding=(0, 1)
            ))
            confirm = Prompt.ask("Are you sure you want to use this high temperature? (y/n)", default="n")
            if confirm.lower() != 'y':
                temperature = float(Prompt.ask("Enter a new temperature value (0.0-1.0)", default="0.7"))
        
        return temperature

    def _setup_system_instructions(self) -> str:
        """
        Handle system instructions setup during wizard.
        
        Returns:
            System instructions string
        """
        self.console.print(Panel.fit(
            "[bold]Enter system instructions (guide the AI's behavior)[/bold]\n"
            "[dim]Press Enter twice to finish[/dim]",
            border_style="blue",
            padding=(0, 2)
        ))
        
        lines = []
        empty_line_count = 0
        
        while True:
            line = input()
            if not line:
                empty_line_count += 1
                if empty_line_count >= 2:  # Exit after two consecutive empty lines
                    break
            else:
                empty_line_count = 0  # Reset counter if non-empty line
                lines.append(line)

        # Use default if no instructions provided
        if not lines:
            system_instructions = "You are a helpful AI assistant."
            self.console.print(Panel.fit(
                "[yellow]No system instructions provided. Using default instructions.[/yellow]",
                border_style="yellow",
                padding=(0, 1)
            ))
        else:
            system_instructions = "\n".join(lines)

        return system_instructions

    def _setup_theme(self) -> str:
        """
        Handle theme setup during wizard.
        
        Returns:
            Selected theme name
        """
        available_themes = ['default', 'dark', 'light', 'hacker']
        self.console.print(Panel.fit(
            f"[green]Available themes:[/green] {', '.join(available_themes)}",
            border_style="green",
            padding=(0, 1)
        ))
        return Prompt.ask("Select theme", choices=available_themes, default="default")

    def _check_for_updates(self) -> None:
        """Check for application updates on startup."""
        try:
            check_for_updates(silent=True)
        except Exception:
            # Silently ignore update check failures
            pass

    def _validate_configuration(self, args: argparse.Namespace) -> bool:
        """
        Validate the loaded configuration.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            True if configuration is valid, False otherwise
        """
        # Ensure config is loaded
        if not self.config:
            return False
            
        # Check API key
        if not self._validate_api_key():
            return False
            
        # Check model selection
        if not self._validate_model_selection(args):
            return False
            
        # Set default system instructions if missing
        if not self.config.get('system_instructions'):
            self.config['system_instructions'] = "You are a helpful AI assistant."
            self.console.print(Panel.fit(
                "[yellow]No system instructions set. Using default instructions.[/yellow]",
                border_style="yellow",
                padding=(0, 1)
            ))
            save_config(self.config)

        return True

    def _validate_api_key(self) -> bool:
        """
        Validate the API key configuration.
        
        Returns:
            True if API key is valid, False otherwise
        """
        if not self.config:
            return False
            
        if not self.config['api_key'] or self.config['api_key'] == "<YOUR_OPENROUTER_API_KEY>":
            self.console.print(Panel.fit(
                "[red]API key not found or not set correctly.[/red]",
                border_style="red",
                padding=(0, 1)
            ))
            
            setup_choice = Prompt.ask("Would you like to run the setup wizard? (y/n)", default="y")
            if setup_choice.lower() == 'y':
                self.config = self._run_setup_wizard()
                if self.config is None:
                    self.console.print(Panel.fit(
                        "[red]Setup failed. Cannot continue without a valid API key.[/red]",
                        border_style="red",
                        padding=(0, 1)
                    ))
                    return False
            else:
                self.console.print(Panel.fit(
                    "[red]Cannot continue without a valid API key.[/red]",
                    border_style="red",
                    padding=(0, 1)
                ))
                return False
        
        return True

    def _validate_model_selection(self, args: argparse.Namespace) -> bool:
        """
        Validate and handle model selection.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            True if model is properly configured, False otherwise
        """
        if not self.config:
            return False
            
        # Handle command line model override
        if args.model:
            self.config['model'] = args.model
            save_config(self.config)
        
        # Check if model is set
        elif not self.config['model']:
            self.console.print(Panel.fit(
                "[yellow]No model selected. Please choose a model.[/yellow]",
                border_style="yellow",
                padding=(0, 1)
            ))
            
            # Use the model selection module
            selected_model = select_model(self.config)
            
            if selected_model:
                self.config['model'] = selected_model
                save_config(self.config)
            else:
                self.console.print(Panel.fit(
                    "[red]Cannot continue without a valid model.[/red]",
                    border_style="red",
                    padding=(0, 1)
                ))
                return False

        return True

    def _handle_command_line_options(self, args: argparse.Namespace) -> None:
        """
        Handle special command line options like task optimization and image analysis.
        
        Args:
            args: Parsed command line arguments
        """
        # Handle task-specific model recommendations
        if args.task:
            self._handle_task_optimization(args.task)

        # Handle image analysis
        if args.image:
            self._handle_image_analysis(args.image)

    def _handle_task_optimization(self, task: str) -> None:
        """
        Handle task-specific model recommendations.
        
        Args:
            task: The task type to optimize for
        """
        try:
            recommended_models = self._get_model_recommendations(task)
            if recommended_models:
                self.console.print(Panel.fit(
                    f"[bold green]Recommended models for {task} tasks:[/bold green]\n" +
                    "\n".join([f"- {model['id']}" for model in recommended_models[:5]]),
                    title="🎯 Task Optimization",
                    border_style="green",
                    padding=(1, 2)
                ))

                use_recommended = Prompt.ask(
                    "Would you like to use one of these recommended models?",
                    choices=["y", "n"],
                    default="y"
                )

                if use_recommended.lower() == 'y':
                    self._select_recommended_model(recommended_models[:5])
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not get task recommendations: {str(e)}[/yellow]")

    def _get_model_recommendations(self, task_type: str) -> List[Dict]:
        """
        Get model recommendations based on task type.
        
        Args:
            task_type: The type of task to get recommendations for
            
        Returns:
            List of recommended model dictionaries
        """
        all_models = get_available_models()

        try:
            task_categories = get_dynamic_task_categories()
            self.console.print(f"[dim]Using dynamic categories for task: {task_type}[/dim]")
        except Exception as e:
            self.console.print(f"[yellow]Warning: Failed to get dynamic categories: {str(e)}[/yellow]")
            # Fallback to basic patterns
            task_categories = {
                "creative": ["claude-3", "gpt-4", "llama", "gemini"],
                "coding": ["claude-3-opus", "gpt-4", "deepseek-coder", "qwen-coder", "devstral", "codestral"],
                "analysis": ["claude-3-opus", "gpt-4", "mistral", "qwen"],
                "chat": ["claude-3-haiku", "gpt-3.5", "gemini-pro", "llama"]
            }

        recommended = []
        task_model_patterns = task_categories.get(task_type, [])
        
        for model in all_models:
            model_id = model.get('id', '').lower()
            if any(pattern.lower() in model_id for pattern in task_model_patterns):
                recommended.append(model)

        return recommended or all_models

    def _select_recommended_model(self, recommended_models: List[Dict]) -> None:
        """
        Let user select from recommended models.
        
        Args:
            recommended_models: List of recommended model dictionaries
        """
        if not self.config:
            return
            
        for i, model in enumerate(recommended_models, 1):
            self.console.print(f"[bold]{i}.[/bold] {model['id']}")

        choice = Prompt.ask("Select model number", default="1")
        try:
            index = int(choice) - 1
            if 0 <= index < len(recommended_models):
                self.config['model'] = recommended_models[index]['id']
                save_config(self.config)
        except ValueError:
            pass

    def _handle_image_analysis(self, image_path: str) -> None:
        """
        Handle image analysis setup.
        
        Args:
            image_path: Path to the image file to analyze
        """
        if not self.config:
            return
            
        self.conversation_history = [
            {"role": "system", "content": self.config['system_instructions']}
        ]
        
        # Use the file handler module
        success, message = handle_attachment(image_path, self.conversation_history)
        
        if success:
            self.console.print(Panel.fit(
                f"[green]{message}[/green]",
                border_style="green",
                padding=(0, 1)
            ))
        else:
            self.console.print(Panel.fit(
                f"[red]{message}[/red]",
                border_style="red",
                padding=(0, 1)
            ))

    def _start_chat_interface(self) -> None:
        """Start the main chat interface."""
        if self.config:
            chat_with_model(self.config, self.conversation_history)
        else:
            self.console.print("[red]Cannot start chat without valid configuration.[/red]")


def main():
    """
    Main entry point for the OrChat application.
    
    This function creates and runs the main application instance.
    """
    app = OrChatApplication()
    app.run()


if __name__ == "__main__":
    main()
