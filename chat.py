import datetime
import json
import os
import re
import time
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from completion import get_user_input_with_completion, HAS_PROMPT_TOOLKIT
from config import save_config
from file_handler import save_conversation, handle_attachment
from model_selection import select_model, get_model_pricing_info, calculate_session_cost
from utils import count_tokens, format_time_delta, format_file_size, clear_terminal
from ui import show_about, show_help, check_for_updates
from api_client import get_model_info
from constants import APP_VERSION

console = Console()
last_thinking_content = ""

def stream_response(response, start_time, thinking_mode=False):
    """Stream the response from the API with proper text formatting"""
    console.print("[bold green]Assistant[/bold green]")

    # Full content accumulates everything
    full_content = ""
    # For thinking detection
    thinking_content = ""
    in_thinking = False
    # For capturing usage information
    usage_info = None

    # Create a temporary file to collect all content
    # This avoids terminal display issues
    collected_content = []

    # For debugging purposes
    global last_thinking_content

    try:
        for chunk in response.iter_lines():
            if not chunk:
                continue

            chunk_text = chunk.decode('utf-8', errors='replace')

            if "OPENROUTER PROCESSING" in chunk_text:
                continue

            if chunk_text.startswith('data:'):
                chunk_text = chunk_text[5:].strip()

            if chunk_text == "[DONE]":
                continue

            try:
                chunk_data = json.loads(chunk_text)
                
                # Capture usage information if present
                if 'usage' in chunk_data:
                    usage_info = chunk_data['usage']
                
                if 'choices' in chunk_data and chunk_data['choices']:
                    delta = chunk_data['choices'][0].get('delta', {}) 
                    content = delta.get('content', delta.get('text', ''))

                    if content:
                        # Add to full content
                        full_content += content

                        # Only process thinking tags if thinking mode is enabled
                        if thinking_mode:
                            # Check for thinking tags
                            if "<thinking>" in content:
                                in_thinking = True
                                # Extract content after the tag
                                thinking_part = content.split("<thinking>", 1)[1]
                                thinking_content += thinking_part
                                # Skip this chunk - don't display the <thinking> tag
                                continue

                            if "</thinking>" in content:
                                in_thinking = False
                                # Extract content before the tag
                                thinking_part = content.split("</thinking>", 1)[0]
                                thinking_content += thinking_part
                                # Skip this chunk - don't display the </thinking> tag
                                continue

                            if in_thinking:
                                thinking_content += content
                                continue

                        # Not in thinking mode or model doesn't support thinking, collect for display
                        collected_content.append(content)
            except json.JSONDecodeError:
                # For non-JSON chunks, quietly ignore
                pass
    except Exception as e:
        console.print(f"\n[red]Error during streaming: {str(e)}[/red]")

    # More robust thinking extraction - uses regex pattern to look for any thinking tags in the full content
    thinking_section = ""
    thinking_pattern = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)
    thinking_matches = thinking_pattern.findall(full_content)

    if thinking_mode and thinking_matches:
        thinking_section = "\n".join(thinking_matches)
        # Update the global thinking content variable
        last_thinking_content = thinking_section

        # Display thinking content immediately if found
        console.print(Markdown(last_thinking_content))
    else:
        # Also check if thinking_content has any content from our incremental collection
        if thinking_content.strip():
            last_thinking_content = thinking_content

            # Display thinking content immediately if found
            console.print(Markdown(last_thinking_content))

    # Clean the full content - only if model supports thinking
    cleaned_content = full_content
    if thinking_mode and "<thinking>" in full_content:
        # Remove the thinking sections with a more robust pattern
        try:
            # Use a non-greedy match to handle multiple thinking sections
            cleaned_content = re.sub(r'<thinking>.*?</thinking>', '', full_content, flags=re.DOTALL)
            cleaned_content = cleaned_content.strip()
        except:
            # Fallback to simpler method
            parts = full_content.split("</thinking>")
            if len(parts) > 1:
                cleaned_content = parts[-1].strip()

    # If after cleaning we have nothing, use a default response
    if not cleaned_content.strip():
        cleaned_content = "Hello! I'm here to help you."

    if cleaned_content:
        console.print(Markdown(cleaned_content))
    else:
        console.print("Hello! I'm here to help you.")

    response_time = time.time() - start_time
    return cleaned_content, response_time, usage_info

