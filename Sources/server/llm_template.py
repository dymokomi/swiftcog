"""
LLM Template system for SwiftCog - supports loading templates from files with variable substitution.
"""
import json
import yaml
import os
import re
from typing import Dict, Any, Optional
from pathlib import Path


class LLMTemplate:
    """Template system for LLM prompts with variable substitution."""
    
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(__file__).parent / templates_dir
        self.templates_cache: Dict[str, Dict[str, Any]] = {}
        
        # Create templates directory if it doesn't exist
        self.templates_dir.mkdir(exist_ok=True)
        
        print(f"LLMTemplate: Initialized with templates directory: {self.templates_dir}")
    
    def _load_template(self, template_name: str) -> Dict[str, Any]:
        """Load a template from file."""
        if template_name in self.templates_cache:
            return self.templates_cache[template_name]
        
        # Try YAML first, then JSON for backward compatibility
        yaml_path = self.templates_dir / f"{template_name}.yaml"
        json_path = self.templates_dir / f"{template_name}.json"
        
        template_path = None
        if yaml_path.exists():
            template_path = yaml_path
        elif json_path.exists():
            template_path = json_path
        else:
            raise FileNotFoundError(f"Template not found: {template_name} (looked for .yaml and .json)")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                if template_path.suffix == '.yaml':
                    template_data = yaml.safe_load(f)
                else:
                    template_data = json.load(f)
            
            # Validate template structure
            required_fields = ['system_prompt', 'user_message']
            for field in required_fields:
                if field not in template_data:
                    raise ValueError(f"Template {template_name} missing required field: {field}")
            
            self.templates_cache[template_name] = template_data
            return template_data
            
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise ValueError(f"Invalid format in template {template_name}: {e}")
    
    def _substitute_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in text using {{variable_name}} syntax."""
        def replace_var(match):
            var_name = match.group(1)
            if var_name in variables:
                value = variables[var_name]
                # Convert to string, handling lists and dicts nicely
                if isinstance(value, (list, dict)):
                    return json.dumps(value, indent=2)
                return str(value)
            else:
                # Keep the original placeholder if variable not found
                return match.group(0)
        
        # Replace {{variable_name}} patterns
        return re.sub(r'\{\{(\w+)\}\}', replace_var, text)
    
    def call(self, template_name: str, **variables) -> Dict[str, str]:
        """
        Call a template with variables and return system_prompt and user_message.
        
        Args:
            template_name: Name of the template file (without .json extension)
            **variables: Variables to substitute in the template
            
        Returns:
            Dict with 'system_prompt' and 'user_message' keys
        """
        template_data = self._load_template(template_name)
        
        # Substitute variables in both system_prompt and user_message
        system_prompt = self._substitute_variables(template_data['system_prompt'], variables)
        user_message = self._substitute_variables(template_data['user_message'], variables)
        
        return {
            'system_prompt': system_prompt,
            'user_message': user_message
        }
    
    def reload_template(self, template_name: str) -> None:
        """Reload a template from file (useful for development)."""
        if template_name in self.templates_cache:
            del self.templates_cache[template_name]
        self._load_template(template_name)
    
    def list_templates(self) -> list:
        """List all available templates."""
        if not self.templates_dir.exists():
            return []
        
        templates = set()
        # Add YAML templates
        for f in self.templates_dir.glob("*.yaml"):
            templates.add(f.stem)
        # Add JSON templates (for backward compatibility)
        for f in self.templates_dir.glob("*.json"):
            templates.add(f.stem)
        
        return sorted(list(templates))
    
    def create_template(self, template_name: str, system_prompt: str, user_message: str, metadata: Optional[Dict[str, Any]] = None, format: str = "yaml") -> None:
        """Create a new template file."""
        template_data = {
            'system_prompt': system_prompt,
            'user_message': user_message
        }
        
        if metadata:
            template_data['metadata'] = metadata
        
        if format == "yaml":
            template_path = self.templates_dir / f"{template_name}.yaml"
            with open(template_path, 'w', encoding='utf-8') as f:
                yaml.dump(template_data, f, default_flow_style=False, allow_unicode=True)
        else:
            template_path = self.templates_dir / f"{template_name}.json"
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)
        
        print(f"LLMTemplate: Created template {template_name} at {template_path}")


# Global instance
llm_template = LLMTemplate() 