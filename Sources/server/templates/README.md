# LLM Templates

This directory contains LLM prompt templates for the SwiftCog system. Templates are stored as YAML files with variable substitution support for easy reading and editing.

## Template Format

Each template is a YAML file with the following structure:

```yaml
system_prompt: |
  Your system prompt here with {{variable_name}} placeholders.
  Multi-line strings are naturally supported without escape characters.
  This makes templates much more readable and editable.

user_message: |
  Your user message here with {{variable_name}} placeholders.
  You can use natural line breaks and formatting.
  No need for \n escape characters!

metadata:
  description: Description of what this template does
  version: "2.0"
  format: yaml
  variables:
    - list
    - of
    - variable
    - names
```

## Variable Substitution

Variables are substituted using `{{variable_name}}` syntax. The template system supports:

- **String variables**: `{{person_id}}` → `"person_123"`
- **Number variables**: `{{count}}` → `5`
- **List variables**: `{{items}}` → JSON formatted list
- **Dict variables**: `{{data}}` → JSON formatted object

## Benefits of YAML Format

- **No escape characters**: Multi-line strings use natural line breaks
- **Easy to read**: Clean, indented structure
- **Easy to edit**: No JSON syntax complications
- **Comments supported**: Use `#` for comments
- **Natural formatting**: Preserves readability

## Usage

```python
from llm_template import llm_template

# Call a template with variables
result = llm_template.call(
    "learning_opportunities",
    person_id="person_123",
    person_concepts_count=5,
    person_concepts=["concept1", "concept2"]
)

# Get the prompts
system_prompt = result['system_prompt']
user_message = result['user_message']
```

## Available Templates

- **`learning_opportunities.yaml`**: Analyzes learning opportunities when a person is added to context
- **`executive_decision.yaml`**: Executive kernel decision-making and response generation

## Creating New Templates

1. Create a new YAML file in this directory
2. Follow the template format above
3. Use `{{variable_name}}` for variable substitution
4. Document variables in the metadata section

### Manual Creation
Create a file like `my_template.yaml`:
```yaml
system_prompt: |
  You are a helpful assistant.
  Today is {{date}}.

user_message: |
  Please help me with {{task}}.
  What would you like to know?

metadata:
  description: A helpful assistant template
  variables:
    - date
    - task
```

### Programmatic Creation
```python
from llm_template import llm_template

# Create a new template programmatically (YAML by default)
llm_template.create_template(
    "my_template",
    system_prompt="You are a helpful assistant.\nToday is {{date}}.",
    user_message="Please help me with {{task}}.",
    metadata={"variables": ["date", "task"]}
)
```

## Benefits

- **Separation of concerns**: Prompts are separate from code
- **Easy editing**: Templates can be edited without code changes  
- **Readable format**: YAML format with natural multi-line strings
- **No escape characters**: Write prompts naturally without `\n`
- **Version control**: Templates can be versioned and tracked
- **Reusability**: Templates can be used across different parts of the system
- **Variable substitution**: Dynamic content without string formatting in code
- **Comments supported**: Add documentation directly in templates
- **Backward compatibility**: Still supports JSON templates if needed 