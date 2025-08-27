"""
API client module for OpenRouter integration.

This module handles all communication with the OpenRouter API, including:
- Fetching available models and their capabilities
- Organizing models by provider, group, and category
- Dynamic task-based model recommendations
- Enhanced model data retrieval
"""

import requests
from typing import Dict, List, Optional, Any
from rich.console import Console

from .config import load_config
from .constants import MODELS_ENDPOINT

console = Console()


class OpenRouterClient:
    """
    Client for interacting with the OpenRouter API.
    
    This class provides a structured way to interact with OpenRouter's various
    endpoints and handle model data efficiently.
    """
    
    def __init__(self):
        """Initialize the OpenRouter client."""
        self.base_url = "https://openrouter.ai/api/v1"
        self.frontend_url = "https://openrouter.ai/api/frontend"
        
    def _get_headers(self) -> Dict[str, str]:
        """
        Get standard headers for API requests.
        
        Returns:
            Dictionary containing authorization and content-type headers
        """
        config = load_config()
        return {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
    
    def _make_request(self, url: str, error_message: str) -> Optional[Dict]:
        """
        Make a GET request to the specified URL with error handling.
        
        Args:
            url: The URL to make the request to
            error_message: Custom error message for failures
            
        Returns:
            Response JSON data or None if request failed
        """
        try:
            headers = self._get_headers()
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                console.print(f"[red]{error_message}: {response.status_code}[/red]")
                return None
        except Exception as e:
            console.print(f"[red]{error_message}: {str(e)}[/red]")
            return None

    def get_available_models(self) -> List[Dict]:
        """
        Fetch all available models from OpenRouter API.
        
        Returns:
            List of model dictionaries containing model information
        """
        with console.status("[bold green]Fetching available models..."):
            response_data = self._make_request(
                f"{self.base_url}/models",
                "Error fetching models"
            )
            
        if response_data:
            return response_data.get("data", [])
        return []

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """
        Get detailed information for a specific model.
        
        Args:
            model_id: The ID of the model to get information for
            
        Returns:
            Model information dictionary or None if not found
        """
        models = self.get_available_models()
        
        try:
            for model in models:
                if model.get("id") == model_id:
                    return model
            
            console.print(f"[yellow]Warning: Could not find info for model '{model_id}'.[/yellow]")
            return None
        except Exception as e:
            console.print(f"[red]Failed to fetch model info: {str(e)}[/red]")
            return None

    def get_enhanced_models(self) -> List[Dict]:
        """
        Fetch enhanced model data from OpenRouter frontend API.
        
        This endpoint provides additional model capabilities and metadata
        not available in the standard models API.
        
        Returns:
            List of enhanced model dictionaries
        """
        with console.status("[bold green]Fetching enhanced model data..."):
            response_data = self._make_request(
                f"{self.frontend_url}/models",
                "Error fetching enhanced models"
            )
            
        if response_data:
            return response_data.get("data", [])
        else:
            # Fallback to standard models API
            console.print("[yellow]Falling back to standard models API[/yellow]")
            return self.get_available_models()

    def get_models_by_capability(self, capability_filter: str = "all") -> List[Dict]:
        """
        Get models filtered by specific capabilities.
        
        Args:
            capability_filter: The capability to filter by 
                             ("all", "reasoning", "multipart", "tools", "free")
            
        Returns:
            List of models matching the capability filter
        """
        try:
            enhanced_models = self.get_enhanced_models()
            
            if capability_filter == "all":
                return enhanced_models
            
            filtered_models = []
            
            for model in enhanced_models:
                if not model:  # Skip None models
                    continue
                    
                endpoint = model.get('endpoint', {})
                if not endpoint:
                    continue
                
                if self._model_matches_capability(model, endpoint, capability_filter):
                    filtered_models.append(model)
                    
            return filtered_models
            
        except Exception as e:
            console.print(f"[red]Error filtering models by capability: {str(e)}[/red]")
            return self.get_available_models()  # Fallback

    def _model_matches_capability(self, model: Dict, endpoint: Dict, capability: str) -> bool:
        """
        Check if a model matches the specified capability.
        
        Args:
            model: The model dictionary
            endpoint: The endpoint information for the model
            capability: The capability to check for
            
        Returns:
            True if the model supports the capability, False otherwise
        """
        if capability == "reasoning":
            # Check if model supports reasoning/thinking
            supports_reasoning = endpoint.get('supports_reasoning', False)
            reasoning_config = model.get('reasoning_config') or endpoint.get('reasoning_config')
            return supports_reasoning or bool(reasoning_config)
            
        elif capability == "multipart":
            # Check if model supports multipart (images/files)
            supports_multipart = endpoint.get('supports_multipart', False)
            input_modalities = model.get('input_modalities', [])
            return supports_multipart or ('image' in input_modalities)
            
        elif capability == "tools":
            # Check if model supports tool parameters
            supports_tools = endpoint.get('supports_tool_parameters', False)
            supported_params = endpoint.get('supported_parameters', []) or []
            return supports_tools or 'tools' in supported_params
            
        elif capability == "free":
            # Check if model is free
            is_free = endpoint.get('is_free', False)
            pricing = endpoint.get('pricing', {}) or {}
            prompt_price = float(pricing.get('prompt', '0'))
            return is_free or prompt_price == 0
            
        return False

    def get_models_by_group(self) -> Dict[str, List[Dict]]:
        """
        Get models organized by their groups.
        
        Returns:
            Dictionary mapping group names to lists of models
        """
        try:
            enhanced_models = self.get_enhanced_models()
            groups = {}
            
            for model in enhanced_models:
                if not model:  # Skip None models
                    continue
                    
                group = model.get('group', 'Other')
                if group not in groups:
                    groups[group] = []
                groups[group].append(model)
            
            return groups
            
        except Exception as e:
            console.print(f"[red]Error grouping models: {str(e)}[/red]")
            return {}

    def get_models_by_provider(self) -> Dict[str, List[Dict]]:
        """
        Get models organized by their providers.
        
        Returns:
            Dictionary mapping provider names to lists of models
        """
        try:
            enhanced_models = self.get_enhanced_models()
            providers = {}
            
            for model in enhanced_models:
                if not model:  # Skip None models
                    continue
                    
                endpoint = model.get('endpoint', {})
                if not endpoint:
                    continue
                    
                provider = endpoint.get('provider_name', 'Unknown')
                if provider not in providers:
                    providers[provider] = []
                providers[provider].append(model)
            
            return providers
            
        except Exception as e:
            console.print(f"[red]Error organizing models by provider: {str(e)}[/red]")
            return {}

    def get_models_by_categories(self, categories: List[str]) -> List[str]:
        """
        Fetch models by categories from OpenRouter API.
        
        Args:
            categories: List of category names to search for
            
        Returns:
            List of model slugs matching the categories
        """
        try:
            # Convert categories list to comma-separated string
            categories_param = ",".join(categories) if isinstance(categories, list) else categories
            
            with console.status(f"[bold green]Fetching models for categories: {categories_param}..."):
                response_data = self._make_request(
                    f"{self.frontend_url}/models/find?categories={categories_param}",
                    "Error fetching models by categories"
                )

            if response_data and "data" in response_data and "models" in response_data["data"]:
                return [model["slug"] for model in response_data["data"]["models"]]
            return []
            
        except Exception as e:
            console.print(f"[red]Error fetching models by categories: {str(e)}[/red]")
            return []

    def get_dynamic_task_categories(self) -> Dict[str, List[str]]:
        """
        Get dynamic task categories by mapping task types to OpenRouter categories.
        
        This method attempts to use OpenRouter's categorization system to find
        relevant models for different task types, with fallback patterns for reliability.
        
        Returns:
            Dictionary mapping task types to lists of relevant model IDs
        """
        # Configuration for mapping task types to categories and fallback patterns
        category_mapping = {
            "creative": {
                "openrouter_categories": ["Programming", "Technology"],
                "fallback_patterns": ["claude-3", "gpt-4", "llama", "gemini"]
            },
            "coding": {
                "openrouter_categories": ["Programming", "Technology"],
                "fallback_patterns": ["claude-3-opus", "gpt-4", "deepseek-coder", "qwen-coder", "devstral", "codestral"]
            },
            "analysis": {
                "openrouter_categories": ["Science", "Academia"],
                "fallback_patterns": ["claude-3-opus", "gpt-4", "mistral", "qwen"]
            },
            "chat": {
                "openrouter_categories": ["Programming"],
                "fallback_patterns": ["claude-3-haiku", "gpt-3.5", "gemini-pro", "llama"]
            }
        }

        dynamic_categories = {}
        
        for task_type, config in category_mapping.items():
            try:
                dynamic_categories[task_type] = self._get_task_models(config)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to get dynamic categories for {task_type}: {str(e)}[/yellow]")
                # Use fallback patterns in case of error
                dynamic_categories[task_type] = config["fallback_patterns"]
        
        return dynamic_categories

    def _get_task_models(self, config: Dict) -> List[str]:
        """
        Get models for a specific task configuration.
        
        Args:
            config: Configuration dictionary with categories and fallback patterns
            
        Returns:
            List of model IDs suitable for the task
        """
        # Try to get models from OpenRouter categories first
        category_models = self.get_models_by_categories(config["openrouter_categories"])
        
        if category_models:
            # Filter using fallback patterns for better accuracy
            filtered_models = [
                model_slug for model_slug in category_models
                if any(pattern in model_slug.lower() for pattern in config["fallback_patterns"])
            ]
            
            # Use filtered models if found, otherwise use top category models
            return filtered_models if filtered_models else category_models[:10]
        else:
            # Fallback to pattern-based filtering with all available models
            all_models = self.get_available_models()
            fallback_models = []
            
            for model in all_models:
                model_id = model.get('id', '').lower()
                if any(pattern in model_id for pattern in config["fallback_patterns"]):
                    fallback_models.append(model['id'])
            
            return fallback_models[:10]  # Limit to 10 for performance


# Global client instance for backward compatibility
client = OpenRouterClient()

# Convenience functions for backward compatibility
def get_available_models() -> List[Dict]:
    """Get available models using the global client instance."""
    return client.get_available_models()

def get_model_info(model_id: str) -> Optional[Dict]:
    """Get model info using the global client instance."""
    return client.get_model_info(model_id)

def get_enhanced_models() -> List[Dict]:
    """Get enhanced models using the global client instance."""
    return client.get_enhanced_models()

def get_models_by_capability(capability_filter: str = "all") -> List[Dict]:
    """Get models by capability using the global client instance."""
    return client.get_models_by_capability(capability_filter)

def get_models_by_group() -> Dict[str, List[Dict]]:
    """Get models by group using the global client instance."""
    return client.get_models_by_group()

def get_models_by_provider() -> Dict[str, List[Dict]]:
    """Get models by provider using the global client instance."""
    return client.get_models_by_provider()

def get_models_by_categories(categories: List[str]) -> List[str]:
    """Get models by categories using the global client instance."""
    return client.get_models_by_categories(categories)

def get_dynamic_task_categories() -> Dict[str, List[str]]:
    """Get dynamic task categories using the global client instance."""
    return client.get_dynamic_task_categories()
