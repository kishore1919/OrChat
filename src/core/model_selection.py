"""
Model selection module for OrChat.

This module handles:
- Interactive model selection from available models
- Model filtering by capabilities, groups, and categories
- Automatic thinking mode detection based on model capabilities
- Integration with fuzzy finder for enhanced selection experience
"""

from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.prompt import Prompt

from ..core.api_client import (
    get_available_models, get_enhanced_models, get_models_by_capability,
    get_models_by_group, get_dynamic_task_categories
)
from ..core.config import save_config

console = Console()

# Try to import fuzzy finder for enhanced model selection
try:
    from pyfzf.pyfzf import FzfPrompt
    HAS_FZF = True
except ImportError:
    HAS_FZF = False


class ModelSelector:
    """
    Handles model selection and configuration for OrChat.
    
    This class provides various methods for selecting AI models,
    including browsing by capabilities, categories, and interactive selection.
    """
    
    def __init__(self):
        """Initialize the model selector."""
        self.console = Console()
    
    def select_model(self, config: Dict) -> Optional[str]:
        """
        Main model selection interface with multiple options.
        
        Args:
            config: Configuration dictionary to update with selected model
            
        Returns:
            Selected model ID or None if cancelled
        """
        all_models = get_available_models()

        if not all_models:
            self.console.print("[red]No models available. Please check your API key and internet connection.[/red]")
            return None

        # Display selection options
        self.console.print("[bold green]Model Selection[/bold green]")
        self.console.print("\n[bold magenta]Options:[/bold magenta]")
        self.console.print("[bold]1[/bold] - View all available models")
        self.console.print("[bold]2[/bold] - Show free models only")
        self.console.print("[bold]3[/bold] - Enter model name directly")
        self.console.print("[bold]4[/bold] - Browse models by task category")
        self.console.print("[bold]5[/bold] - Browse by capabilities (enhanced)")
        self.console.print("[bold]6[/bold] - Browse by model groups")
        self.console.print("[bold]q[/bold] - Cancel selection")

        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "q"], default="1")

        if choice == "q":
            return None
        elif choice == "1":
            return self._select_from_all_models(config, all_models)
        elif choice == "2":
            return self._select_free_models(config, all_models)
        elif choice == "3":
            return self._direct_model_entry(config, all_models)
        elif choice == "4":
            return self._select_by_task_category(config)
        elif choice == "5":
            return self._select_by_capabilities(config)
        elif choice == "6":
            return self._select_by_groups(config)

    def _direct_model_entry(self, config: Dict, all_models: List[Dict]) -> Optional[str]:
        """
        Allow direct model name entry.
        
        Args:
            config: Configuration dictionary
            all_models: List of available models
            
        Returns:
            Selected model ID or None
        """
        self.console.print("[yellow]Enter the exact model name (e.g., 'anthropic/claude-3-opus')[/yellow]")
        model_name = Prompt.ask("Model name")

        # Validate the model name
        model_exists = any(model["id"] == model_name for model in all_models)
        if model_exists:
            self._auto_detect_thinking_mode(config, model_name)
            return model_name

        self.console.print("[yellow]Warning: Model not found in available models. Using anyway.[/yellow]")
        confirm = Prompt.ask("Continue with this model name? (y/n)", default="y")
        if confirm.lower() == "y":
            self._auto_detect_thinking_mode(config, model_name)
            return model_name
        
        return self.select_model(config)  # Start over

    def _select_from_all_models(self, config: Dict, all_models: List[Dict]) -> Optional[str]:
        """
        Select from all available models.
        
        Args:
            config: Configuration dictionary
            all_models: List of all available models
            
        Returns:
            Selected model ID or None
        """
        self.console.print("[bold green]All Available Models:[/bold green]")

        # Try fuzzy finder first if available
        if HAS_FZF:
            try:
                fzf = FzfPrompt()
                model_choice = fzf.prompt([model['id'] for model in all_models])
                if not model_choice:
                    self.console.print("[red]No model selected.[/red]")
                    return self.select_model(config)
                else:
                    self._auto_detect_thinking_mode(config, model_choice[0])
                    return model_choice[0]
            except Exception as e:
                self.console.print(f"[yellow]FZF not available: {str(e)}. Using numbered list.[/yellow]")

        # Fall back to numbered list
        return self._numbered_model_selection(config, all_models, "all models")

    def _select_free_models(self, config: Dict, all_models: List[Dict]) -> Optional[str]:
        """
        Select from free models only.
        
        Args:
            config: Configuration dictionary
            all_models: List of all available models
            
        Returns:
            Selected model ID or None
        """
        free_models = [model for model in all_models if model['id'].endswith(":free")]

        if not free_models:
            self.console.print("[yellow]No free models found.[/yellow]")
            Prompt.ask("Press Enter to continue")
            return self.select_model(config)

        self.console.print("[bold green]Free Models:[/bold green]")
        return self._numbered_model_selection(config, free_models, "free models", highlight_free=True)

    def _select_by_task_category(self, config: Dict) -> Optional[str]:
        """
        Select models by task category.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Selected model ID or None
        """
        try:
            task_categories = get_dynamic_task_categories()
            
            self.console.print("[bold green]Task Categories:[/bold green]")
            categories = list(task_categories.keys())
            
            for i, category in enumerate(categories, 1):
                self.console.print(f"[bold]{i}.[/bold] {category.title()}")
            self.console.print("[bold]b.[/bold] Back to main menu")

            choice = Prompt.ask("Select category", default="1")
            
            if choice.lower() == 'b':
                return self.select_model(config)

            try:
                index = int(choice) - 1
                if 0 <= index < len(categories):
                    selected_category = categories[index]
                    return self._show_category_models(config, selected_category, task_categories)
                else:
                    self.console.print("[red]Invalid selection[/red]")
                    return self._select_by_task_category(config)
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")
                return self._select_by_task_category(config)
                
        except Exception as e:
            self.console.print(f"[red]Error loading task categories: {str(e)}[/red]")
            return self.select_model(config)

    def _select_by_capabilities(self, config: Dict) -> Optional[str]:
        """
        Select models by capabilities.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Selected model ID or None
        """
        capabilities = ["reasoning", "multipart", "tools", "free"]
        
        self.console.print("[bold green]Model Capabilities:[/bold green]")
        for i, capability in enumerate(capabilities, 1):
            description = self._get_capability_description(capability)
            self.console.print(f"[bold]{i}.[/bold] {capability.title()} - {description}")
        self.console.print("[bold]b.[/bold] Back to main menu")

        choice = Prompt.ask("Select capability", default="1")
        
        if choice.lower() == 'b':
            return self.select_model(config)

        try:
            index = int(choice) - 1
            if 0 <= index < len(capabilities):
                selected_capability = capabilities[index]
                capable_models = get_models_by_capability(selected_capability)
                
                if not capable_models:
                    self.console.print(f"[yellow]No models found with {selected_capability} capability.[/yellow]")
                    Prompt.ask("Press Enter to continue")
                    return self._select_by_capabilities(config)
                
                return self._numbered_model_selection(config, capable_models, f"{selected_capability} models")
            else:
                self.console.print("[red]Invalid selection[/red]")
                return self._select_by_capabilities(config)
        except ValueError:
            self.console.print("[red]Please enter a valid number[/red]")
            return self._select_by_capabilities(config)

    def _select_by_groups(self, config: Dict) -> Optional[str]:
        """
        Select models by groups.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Selected model ID or None
        """
        try:
            groups = get_models_by_group()
            
            if not groups:
                self.console.print("[yellow]No model groups found.[/yellow]")
                Prompt.ask("Press Enter to continue")
                return self.select_model(config)
            
            self.console.print("[bold green]Model Groups:[/bold green]")
            group_names = list(groups.keys())
            
            for i, group_name in enumerate(group_names, 1):
                model_count = len(groups[group_name])
                self.console.print(f"[bold]{i}.[/bold] {group_name} ({model_count} models)")
            self.console.print("[bold]b.[/bold] Back to main menu")

            choice = Prompt.ask("Select group", default="1")
            
            if choice.lower() == 'b':
                return self.select_model(config)

            try:
                index = int(choice) - 1
                if 0 <= index < len(group_names):
                    selected_group = group_names[index]
                    group_models = groups[selected_group]
                    return self._numbered_model_selection(config, group_models, f"{selected_group} models")
                else:
                    self.console.print("[red]Invalid selection[/red]")
                    return self._select_by_groups(config)
            except ValueError:
                self.console.print("[red]Please enter a valid number[/red]")
                return self._select_by_groups(config)
                
        except Exception as e:
            self.console.print(f"[red]Error loading model groups: {str(e)}[/red]")
            return self.select_model(config)

    def _numbered_model_selection(self, config: Dict, models: List[Dict], 
                                 title: str, highlight_free: bool = False) -> Optional[str]:
        """
        Display numbered list of models for selection.
        
        Args:
            config: Configuration dictionary
            models: List of models to display
            title: Title for the selection
            highlight_free: Whether to highlight free models
            
        Returns:
            Selected model ID or None
        """
        with self.console.pager(styles=True):
            for i, model in enumerate(models, 1):
                model_id = model.get('id', 'Unknown')
                if highlight_free and model_id.endswith(":free"):
                    self.console.print(f"[bold]{i}.[/bold] {model_id} [green](FREE)[/green]")
                else:
                    self.console.print(f"[bold]{i}.[/bold] {model_id}")

        model_choice = Prompt.ask("Enter model number or 'b' to go back", default="1")

        if model_choice.lower() == 'b':
            return self.select_model(config)

        try:
            index = int(model_choice) - 1
            if 0 <= index < len(models):
                selected_model = models[index].get('id')
                if selected_model:
                    self._auto_detect_thinking_mode(config, selected_model)
                    return selected_model
            
            self.console.print("[red]Invalid selection[/red]")
            Prompt.ask("Press Enter to continue")
            return self._numbered_model_selection(config, models, title, highlight_free)
        except ValueError:
            self.console.print("[red]Please enter a valid number[/red]")
            Prompt.ask("Press Enter to continue")
            return self._numbered_model_selection(config, models, title, highlight_free)

    def _show_category_models(self, config: Dict, category: str, 
                            task_categories: Dict) -> Optional[str]:
        """
        Show models for a specific category.
        
        Args:
            config: Configuration dictionary
            category: Selected category name
            task_categories: Dictionary of task categories
            
        Returns:
            Selected model ID or None
        """
        model_patterns = task_categories.get(category, [])
        all_models = get_available_models()
        
        # Filter models based on category patterns
        category_models = []
        for model in all_models:
            model_id = model.get('id', '').lower()
            if any(pattern.lower() in model_id for pattern in model_patterns):
                category_models.append(model)
        
        if not category_models:
            self.console.print(f"[yellow]No models found for {category} category.[/yellow]")
            Prompt.ask("Press Enter to continue")
            return self._select_by_task_category(config)
        
        self.console.print(f"[bold green]{category.title()} Models:[/bold green]")
        return self._numbered_model_selection(config, category_models, f"{category} models")

    def _get_capability_description(self, capability: str) -> str:
        """Get human-readable description for a capability."""
        descriptions = {
            "reasoning": "Models that show their thinking process",
            "multipart": "Models that can process images and files",
            "tools": "Models that support function calling",
            "free": "Free models with no cost"
        }
        return descriptions.get(capability, "Unknown capability")

    def _auto_detect_thinking_mode(self, config: Dict, selected_model: str) -> None:
        """
        Automatically detect if the selected model supports thinking mode.
        
        Args:
            config: Configuration dictionary to update
            selected_model: ID of the selected model
        """
        # Ensure thinking_mode key exists in config
        if 'thinking_mode' not in config:
            config['thinking_mode'] = False  # Default to disabled

        try:
            # Get enhanced models to check if this model supports reasoning
            enhanced_models = get_enhanced_models()
            
            for model in enhanced_models:
                if model is None:
                    continue
                    
                # Check if this is the selected model
                model_slug = model.get('slug') or model.get('name') or model.get('short_name', '')
                if model_slug == selected_model:
                    # Check if model supports reasoning/thinking
                    endpoint = model.get('endpoint', {})
                    supports_reasoning = endpoint.get('supports_reasoning', False) if endpoint else False
                    reasoning_config = model.get('reasoning_config') or (endpoint.get('reasoning_config') if endpoint else None)
                    
                    if supports_reasoning or reasoning_config:
                        config['thinking_mode'] = True
                        self.console.print("[green]🧠 Thinking mode automatically enabled for this reasoning model.[/green]")
                        if reasoning_config:
                            start_token = reasoning_config.get('start_token', '<thinking>')
                            end_token = reasoning_config.get('end_token', '</thinking>')
                            self.console.print(f"[dim]Uses reasoning tags: {start_token}...{end_token}[/dim]")
                    else:
                        config['thinking_mode'] = False
                        self.console.print("[dim]Thinking mode disabled - this model doesn't support reasoning.[/dim]")
                    return
            
            # If model not found in enhanced models, disable thinking mode
            config['thinking_mode'] = False
            self.console.print("[dim]Thinking mode disabled - unable to verify reasoning support.[/dim]")
            
        except Exception as e:
            # If there's an error, keep current setting or default to disabled
            config['thinking_mode'] = config.get('thinking_mode', False)
            self.console.print(f"[yellow]Error detecting thinking mode: {str(e)}[/yellow]")

    def get_model_pricing_info(self, model_id: str) -> Optional[Dict]:
        """
        Get pricing information for a specific model.
        
        Args:
            model_id: ID of the model to get pricing for
            
        Returns:
            Pricing information dictionary or None
        """
        try:
            enhanced_models = get_enhanced_models()
            
            for model in enhanced_models:
                if model and model.get('id') == model_id:
                    endpoint = model.get('endpoint', {})
                    pricing = endpoint.get('pricing', {}) if endpoint else {}
                    return pricing
            
            return None
        except Exception as e:
            self.console.print(f"[yellow]Error getting pricing info: {str(e)}[/yellow]")
            return None

    def calculate_session_cost(self, conversation_history: List[Dict], 
                             model_id: str) -> Optional[float]:
        """
        Calculate estimated cost for the current session.
        
        Args:
            conversation_history: List of conversation messages
            model_id: ID of the model being used
            
        Returns:
            Estimated cost or None if calculation fails
        """
        try:
            pricing = self.get_model_pricing_info(model_id)
            if not pricing:
                return None
            
            # This is a simplified calculation - would need actual token counting
            total_chars = sum(len(str(msg.get('content', ''))) for msg in conversation_history)
            estimated_tokens = total_chars // 4  # Rough approximation
            
            prompt_price = float(pricing.get('prompt', 0))
            completion_price = float(pricing.get('completion', 0))
            
            # Estimate 70% prompt, 30% completion
            prompt_tokens = int(estimated_tokens * 0.7)
            completion_tokens = int(estimated_tokens * 0.3)
            
            cost = ((prompt_tokens * prompt_price) + (completion_tokens * completion_price)) / 1_000_000
            return cost
            
        except Exception as e:
            self.console.print(f"[yellow]Error calculating cost: {str(e)}[/yellow]")
            return None


# Global model selector instance
model_selector = ModelSelector()

# Convenience functions for backward compatibility
def select_model(config: Dict) -> Optional[str]:
    """Select model using the global model selector."""
    return model_selector.select_model(config)

def auto_detect_thinking_mode(config: Dict, selected_model: str) -> None:
    """Auto-detect thinking mode using the global model selector."""
    model_selector._auto_detect_thinking_mode(config, selected_model)

def get_model_pricing_info(model_id: str) -> Optional[Dict]:
    """Get model pricing info using the global model selector."""
    return model_selector.get_model_pricing_info(model_id)

def calculate_session_cost(conversation_history: List[Dict], model_id: str) -> Optional[float]:
    """Calculate session cost using the global model selector."""
    return model_selector.calculate_session_cost(conversation_history, model_id)