def manage_context_window(conversation_history, max_tokens=8000, model_name="cl100k_base"):
    """Manage the context window to prevent exceeding token limits"""
    # Always keep the system message
    system_message = conversation_history[0]

    # Count total tokens in the conversation
    total_tokens = sum(count_tokens(msg["content"], model_name) for msg in conversation_history)

    # If we're under the limit, no need to trim
    if total_tokens <= max_tokens:
        return conversation_history, 0

    # We need to trim the conversation
    # Start with just the system message
    trimmed_history = [system_message]
    current_tokens = count_tokens(system_message["content"], model_name)

    # Add messages from the end (most recent) until we approach the limit
    # Leave room for the next user message
    messages_to_consider = conversation_history[1:]
    trimmed_count = 0

    for msg in reversed(messages_to_consider):
        msg_tokens = count_tokens(msg["content"], model_name)
        if current_tokens + msg_tokens < max_tokens - 1000:  # Leave 1000 tokens buffer
            trimmed_history.insert(1, msg)  # Insert after system message
            current_tokens += msg_tokens
        else:
            trimmed_count += 1

    # Add a note about trimmed messages if any were removed
    if trimmed_count > 0:
        note = {"role": "system", "content": f"Note: {trimmed_count} earlier messages have been removed to stay within the context window."}
        trimmed_history.insert(1, note)

    return trimmed_history, trimmed_count

def create_chat_ui():
    """Creates a modern, attractive CLI interface using rich components"""
    # Removed panel printing to eliminate it from the response
    console.print("1. [cyan]/help[/cyan] - View all available commands")
    console.print("2. [cyan]/model[/cyan] - Change AI models")
    console.print("3. [cyan]/theme[/cyan] - Customize appearance")


