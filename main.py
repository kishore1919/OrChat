import argparse
import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from api_client import get_available_models, get_dynamic_task_categories
from chat import chat_with_model
from config import load_config, save_config, secure_input_api_key
from constants import APP_VERSION
from file_handler import handle_attachment
from model_selection import select_model
from ui import create_chat_ui, check_for_updates

console = Console()

def setup_wizard():
    """Interactive setup wizard for first-time users"""
    console.print(Panel.fit(
        "[bold blue]Welcome to the OrChat Setup Wizard![/bold blue]\n" \
        "Let's configure your chat settings.",
        title="Setup Wizard"
    ))

    if "OPENROUTER_API_KEY" not in os.environ:
        console.print("[bold yellow]🔐 API Key Setup[/bold yellow]")
        console.print("[dim]Your API key will be encrypted and stored securely[/dim]")
        
        # Loop until we get a valid API key or user explicitly cancels
        while True:
            api_key = secure_input_api_key()
            if not api_key:
                console.print("[red]Invalid API key provided.[/red]")
                retry = Prompt.ask("Would you like to try again? (y/n)", default="y")
                if retry.lower() != 'y':
                    console.print("[red]Setup cancelled - no valid API key provided[/red]")
                    return None
                continue  # Ask for API key again
            else:
                break  # Valid API key received, exit loop
    else:
        api_key = os.getenv("OPENROUTER_API_KEY")

    # Save API key temporarily to allow model fetching
    temp_config = {'api_key': api_key, 'thinking_mode': False}  # Default to disabled

    # Use the simplified model selection
    console.print("[bold]Select an AI model to use:[/bold]")
    model = ""
    thinking_mode = False  # Default value - disabled
    try:
        with console.status("[bold green]Connecting to OpenRouter...[/bold green]"):
            # Small delay to ensure the API key is registered
            time.sleep(1)

        selected_model = select_model(temp_config)
        if selected_model:
            model = selected_model
            # Use the thinking_mode value that was set during model selection
            thinking_mode = temp_config.get('thinking_mode', False)
        else:
            console.print("[yellow]Model selection cancelled. You can set a model later.[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Error during model selection: {str(e)}. You can set a model later.[/yellow]")

    temperature = float(Prompt.ask("Set temperature (0.0-2.0)", default="0.7"))
    if temperature > 1.0:
        console.print("[yellow]Warning: High temperature values (>1.0) may cause erratic or nonsensical responses.[/yellow]")
        confirm = Prompt.ask("Are you sure you want to use this high temperature? (y/n)", default="n")
        if confirm.lower() != 'y':
            temperature = float(Prompt.ask("Enter a new temperature value (0.0-1.0)", default="0.7"))

    console.print("[bold]Enter system instructions (guide the AI's behavior)[/bold]")
    console.print("[dim]Press Enter twice to finish[/dim]")
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

    # If no instructions provided, use a default value
    if not lines:
        system_instructions = "You are a helpful AI assistant."
        console.print("[yellow]No system instructions provided. Using default instructions.[/yellow]")
    else:
        system_instructions = "\n".join(lines)

    # Add theme selection
    available_themes = ['default', 'dark', 'light', 'hacker']
    console.print("[green]Available themes:[/green]")
    for theme in available_themes:
        console.print(f"- {theme}")
    theme_choice = Prompt.ask("Select theme", choices=available_themes, default="default")

    # We already asked about thinking mode during model selection, so we'll use that value
    # Only ask if model selection failed or was cancelled
    if not model:
        # Enhanced thinking mode explanation
        console.print(Panel.fit(
            "[yellow]Thinking Mode:[/yellow]\n\n"
            "Thinking mode shows the AI's reasoning process between <thinking> and </thinking> tags.\n"
            "This reveals how the AI approaches your questions and can help you understand its thought process.\n\n"
            "[dim]Note: Not all models support this feature. If you notice issues with responses, you can disable it later with /thinking-mode[/dim]",
            title="🧠 AI Reasoning Process",
            border_style="yellow"
        ))

        thinking_mode = Prompt.ask(
            "Enable thinking mode?",
            choices=["y", "n"],
            default="n"
        ).lower() == "y"

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

