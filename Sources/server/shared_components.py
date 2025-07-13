"""
Shared kernel components for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import ray
from swiftcog_types import KernelID, KernelMessage
from llm_service import LLMService, OpenAIProvider, ToolDefinition


@ray.remote
class SharedLLMService:
    """Shared LLM service as a Ray actor for use across all kernels."""
    
    def __init__(self, api_key: str):
        openai_provider = OpenAIProvider(api_key)
        self.llm_service = LLMService(openai_provider)
    
    async def process_message(self, message: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 500, template_name: str = "unknown"):
        """Process a message using the LLM service."""
        return await self.llm_service.process_message(
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            template_name=template_name
        )
    
    async def process_message_with_tools(self, message: str, system_prompt: str = None, tools: List[ToolDefinition] = None, temperature: float = 0.7, max_tokens: int = 500, max_tool_calls: int = 1, template_name: str = "unknown") -> Dict[str, Any]:
        """Process a message with tool calling support."""
        return await self.llm_service.process_message_with_tools(
            message=message,
            system_prompt=system_prompt,
            tools=tools or [],
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_calls=max_tool_calls,
            template_name=template_name
        )
    
    async def execute_tools(self, tool_calls: List[Dict[str, Any]], available_tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Execute tool calls and return results."""
        return await self.llm_service.execute_tools(tool_calls, available_tools)


class Kernel(ABC):
    """Abstract base class for all kernels."""
    
    @abstractmethod
    def get_kernel_id(self) -> KernelID:
        """Get the kernel ID."""
        pass
    
    @abstractmethod
    async def receive(self, message: KernelMessage) -> None:
        """Receive and process a message."""
        pass 