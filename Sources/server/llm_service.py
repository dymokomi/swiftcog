"""
LLM service implementation for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable
import openai
import os
import json
import yaml
import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMTracer:
    """LLM tracing utility for logging prompts and responses."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
    def trace_llm_call(self, template_name: str, system_prompt: str, user_message: str, 
                      response: str, tools: list = None, metadata: dict = None):
        """Log an LLM call with all context."""
        try:
            timestamp = datetime.datetime.now()
            
            # Create trace data in a more readable format
            trace_data = {
                "timestamp": timestamp.isoformat(),
                "template_name": template_name,
                "metadata": metadata or {},
                "tools_available": [tool.name if hasattr(tool, 'name') else str(tool) for tool in (tools or [])],
                "system_prompt": system_prompt,
                "user_message": user_message,
                "response": response
            }
            
            # Create filename with timestamp and template name
            safe_template = template_name.replace("/", "_").replace("\\", "_")
            timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
            filename = f"{safe_template}_{timestamp_str}.yaml"
            
            # Save to template-specific subdirectory
            template_dir = self.log_dir / safe_template
            template_dir.mkdir(exist_ok=True)
            
            filepath = template_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(trace_data, f, default_flow_style=False, allow_unicode=True, width=120)
                
            print(f"LLMTracer: Saved trace to {filepath}")
            
        except Exception as e:
            print(f"LLMTracer: Error saving trace: {e}")


class ToolDefinition:
    """Tool definition for LLM function calling."""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], function: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_completion(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        tools: Optional[List[ToolDefinition]] = None
    ) -> str:
        """Generate a completion from the LLM provider."""
        pass
    
    @abstractmethod
    async def generate_completion_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: List[ToolDefinition],
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_tool_calls: int = 1
    ) -> Dict[str, Any]:
        """Generate a completion with tool calling support."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation matching the Swift version."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Initialize OpenAI client
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
    
    async def generate_completion(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        tools: Optional[List[ToolDefinition]] = None
    ) -> str:
        """Generate a completion using OpenAI's API."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            kwargs = {
                "model": "gpt-4.1",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            if tools:
                kwargs["tools"] = [tool.to_openai_format() for tool in tools]
                kwargs["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**kwargs)
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                raise ValueError("No response from OpenAI")
                
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def generate_completion_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: List[ToolDefinition],
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_tool_calls: int = 1
    ) -> Dict[str, Any]:
        """Generate a completion with tool calling support."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=[tool.to_openai_format() for tool in tools],
                tool_choice="auto"
            )
            
            if not response.choices:
                raise ValueError("No response from OpenAI")
            
            message = response.choices[0].message
            
            result = {
                "content": message.content,
                "tool_calls": []
            }
            
            if message.tool_calls:
                # Limit the number of tool calls to max_tool_calls
                limited_tool_calls = message.tool_calls[:max_tool_calls]
                for tool_call in limited_tool_calls:
                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "function": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    })
            
            return result
                
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")


class LLMService:
    """LLM service wrapper matching the Swift implementation."""
    
    def __init__(self, provider: LLMProvider, enable_tracing: bool = True):
        self.provider = provider
        self.tracer = LLMTracer() if enable_tracing else None
    
    async def process_message(
        self,
        message: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        template_name: str = "unknown"
    ) -> str:
        """Process a message using the LLM provider."""
        response = await self.provider.generate_completion(
            system_prompt=system_prompt,
            user_message=message,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Log the trace
        if self.tracer:
            metadata = {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "has_tools": False
            }
            self.tracer.trace_llm_call(
                template_name=template_name,
                system_prompt=system_prompt,
                user_message=message,
                response=response or '',  # Handle None response
                metadata=metadata
            )
        
        return response
    
    async def process_message_with_tools(
        self,
        message: str,
        system_prompt: str,
        tools: List[ToolDefinition],
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_tool_calls: int = 1,
        template_name: str = "unknown"
    ) -> Dict[str, Any]:
        """Process a message with tool calling support."""
        response = await self.provider.generate_completion_with_tools(
            system_prompt=system_prompt,
            user_message=message,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_calls=max_tool_calls
        )
        
        # Log the trace
        if self.tracer:
            metadata = {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "max_tool_calls": max_tool_calls,
                "has_tools": True,
                "tool_calls_made": len(response.get('tool_calls', []))
            }
            response_content = response.get('content') or ''  # Handle None safely
            response_text = response_content + (
                f" [TOOLS: {len(response.get('tool_calls', []))} calls]" if response.get('tool_calls') else ""
            )
            self.tracer.trace_llm_call(
                template_name=template_name,
                system_prompt=system_prompt,
                user_message=message,
                response=response_text,
                tools=tools,
                metadata=metadata
            )
        
        return response
    
    async def execute_tools(self, tool_calls: List[Dict[str, Any]], available_tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []
        
        tool_map = {tool.name: tool for tool in available_tools}
        
        for tool_call in tool_calls:
            function_name = tool_call["function"]
            arguments = tool_call["arguments"]
            
            if function_name in tool_map:
                try:
                    # Execute the tool function
                    tool_function = tool_map[function_name].function
                    result = await tool_function(**arguments)
                    
                    results.append({
                        "call_id": tool_call["id"],
                        "function": function_name,
                        "result": result,
                        "success": True
                    })
                except Exception as e:
                    results.append({
                        "call_id": tool_call["id"],
                        "function": function_name,
                        "result": f"Error: {str(e)}",
                        "success": False
                    })
            else:
                results.append({
                    "call_id": tool_call["id"],
                    "function": function_name,
                    "result": f"Unknown function: {function_name}",
                    "success": False
                })
        
        return results 