def get_model_recommendations(task_type=None, budget=None):
    """Recommends models based on task type and budget constraints using dynamic OpenRouter categories"""
    all_models = get_available_models()

    if not task_type:
        return all_models

    # Get dynamic task categories from OpenRouter API instead of hardcoded ones
    try:
        task_categories = get_dynamic_task_categories()
        console.print(f"[dim]Using dynamic categories for task: {task_type}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to get dynamic categories, using fallback patterns: {str(e)}[/yellow]")
        # Fallback to basic patterns if API fails
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
        # Check if model matches any of the task-specific patterns/slugs
        if any(pattern.lower() in model_id for pattern in task_model_patterns):
            # Filter by budget if specified
            if budget == "free" and ":free" in model['id']:
                recommended.append(model)
            elif budget is None or budget != "free":
                recommended.append(model)

    return recommended or all_models

def main():
    parser = argparse.ArgumentParser(description="OrChat - AI chat powered by OpenRouter")
    parser.add_argument("--setup", action="store_true", help="Run the setup wizard")
    parser.add_argument("--model", type=str, help="Specify model to use")
    parser.add_argument("--task", type=str, choices=["creative", "coding", "analysis", "chat"],
                        help="Optimize for specific task type")
    parser.add_argument("--image", type=str, help="Path to image file to analyze")
    args = parser.parse_args()

    # Check if config exists
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    if args.setup or (not os.path.exists(config_file) and not os.path.exists(env_file)):
        config = setup_wizard()
        if config is None:
            console.print("[red]Setup failed. Cannot continue without proper configuration. Exiting.[/red]")
            sys.exit(1)
    else:
        config = load_config()

    # Show welcome UI
    create_chat_ui()

    # Auto-check for updates on startup
    try:
        check_for_updates(silent=True)
    except Exception:
        pass  # Silently ignore update check failures

    # Check if API key is set
    if not config['api_key'] or config['api_key'] == "<YOUR_OPENROUTER_API_KEY>":
        console.print("[red]API key not found or not set correctly.[/red]")
        setup_choice = Prompt.ask("Would you like to run the setup wizard? (y/n)", default="y")
        if setup_choice.lower() == 'y':
            config = setup_wizard()
            if config is None:
                console.print("[red]Setup failed. Cannot continue without a valid API key. Exiting.[/red]")
                sys.exit(1)
        else:
            console.print("[red]Cannot continue without a valid API key. Exiting.[/red]")
            sys.exit(1)

    # Handle task-specific model recommendation
    if args.task:
        recommended_models = get_model_recommendations(args.task)
        if recommended_models:
            console.print(Panel.fit(
                f"[bold green]Recommended models for {args.task} tasks:[/bold green]\n" +
                "\n".join([f"- {model['id']}" for model in recommended_models[:5]]),
                title="🎯 Task Optimization"
            ))

            use_recommended = Prompt.ask(
                "Would you like to use one of these recommended models?",
                choices=["y", "n"],
                default="y"
            )

            if use_recommended.lower() == 'y':
                # Let user select from recommended models
                for i, model in enumerate(recommended_models[:5], 1):
                    console.print(f"[bold]{i}.[/bold] {model['id']}")

                choice = Prompt.ask("Select model number", default="1")
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(recommended_models[:5]):
                        config['model'] = recommended_models[index]['id']
                        save_config(config)
                except ValueError:
                    pass

    # Check if model is set or specified via command line
    if args.model:
        config['model'] = args.model
        save_config(config)
    elif not config['model']:
        console.print("[yellow]No model selected. Please choose a model.[/yellow]")
        selected_model = select_model(config)
        if selected_model:
            config['model'] = selected_model
            save_config(config)
        else:
            console.print("[red]Cannot continue without a valid model. Exiting.[/red]")
            sys.exit(1)

    # Check if system instructions are set - make sure we don't prompt again after setup
    if not config['system_instructions']:
        # Only prompt for system instructions if they weren't already set during setup
        # Set a default value without prompting
        config['system_instructions'] = "You are a helpful AI assistant."
        console.print("[yellow]No system instructions set. Using default instructions.[/yellow]")
        save_config(config)

    # Handle image analysis if provided
    conversation_history = None
    if args.image:
        conversation_history = [
            {"role": "system", "content": config['system_instructions']}
        ]
        success, message = handle_attachment(args.image, conversation_history)
        if success:
            console.print(f"[green]{message}[/green]")
        else:
            console.print(f"[red]{message}[/red]")

    # Start chat
    chat_with_model(config, conversation_history)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application...")
    except Exception as e:
        console.print(f"[red]Critical error: {str(e)}[/red]")
        sys.exit(1)
