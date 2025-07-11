"""
Shared kernel components for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Optional
import ray
from swiftcog_types import KernelID, KernelMessage
from llm_service import LLMService, OpenAIProvider


@ray.remote
class SharedLLMService:
    """Shared LLM service as a Ray actor for use across all kernels."""
    
    def __init__(self, api_key: str):
        openai_provider = OpenAIProvider(api_key)
        self.llm_service = LLMService(openai_provider)
    
    async def process_message(self, message: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 500):
        """Process a message using the LLM service."""
        return await self.llm_service.process_message(
            message=message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )


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