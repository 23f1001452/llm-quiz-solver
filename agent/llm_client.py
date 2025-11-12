# ============================================================================
# agent/llm_client.py - LLM API Wrapper
# ============================================================================

import os
from groq import AsyncGroq
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client supporting multiple providers
    """
    
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.ai21_key = os.getenv("AI21_API_KEY")
        
        # Initialize Groq client if available
        if self.groq_key:
            self.groq_client = AsyncGroq(api_key=self.groq_key)
            self.provider = "groq"
            self.model = "llama-3.3-70b-versatile"  # Updated to current model
            logger.info("Initialized Groq client")
        else:
            raise ValueError("No LLM API key found. Please set GROQ_API_KEY or AI21_API_KEY")
    
    async def chat(
        self,
        messages: list,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        **kwargs
    ) -> str:
        """
        Send chat completion request
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            str: Generated text response
        """
        try:
            if self.provider == "groq":
                response = await self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM API error: {str(e)}")
            raise
    
    async def chat_with_tools(
        self,
        messages: list,
        tools: list,
        temperature: float = 0.1,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Chat with function calling / tool use
        
        Returns:
            dict: Response with potential tool calls
        """
        try:
            if self.provider == "groq":
                response = await self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tool_choice="auto"
                )
                return {
                    "content": response.choices[0].message.content,
                    "tool_calls": response.choices[0].message.tool_calls
                }
        except Exception as e:
            logger.error(f"LLM tool use error: {str(e)}")
            raise
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)"""
        return len(text) // 4