def chat_with_model(config, conversation_history=None):
    """ Main chat loop with model interaction """
    if conversation_history is None:
        # Use user's thinking mode preference instead of model detection
        if config['thinking_mode']:
            # Make the thinking instruction more explicit and mandatory
            thinking_instruction = (
                f"{config['system_instructions']}\n\n"
                "CRITICAL INSTRUCTION: For EVERY response without exception, you MUST first explain your "
                "thinking process between <thinking> and </thinking> tags, even for simple greetings or short "
                "responses. This thinking section should explain your reasoning and approach. "
                "After the thinking section, provide your final response. Example format:\n"
                "<thinking>Here I analyze what to say, considering context and appropriate responses...</thinking>\n"
                "This is my actual response to the user."
            )
        else:
            # Use standard instructions without thinking tags
            thinking_instruction = config['system_instructions']

        conversation_history = [
            {"role": "system", "content": thinking_instruction}
        ]

    # Initialize command history for session
    if HAS_PROMPT_TOOLKIT:
        from prompt_toolkit.history import InMemoryHistory
        session_history = InMemoryHistory()
    else:
        session_history = None

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    # Check if temperature is too high and warn the user
    if config['temperature'] > 1.0:
        console.print(Panel.fit(
            f"[yellow]Warning: High temperature setting ({config['temperature']}) may cause erratic responses.[/yellow]\n"
            f"Consider using a value between 0.0 and 1.0 for more coherent outputs.",
            title="⚠️ High Temperature Warning",
            border_style="yellow",
            padding=(1, 2)
        ))

    # Get pricing information for the model
    pricing_info = get_model_pricing_info(config['model'])
    pricing_display = f"[cyan]Pricing:[/cyan] {pricing_info['display']}"
    if pricing_info['is_free']:
        pricing_display += f" [green]({pricing_info['provider']})[/green]"
    else:
        pricing_display += f" [dim]({pricing_info['provider']})[/dim]"

    # Move session panel to first position and integrate status
    console.print(Panel.fit(
        f"[bold green]Or[/bold green][bold cyan]Chat[/bold cyan] [dim]v{APP_VERSION}[/dim]\n"
        f"[dim]Model:[/dim] {config['model']}\n"
        f"[dim]Temperature:[/dim] {config['temperature']}\n"
        f"[dim]Thinking mode:[/dim] {'[green]✓ Enabled[/green]' if config['thinking_mode'] else '[yellow]✗ Disabled[/yellow]'}\n"
        f"{pricing_display}\n"
        f"[dim]Status: Connected[/dim]\n"
        f"[dim]Mode: Interactive[/dim]\n"
        f"[dim]Session started:[/dim] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"[dim]Type your message or use commands: /help for available commands[/dim]",
        title="🤖 Neural Link Active",
        border_style="green",
        padding=(1, 2)
    ))

    # Show welcome UI after session panel
    create_chat_ui()


    # Add session tracking
    session_start_time = time.time()
    total_tokens_used = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    response_times = []
    message_count = 0
    max_tokens = config.get('max_tokens')
    
    if not max_tokens or max_tokens == 0:
        model_info = get_model_info(config['model'])
        if model_info and 'context_length' in model_info and model_info['context_length']:
            max_tokens = model_info['context_length']
            console.print(f"[dim]Using model\'s context length: {max_tokens:,} tokens[/dim]")
        else:
            max_tokens = 8192
            console.print(f"[yellow]Could not determine model\'s context length. Using default: {max_tokens:,} tokens[/yellow]")
    else:
        console.print(f"[dim]Using user-defined max tokens: {max_tokens:,}[/dim]")

    # Create a session directory for saving files
    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Auto-save conversation periodically
    last_autosave = time.time()
    autosave_interval = config['autosave_interval']

    # Check if we need to trim the conversation history
    conversation_history, trimmed_count = manage_context_window(conversation_history, max_tokens=max_tokens, model_name=config['model'])
    if trimmed_count > 0:
        console.print(Panel.fit(
            f"[yellow]Note: Removed {trimmed_count} earlier messages to stay within the context window.[/yellow]",
            border_style="green",
            padding=(0, 1)
        ))

    while True:
        try:
            # Display user input panel similar to assistant style
            console.print("\n")
            # console.print(Panel.fit(
            #     "Enter your message",
            #     title="👤 Human Input",
            #     border_style="green",
            #     padding=(0, 2)
            # ))
            
            # Use auto-completion if available, otherwise fallback to regular input
            if HAS_PROMPT_TOOLKIT:
                user_input = get_user_input_with_completion(session_history)
            else:
                console.print("[bold green]👤 >[/bold green] ", end="")
                user_input = input()

            # Ignore empty or whitespace-only input
            if not user_input.strip():
                continue

            # Handle special commands and file picker
            # Check if input starts with a command OR contains file picker
            if user_input.startswith('/'):
                # Handle regular commands starting with /
                command = user_input.lower()
            elif user_input.startswith('#'):
                # Handle file picker with #
                file_path = user_input[1:].strip()
                
                if not file_path:
                    console.print(Panel.fit(
                        "[yellow]Please select a file using the file picker.[/yellow]",
                        border_style="yellow",
                        padding=(0, 1)
                    ))
                    console.print(Panel.fit(
                        "[dim]Type # to browse files in the current directory[/dim]",
                        border_style="blue",
                        padding=(0, 1)
                    ))
                    continue
                
                # Handle relative paths - make them absolute
                if not os.path.isabs(file_path):
                    file_path = os.path.abspath(file_path)
                
                # Check if file exists
                if not os.path.exists(file_path):
                    console.print(Panel.fit(
                        f"[red]File not found: {file_path}[/red]",
                        border_style="red",
                        padding=(0, 1)
                    ))
                    console.print(Panel.fit(
                        "[dim]Make sure the file path is correct and the file exists.[/dim]",
                        border_style="blue",
                        padding=(0, 1)
                    ))
                    continue

                # Show attachment preview
                file_name = os.path.basename(file_path)
                file_ext = os.path.splitext(file_path)[1].lower()
                file_size = os.path.getsize(file_path)
                file_size_formatted = format_file_size(file_size)

                console.print(Panel.fit(
                    f"File: [bold]{file_name}[/bold]\n"
                    f"Type: {file_ext[1:].upper() if file_ext else 'Unknown'}\n"
                    f"Size: {file_size_formatted}",
                    title="📎 Attachment Preview",
                    border_style="cyan",
                    padding=(1, 2)
                ))

                # Process the file attachment
                success, message = handle_attachment(file_path, conversation_history)
                if success:
                    console.print(Panel.fit(
                        f"[green]{message}[/green]",
                        border_style="green",
                        padding=(0, 1)
                    ))
                else:
                    console.print(Panel.fit(
                        f"[red]{message}[/red]",
                        border_style="red",
                        padding=(0, 1)
                    ))
                    continue
                
                # Continue to get user's actual message about the file
                console.print(Panel.fit(
                    "\n[dim]The file has been attached. Now enter your message about this file:[/dim]",
                    border_style="blue",
                    padding=(0, 1)
                ))
                
                # Get user input for the message about the file
                if HAS_PROMPT_TOOLKIT:
                    user_message = get_user_input_with_completion(session_history)
                else:
                    print("> ", end="")
                    user_message = input()
                
                if user_message.strip():
                    user_input = user_message  # Use the message as the actual input
                else:
                    continue  # Skip if no message provided
            
            elif '#' in user_input:
                # Handle file picker anywhere in the message
                parts = user_input.split('#', 1)
                if len(parts) == 2:
                    message_part = parts[0].strip()
                    file_and_rest = parts[1].strip()
                    
                    if file_and_rest:
                        # Parse filename and any additional text after it
                        # Split by whitespace to separate filename from additional text
                        file_tokens = file_and_rest.split()
                        file_part = file_tokens[0] if file_tokens else ""
                        additional_text = " ".join(file_tokens[1:]) if len(file_tokens) > 1 else ""
                        
                        if file_part:
                            # Handle relative paths - make them absolute
                            if not os.path.isabs(file_part):
                                file_part = os.path.abspath(file_part)
                            
                            # Check if file exists
                            if not os.path.exists(file_part):
                                console.print(Panel.fit(
                                    f"[red]File not found: {file_part}[/red]",
                                    border_style="red",
                                    padding=(0, 1)
                                ))
                                console.print(Panel.fit(
                                    "[dim]Make sure the file path is correct and the file exists.[/dim]",
                                    border_style="blue",
                                    padding=(0, 1)
                                ))
                                continue

                        # Show attachment preview
                        file_name = os.path.basename(file_part)
                        file_ext = os.path.splitext(file_part)[1].lower()
                        file_size = os.path.getsize(file_part)
                        file_size_formatted = format_file_size(file_size)

                        console.print(Panel.fit(
                            f"File: [bold]{file_name}[/bold]\n"
                            f"Type: {file_ext[1:].upper() if file_ext else 'Unknown'}\n"
                            f"Size: {file_size_formatted}",
                            title="📎 Attachment Preview",
                            border_style="cyan",
                            padding=(1, 2)
                        ))

                        # Process the file attachment
                        success, attachment_message = handle_attachment(file_part, conversation_history)
                        if success:
                            console.print(f"[green]{attachment_message}[/green]")
                            # Combine message part with any additional text after filename
                            combined_message = ""
                            if message_part:
                                combined_message = message_part
                            if additional_text:
                                if combined_message:
                                    combined_message += " " + additional_text
                                else:
                                    combined_message = additional_text
                            
                            if combined_message:
                                user_input = combined_message
                            else:
                                console.print(Panel.fit(
                                    "\n[dim]File attached. Enter your message about this file:[/dim]",
                                    border_style="blue",
                                    padding=(0, 1)
                                ))
                                if HAS_PROMPT_TOOLKIT:
                                    user_input = get_user_input_with_completion(session_history)
                                else:
                                    print("> ", end="")
                                    user_input = input()
                        else:
                            console.print(Panel.fit(
                                f"[red]{attachment_message}[/red]",
                                border_style="red",
                                padding=(0, 1)
                            ))
                            continue
            
            # Process commands if we have one
            if user_input.startswith('/'):
                command = user_input.lower()

                if command == '/exit' or command == '/quit':
                    console.print(
                        "[yellow]Exiting chat...[/yellow]",
                        border_style="yellow",
                        padding=(0, 1)
                    )
                    break

                if command == '/help':
                    show_help()
                    continue

                elif command == '/clear':
                    conversation_history = [{"role": "system", "content": config['system_instructions']}]
                    console.print("[green]Conversation history cleared![/green]")
                    continue

                elif command == '/new':
                    # Check if there's any actual conversation to save
                    if len(conversation_history) > 1:
                        save_prompt = Prompt.ask(
                            "Would you like to save the current conversation before starting a new one?",
                            choices=["y", "n"],
                            default="n"
                        )

                        if save_prompt.lower() == "y":
                            # Auto-generate a filename with timestamp
                            filename = f"conversation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                            filepath = os.path.join(session_dir, filename)
                            save_conversation(conversation_history, filepath, "markdown")
                            console.print(f"[green]Conversation saved to {filepath}[/green]")

                    # Reset conversation
                    conversation_history = [{"role": "system", "content": config['system_instructions']}]

                    # Reset session tracking variables
                    total_tokens_used = 0
                    response_times = []
                    message_count = 0
                    last_autosave = time.time()

                    # Create a new session directory
                    session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions", session_id)
                    os.makedirs(session_dir, exist_ok=True)

                    console.print(Panel.fit(
                        "[green]New conversation started![/green]\n"
                        "Previous conversation history has been cleared.",
                        title="🔄 New Conversation",
                        border_style="green"
                    ))
                    continue

                elif command == '/save':
                    parts = user_input.split(' ', 1)
                    if len(parts) > 1:
                        filename = parts[1]
                    else:
                        filename = Prompt.ask("Enter filename to save conversation",
                                            default=f"conversation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md")

                    format_options = ["markdown", "json", "html"]
                    format_choice = Prompt.ask("Choose format", choices=format_options, default="markdown")

                    if not filename.endswith(f".{format_choice.split('.')[-1]}"):
                        if format_choice == "markdown":
                            filename += ".md"
                        elif format_choice == "json":
                            filename += ".json"
                        elif format_choice == "html":
                            filename += ".html"

                    filepath = os.path.join(session_dir, filename)
                    save_conversation(conversation_history, filepath, format_choice)
                    console.print(f"[green]Conversation saved to {filepath}[/green]")
                    continue

                elif command == '/settings':
                    console.print(Panel.fit(
                        f"Current Settings:\n"
                        f"Model: {config['model']}\n"
                        f"Temperature: {config['temperature']}\n"
                        f"System Instructions: {config['system_instructions'][:50]}...",
                        title="Settings",
                        border_style="blue",
                        padding=(1, 2)
                    ))
                    continue

                elif command == '/tokens':
                    # Calculate session statistics
                    session_duration = time.time() - session_start_time
                    session_cost = calculate_session_cost(total_prompt_tokens, total_completion_tokens, pricing_info)
                    
                    # Create detailed token statistics
                    stats_text = f"[bold cyan]📊 Session Statistics[/bold cyan]\n\n"
                    stats_text += f"[cyan]Model:[/cyan] {config['model']}\n"
                    stats_text += f"[cyan]Session duration:[/cyan] {format_time_delta(session_duration)}\n"
                    stats_text += f"[cyan]Messages exchanged:[/cyan] {message_count}\n\n"
                    
                    stats_text += f"[bold]Token Usage:[/bold]\n"
                    stats_text += f"[cyan]Prompt tokens:[/cyan] {total_prompt_tokens:,}\n"
                    stats_text += f"[cyan]Completion tokens:[/cyan] {total_completion_tokens:,}\n"
                    stats_text += f"[cyan]Total tokens:[/cyan] {total_tokens_used:,}\n"
                    stats_text += f"[dim]Token counts from OpenRouter API (accurate)[/dim]\n\n"
                    
                    if pricing_info['is_free']:
                        stats_text += f"[green]💰 Cost: FREE[/green]\n"
                    else:
                        if session_cost < 0.01:
                            cost_display = f"${session_cost:.6f}"
                        else:
                            cost_display = f"${session_cost:.4f}"
                        stats_text += f"[cyan]💰 Session cost:[/cyan] {cost_display}\n"
                        stats_text += f"[dim]{pricing_info['display']}[/dim]\n"
                    
                    if response_times:
                        avg_time = sum(response_times) / len(response_times)
                        stats_text += f"\n[cyan]⏱️ Avg response time:[/cyan] {format_time_delta(avg_time)}"
                        
                        if total_completion_tokens > 0 and avg_time > 0:
                            tokens_per_second = total_completion_tokens / sum(response_times)
                            stats_text += f"\n[cyan]⚡ Speed:[/cyan] {tokens_per_second:.1f} tokens/second"
                    
                    console.print(Panel.fit(
                        stats_text,
                        title="📈 Token Statistics",
                        border_style="cyan",
                        padding=(1, 2)
                    ))
                    continue

                elif command == '/speed':
                    if not response_times:
                        console.print("[yellow]No response time data available yet.[/yellow]")
                    else:
                        avg_time = sum(response_times) / len(response_times)
                        min_time = min(response_times)
                        max_time = max(response_times)
                        console.print(Panel.fit(
                            f"Response Time Statistics:\n"
                            f"Average: {format_time_delta(avg_time)}\n"
                            f"Fastest: {format_time_delta(min_time)}\n"
                            f"Slowest: {format_time_delta(max_time)}\n"
                            f"Total responses: {len(response_times)}",
                            title="Speed Statistics",
                            border_style="blue",
                            padding=(1, 2)
                        ))
                    continue

                elif command.startswith('/model'):
                    selected_model = select_model(config)
                    if selected_model:
                        config['model'] = selected_model
                        save_config(config)
                        console.print(f"[green]Model changed to {config['model']}[/green]")
                    else:
                        console.print(Panel.fit(
                            "[yellow]Model selection cancelled[/yellow]",
                            border_style="yellow",
                            padding=(0, 1)
                        ))
                    continue

                elif command.startswith('/temperature'):
                    parts = command.split()
                    if len(parts) > 1:
                        try:
                            temp = float(parts[1])
                            if 0 <= temp <= 2:
                                if temp > 1.0:
                                    console.print("[yellow]Warning: High temperature values (>1.0) may cause erratic or nonsensical responses.[/yellow]")
                                    confirm = Prompt.ask("Are you sure you want to use this high temperature? (y/n)", default="n")
                                    if confirm.lower() != 'y':
                                        continue

                                config['temperature'] = temp
                                save_config(config)
                                console.print(f"[green]Temperature set to {temp}[/green]")
                            else:
                                console.print(Panel.fit(
                                    "[red]Temperature must be between 0 and 2[/red]",
                                    border_style="red",
                                    padding=(0, 1)
                                ))
                        except ValueError:
                            console.print(Panel.fit(
                                "[red]Invalid temperature value[/red]",
                                border_style="red",
                                padding=(0, 1)
                            ))
                    else:
                        new_temp = Prompt.ask("Enter new temperature (0.0-2.0)", default=str(config['temperature']))
                        try:
                            temp = float(new_temp)
                            if 0 <= temp <= 2:
                                if temp > 1.0:
                                    console.print("[yellow]Warning: High temperature values (>1.0) may cause erratic or nonsensical responses.[/yellow]")
                                    confirm = Prompt.ask("Are you sure you want to use this high temperature? (y/n)", default="n")
                                    if confirm.lower() != 'y':
                                        continue

                                config['temperature'] = temp
                                save_config(config)
                                console.print(Panel.fit(
                                    f"[green]Temperature set to {temp}[/green]",
                                    border_style="green",
                                    padding=(0, 1)
                                ))
                            else:
                                console.print(Panel.fit(
                                    "[red]Temperature must be between 0 and 2[/red]",
                                    border_style="red",
                                    padding=(0, 1)
                                ))
                        except ValueError:
                            console.print(Panel.fit(
                                "[red]Invalid temperature value[/red]",
                                border_style="red",
                                padding=(0, 1)
                            ))
                    continue

                elif command.startswith('/system'):
                    parts = user_input.split(' ', 1)
                    if len(parts) > 1:
                        config['system_instructions'] = parts[1]
                        conversation_history[0] = {"role": "system", "content": config['system_instructions']}
                        save_config(config)
                        console.print("[green]System instructions updated![/green]")
                    else:
                        console.print(Panel.fit(
                            config['system_instructions'],
                            title="Current System Instructions",
                            border_style="blue",
                            padding=(1, 2)
                        ))
                        change = Prompt.ask("Update system instructions? (y/n)", default="n")
                        if change.lower() == 'y':
                            console.print("[bold]Enter new system instructions (guide the AI's behavior)[/bold]")
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
                            system_instructions = "\n".join(lines)
                            config['system_instructions'] = system_instructions
                            conversation_history[0] = {"role": "system", "content": config['system_instructions']}
                            save_config(config)
                            console.print("[green]System instructions updated![/green]")
                    continue

                elif command.startswith('/theme'):
                    parts = command.split()
                    available_themes = ['default', 'dark', 'light', 'hacker']
                    
                    if len(parts) > 1:
                        theme = parts[1].lower()
                        if theme in available_themes:
                            config['theme'] = theme
                            save_config(config)
                            console.print(f"[green]Theme changed to {theme}[/green]")
                        else:
                            console.print(f"[red]Invalid theme. Available themes: {', '.join(available_themes)}[/red]")
                    else:
                        console.print(Panel.fit(
                            f"[cyan]Current theme:[/cyan] {config['theme']}\n"
                            f"[cyan]Available themes:[/cyan] {', '.join(available_themes)}",
                            border_style="blue",
                            padding=(0, 2)
                        ))
                        new_theme = Prompt.ask("Select theme", choices=available_themes, default=config['theme'])
                        config['theme'] = new_theme
                        save_config(config)
                        console.print(Panel.fit(
                            f"[green]Theme changed to {new_theme}[/green]",
                            border_style="green",
                            padding=(0, 1)
                        ))
                    continue

                elif command == '/about':
                    show_about()
                    continue

                elif command == '/update':
                    check_for_updates(silent=False)
                    continue

                elif command == '/thinking':
                    if last_thinking_content:
                        console.print(Panel.fit(
                            last_thinking_content,
                            title="🧠 Last Thinking Process",
                            border_style="green",
                            padding=(1, 2)
                        ))
                    else:
                        console.print(Panel.fit(
                            "[yellow]No thinking content available from the last response.[/yellow]",
                            border_style="green",
                            padding=(0, 1)
                        ))
                    continue

                elif command == '/thinking-mode':
                    # Toggle thinking mode
                    config['thinking_mode'] = not config['thinking_mode']
                    save_config(config)

                    # Update the system prompt for future messages
                    if len(conversation_history) > 0 and conversation_history[0]['role'] == 'system':
                        original_instructions = config['system_instructions']
                        if config['thinking_mode']:
                            thinking_instruction = (
                                f"{original_instructions}\n\n"
                                "CRITICAL INSTRUCTION: For EVERY response without exception, you MUST first explain your "
                                "thinking process between <thinking> and </thinking> tags, even for simple greetings or short "
                                "responses. This thinking section should explain your reasoning and approach. "
                                "After the thinking section, provide your final response. Example format:\n"
                                "<thinking>Here I analyze what to say, considering context and appropriate responses...</thinking>\n"
                                "This is my actual response to the user."
                            )
                            conversation_history[0]['content'] = thinking_instruction
                        else:
                            # Revert to original instructions without thinking tags
                            conversation_history[0]['content'] = original_instructions

                    console.print(Panel.fit(
                        f"[green]Thinking mode is now {'enabled' if config['thinking_mode'] else 'disabled'}[/green]",
                        border_style="green",
                        padding=(0, 1)
                    ))
                    continue

                elif command in ('/cls', '/clear-screen'):
                    # Clear the terminal
                    clear_terminal()

                    # After clearing, redisplay the session header for context
                    # Re-get pricing info for display
                    current_pricing_info = get_model_pricing_info(config['model'])
                    pricing_display = f"[cyan]Pricing:[/cyan] {current_pricing_info['display']}"
                    if not current_pricing_info['is_free']:
                        pricing_display += f" [dim]({current_pricing_info['provider']})[/dim]"
                    else:
                        pricing_display += f" [green]({current_pricing_info['provider']})[/green]"
                        
                    console.print(Panel.fit(
                        f"[bold green]Or[/bold green][bold cyan]Chat[/bold cyan] [dim]v{APP_VERSION}[/dim]\n"
                        f"[dim]Model:[/dim] {config['model']}\n"
                        f"[dim]Temperature:[/dim] {config['temperature']}\n"
                        f"[dim]Thinking mode:[/dim] {'[green]✓ Enabled[/green]' if config['thinking_mode'] else '[yellow]✗ Disabled[/yellow]'}\n"
                        f"{pricing_display}\n"
                        f"[dim]Status: Connected[/dim]\n"
                        f"[dim]Mode: Interactive[/dim]\n"
                        f"[dim]Session started:[/dim] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"[dim]Type your message or use commands: /help for available commands[/dim]",
                        title="🤖 Neural Link Active",
                        border_style="green",
                        padding=(1, 2)
                    ))
                    console.print(Panel.fit(
                        "[green]Terminal screen cleared. Chat session continues.[/green]",
                        border_style="green",
                        padding=(0, 1)
                    ))
                    continue

                else:
                    console.print(Panel.fit(
                        "[yellow]Unknown command. Type /help for available commands.[/yellow]",
                        border_style="yellow",
                        padding=(0, 1)
                    ))
                    continue

            # Count tokens in user input
            # Estimate input tokens for display purposes (will be replaced by API data if available)
            estimated_input_tokens = count_tokens(user_input)
            input_tokens = estimated_input_tokens
            total_prompt_tokens += input_tokens

            # Add user message to conversation history
            conversation_history.append({"role": "user", "content": user_input})

            # Get model max tokens
            model_info = get_model_info(config['model'])
            if model_info and 'context_length' in model_info:
                # This is just for display, max_tokens for management is set at the start
                display_max_tokens = model_info['context_length']
            else:
                display_max_tokens = max_tokens

            # Check if we need to trim the conversation history
            conversation_history, trimmed_count = manage_context_window(conversation_history, max_tokens=max_tokens, model_name=config['model'])
            if trimmed_count > 0:
                console.print(Panel.fit(
                    f"[yellow]Note: Removed {trimmed_count} earlier messages to stay within the context window.[/yellow]",
                    border_style="green",
                    padding=(0, 1)
                ))

            # Clean conversation history for API - remove any messages with invalid fields
            clean_conversation = []
            for msg in conversation_history:
                clean_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                # Handle models that don't support system messages (like Gemma)
                if clean_msg["role"] == "system":
                    # Check if this is a Gemma model that doesn't support system messages
                    if "gemma" in config['model'].lower():
                        # Convert system message to user message with instructions
                        if clean_msg["content"] and clean_msg["content"].strip():
                            clean_msg["role"] = "user"
                            clean_msg["content"] = f"Please follow these instructions: {clean_msg['content']}"
                        else:
                            # Skip empty system messages
                            continue
                    else:
                        # Keep system message for models that support it
                        pass
                
                # Only include valid roles for OpenRouter API
                if clean_msg['role'] in ["system", "user", "assistant"]:
                    clean_conversation.append(clean_msg)

            # Update the API call to use streaming
            data = {
                "model": config['model'],
                "messages": clean_conversation,
                "temperature": config['temperature'],
                "stream": True,
            }

            # Start timing the response
            start_time = time.time()
            timer_display = console.status("[bold cyan]⏱️ Waiting for response...[/bold cyan]")
            timer_display.start()

            try:
                # Make streaming request
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=60  # Add a timeout
                )

                if response.status_code == 200:
                    # Pass config['thinking_mode'] to stream_response
                    message_content, response_time, usage_info = stream_response(response, start_time, config['thinking_mode'])

                    # Only add to history if we got actual content
                    if message_content:
                        response_times.append(response_time)

                        # Add assistant response to conversation history
                        conversation_history.append({"role": "assistant", "content": message_content})

                        # Use API-provided token counts if available, otherwise fallback to tiktoken
                        if usage_info:
                            actual_prompt_tokens = usage_info.get('prompt_tokens', 0)
                            actual_completion_tokens = usage_info.get('completion_tokens', 0)
                            actual_total_tokens = usage_info.get('total_tokens', actual_prompt_tokens + actual_completion_tokens)
                            
                            total_prompt_tokens += actual_prompt_tokens
                            total_completion_tokens += actual_completion_tokens
                            total_tokens_used += actual_total_tokens
                            
                            input_tokens = actual_prompt_tokens
                            response_tokens = actual_completion_tokens
                        else:
                            # Fallback to tiktoken estimation
                            response_tokens = count_tokens(message_content)
                            total_tokens_used += input_tokens + response_tokens
                            total_completion_tokens += response_tokens

                        # Calculate cost for this exchange
                        exchange_cost = calculate_session_cost(input_tokens, response_tokens, pricing_info)

                        # Display speed and token information
                        formatted_time = format_time_delta(response_time)
                        console.print(f"[dim]⏱️ Response time: {formatted_time}[/dim]")
                        
                        # Enhanced token display with cost and accuracy indicator
                        token_source = "API" if usage_info else "estimated"
                        token_display = f"[dim]Tokens: {input_tokens} (input) + {response_tokens} (response) = {input_tokens + response_tokens} (total) [{token_source}]"
                        if exchange_cost > 0:
                            if exchange_cost < 0.01:
                                token_display += f" | Cost: ${exchange_cost:.6f}"
                            else:
                                token_display += f" | Cost: ${exchange_cost:.4f}"
                        token_display += "[/dim]"
                        console.print(token_display)
                        
                        if max_tokens:
                            console.print(f"[dim]Total Tokens: {total_tokens_used:,} / {display_max_tokens:,}[/dim]")
                        
                        # Increment message count for successful exchanges
                        message_count += 1
                    else:
                        # If we didn't get content but status was 200, something went wrong with streaming
                        console.print(Panel.fit(
                            "[red]Error: Received empty response from API[/red]",
                            border_style="green",
                            padding=(0, 1)
                        ))
                        # Remove the user's last message since we didn't get a response
                        if conversation_history and conversation_history[-1]["role"] == "user":
                            conversation_history.pop()
                else:
                    # Try to get error details from response
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', {}).get('message', str(response.text))
                        
                        # Special handling for insufficient credits error (402)
                        if response.status_code == 402:
                            suggestions_text = (
                                f"[yellow]Solutions:[/yellow]\n"
                                f"• Add credits at: [link=https://openrouter.ai/settings/credits]https://openrouter.ai/settings/credits[/link]\n"
                                f"• Browse free models: [cyan]/model[/cyan] → [cyan]2[/cyan] (Show free models only)\n"
                                f"• Try the free version if available: [cyan]{config['model']}:free[/cyan]\n"
                                f"\n[dim]Original error: {error_message}[/dim]"
                            )
                            
                            console.print(Panel.fit(
                                f"[red]💳 Insufficient Credits[/red]\n\n"
                                f"The model '[cyan]{config['model']}[/cyan]' requires credits to use.\n\n"
                                f"{suggestions_text}",
                                title="⚠️ Payment Required",
                                border_style="green",
                                padding=(1, 2)
                            ))
                        else:
                            console.print(Panel.fit(
                                f"[red]API Error ({response.status_code}): {error_message}[/red]",
                                border_style="green",
                                padding=(0, 1)
                            ))
                    except Exception:
                        console.print(Panel.fit(
                            f"[red]API Error: Status code {response.status_code}[/red]",
                            border_style="green",
                            padding=(0, 1)
                        ))
                        console.print(Panel.fit(
                            f"[red]{response.text}[/red]",
                            border_style="green",
                            padding=(0, 1)
                        ))

                # Remove the user's last message since we didn't get a response
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.pop()
            except requests.exceptions.RequestException as e:
                console.print(Panel.fit(
                    f"[red]Network error: {str(e)}[/red]",
                    border_style="green",
                    padding=(0, 1)
                ))
                # Remove the user's last message since we didn't get a response
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.pop()
            except Exception as e:
                console.print(Panel.fit(
                    f"[red]Error: {str(e)}[/red]",
                    border_style="green",
                    padding=(0, 1)
                ))
                # Remove the user's last message since we didn't get a response
                if conversation_history and conversation_history[-1]["role"] == "user":
                    conversation_history.pop()
            finally:
                timer_display.stop()

        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Keyboard interrupt detected. Type /exit to quit.[/yellow]",
            )
            break
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
