"""
LLM service implementation for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable
import openai
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


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
        max_tokens: int = 500
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
                "model": "gpt-4o-mini",
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
        max_tokens: int = 500
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
                for tool_call in message.tool_calls:
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
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
    
    async def process_message(
        self,
        message: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Process a message using the LLM provider."""
        return await self.provider.generate_completion(
            system_prompt=system_prompt,
            user_message=message,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    async def process_message_with_tools(
        self,
        message: str,
        system_prompt: str,
        tools: List[ToolDefinition],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """Process a message with tool calling support."""
        return await self.provider.generate_completion_with_tools(
            system_prompt=system_prompt,
            user_message=message,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
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