import requests
from rich.console import Console

from config import load_config

console = Console()

def get_available_models():
    """Fetch available models from OpenRouter API"""
    try:
        config = load_config()
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        with console.status("[bold green]Fetching available models..."):
            response = requests.get("https://openrouter.ai/api/v1/models", headers=headers)

        if response.status_code == 200:
            models_data = response.json()
            return models_data["data"]
        console.print(f"[red]Error fetching models: {response.status_code}[/red]")
        return []
    except Exception as e:
        console.print(f"[red]Error fetching models: {str(e)}[/red]")
        return []

def get_model_info(model_id):
    """Get model information of all models"""
    models = get_available_models()
    
    try:
        for model in models:
            if model["id"] == model_id:
                return model
        
        console.print(f"[yellow]Warning: Could not find info for model '{model_id}'.[/yellow]")
        return None
    except Exception as e:
        console.print(f"[red] Failed to fetch model info: {str(e)}[/red]")
        return None

def get_enhanced_models():
    """Fetch enhanced model data from OpenRouter frontend API with detailed capabilities"""
    try:
        config = load_config()
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        with console.status("[bold green]Fetching enhanced model data..."):
            response = requests.get("https://openrouter.ai/api/frontend/models", headers=headers)

        if response.status_code == 200:
            models_data = response.json()
            return models_data.get("data", [])
        else:
            console.print(f"[red]Error fetching enhanced models: {response.status_code}[/red]")
            # Fallback to standard models API
            return get_available_models()
    except Exception as e:
        console.print(f"[red]Error fetching enhanced models: {str(e)}[/red]")
        # Fallback to standard models API
        return get_available_models()

def get_models_by_capability(capability_filter="all"):
    """Get models filtered by specific capabilities using the enhanced frontend API"""
    try:
        enhanced_models = get_enhanced_models()
        
        if capability_filter == "all":
            return enhanced_models
        
        filtered_models = []
        
        for model in enhanced_models:
            # Skip None models
            if model is None:
                continue
                
            # Extract capability information from the endpoint data
            endpoint = model.get('endpoint', {})
            if endpoint is None:
                continue
            
            if capability_filter == "reasoning":
                # Check if model supports reasoning/thinking
                supports_reasoning = endpoint.get('supports_reasoning', False)
                reasoning_config = model.get('reasoning_config') or endpoint.get('reasoning_config')
                if supports_reasoning or reasoning_config:
                    filtered_models.append(model)
                    
            elif capability_filter == "multipart":
                # Check if model supports multipart (images/files)
                supports_multipart = endpoint.get('supports_multipart', False)
                input_modalities = model.get('input_modalities', [])
                if supports_multipart or ('image' in input_modalities):
                    filtered_models.append(model)
                    
            elif capability_filter == "tools":
                # Check if model supports tool parameters
                supports_tools = endpoint.get('supports_tool_parameters', False)
                supported_params = endpoint.get('supported_parameters', [])
                if supported_params is None:
                    supported_params = []
                if supports_tools or 'tools' in supported_params:
                    filtered_models.append(model)
                    
            elif capability_filter == "free":
                # Check if model is free
                is_free = endpoint.get('is_free', False)
                pricing = endpoint.get('pricing', {})
                if pricing is None:
                    pricing = {}
                prompt_price = float(pricing.get('prompt', '0'))
                if is_free or prompt_price == 0:
                    filtered_models.append(model)
                    
        return filtered_models
        
    except Exception as e:
        console.print(f"[red]Error filtering models by capability: {str(e)}[/red]")
        # Fallback to standard models
        return get_available_models()

def get_models_by_group():
    """Get models organized by their groups using enhanced API"""
    try:
        enhanced_models = get_enhanced_models()
        groups = {}
        
        for model in enhanced_models:
            # Skip None models
            if model is None:
                continue
                
            group = model.get('group', 'Other')
            if group not in groups:
                groups[group] = []
            groups[group].append(model)
        
        return groups
        
    except Exception as e:
        console.print(f"[red]Error grouping models: {str(e)}[/red]")
        return {}

def get_models_by_provider():
    """Get models organized by their providers using enhanced API"""
    try:
        enhanced_models = get_enhanced_models()
        providers = {}
        
        for model in enhanced_models:
            # Skip None models
            if model is None:
                continue
                
            endpoint = model.get('endpoint', {})
            if endpoint is None:
                continue
                
            provider = endpoint.get('provider_name', 'Unknown')
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model)
        
        return providers
        
    except Exception as e:
        console.print(f"[red]Error organizing models by provider: {str(e)}[/red]")
        return {}

def get_models_by_categories(categories):
    """Fetch models by categories from OpenRouter API using the find endpoint"""
    try:
        config = load_config()
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        # Convert categories list to comma-separated string for the API
        categories_param = ",".join(categories) if isinstance(categories, list) else categories
        
        with console.status(f"[bold green]Fetching models for categories: {categories_param}..."):
            response = requests.get(
                f"https://openrouter.ai/api/frontend/models/find?categories={categories_param}",
                headers=headers
            )

        if response.status_code == 200:
            models_data = response.json()
            # Extract model slugs from the response
            if "data" in models_data and "models" in models_data["data"]:
                return [model["slug"] for model in models_data["data"]["models"]]
            return []
        else:
            console.print(f"[red]Error fetching models by categories: {response.status_code}[/red]")
            return []
    except Exception as e:
        console.print(f"[red]Error fetching models by categories: {str(e)}[/red]")
        return []

def get_dynamic_task_categories():
    """Get dynamic task categories by fetching models from specific OpenRouter categories"""
    # Map our task types to OpenRouter categories and fallback model patterns
    category_mapping = {
        "creative": {
            "openrouter_categories": ["Programming", "Technology"],  # OpenRouter categories that might contain creative models
            "fallback_patterns": ["claude-3", "gpt-4", "llama", "gemini"]  # Fallback to original patterns
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
            "openrouter_categories": ["Programming"],  # General chat category
            "fallback_patterns": ["claude-3-haiku", "gpt-3.5", "gemini-pro", "llama"]
        }
    }

    dynamic_categories = {}
    
    for task_type, config in category_mapping.items():
        try:
            # Try to get models from OpenRouter categories first
            category_models = get_models_by_categories(config["openrouter_categories"])
            
            if category_models:
                # Filter to get relevant models based on fallback patterns for better accuracy
                filtered_models = []
                for model_slug in category_models:
                    if any(pattern in model_slug.lower() for pattern in config["fallback_patterns"]):
                        filtered_models.append(model_slug)
                
                # If we found filtered models, use them, otherwise use all category models
                dynamic_categories[task_type] = filtered_models if filtered_models else category_models[:10]  # Limit to 10 for performance
            else:
                # Fallback to pattern-based filtering with all available models
                all_models = get_available_models()
                fallback_models = []
                for model in all_models:
                    model_id = model.get('id', '').lower()
                    if any(pattern in model_id for pattern in config["fallback_patterns"]):
                        fallback_models.append(model['id'])
                
                dynamic_categories[task_type] = fallback_models[:10]  # Limit to 10 for performance
                        
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to get dynamic categories for {task_type}: {str(e)}[/yellow]")
            # Use fallback patterns in case of error
            dynamic_categories[task_type] = config["fallback_patterns"]
    
    return dynamic_categories
