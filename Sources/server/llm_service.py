"""
LLM service implementation for the SwiftCog Python server.
"""
from abc import ABC, abstractmethod
from typing import Optional
import openai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_completion(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate a completion from the LLM provider."""
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
        max_tokens: int = 500
    ) -> str:
        """Generate a completion using OpenAI's API."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                raise ValueError("No response from OpenAI")
                
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