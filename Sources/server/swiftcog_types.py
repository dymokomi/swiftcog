"""
Core types for the SwiftCog Python server implementation.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel
import uuid
import json


class KernelID(Enum):
    """Kernel identifiers matching the Swift implementation."""
    SENSING = "sensing"
    EXECUTIVE = "executive"
    MEMORY = "memory"
    LEARNING = "learning"
    MOTOR = "motor"
    EXPRESSION = "expression"
    SENSING_INTERFACE = "sensing-interface"


@dataclass
class KernelMessage:
    """Kernel message structure matching the Swift implementation."""
    id: str
    source_kernel_id: KernelID
    payload: str
    timestamp: datetime
    
    def __init__(self, source_kernel_id: KernelID, payload: str, message_id: Optional[str] = None):
        self.id = message_id or str(uuid.uuid4())
        self.source_kernel_id = source_kernel_id
        self.payload = payload
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "sourceKernelId": self.source_kernel_id.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KernelMessage':
        """Create from dictionary for JSON deserialization."""
        return cls(
            source_kernel_id=KernelID(data["sourceKernelId"]),
            payload=data["payload"],
            message_id=data.get("id")
        )


@dataclass
class AsyncMessage:
    """Async message wrapper matching the Swift implementation."""
    type: str
    kernel_message: Optional[KernelMessage] = None
    app_code: Optional[str] = None
    app_name: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"type": self.type}
        
        if self.kernel_message:
            result["kernelMessage"] = self.kernel_message.to_dict()
        if self.app_code:
            result["appCode"] = self.app_code
        if self.app_name:
            result["appName"] = self.app_name
        if self.error_message:
            result["errorMessage"] = self.error_message
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AsyncMessage':
        """Create from dictionary for JSON deserialization."""
        return cls(
            type=data["type"],
            kernel_message=KernelMessage.from_dict(data["kernelMessage"]) if "kernelMessage" in data else None,
            app_code=data.get("appCode"),
            app_name=data.get("appName"),
            error_message=data.get("errorMessage")
        )


class DisplayCommandType(Enum):
    """Display command types matching the Swift implementation."""
    TEXT_BUBBLE = "textBubble"
    CLEAR_SCREEN = "clearScreen"
    HIGHLIGHT_TEXT = "highlightText"
    DISPLAY_LIST = "displayList"
    UPDATE_STATUS = "updateStatus"
    SHOW_THINKING = "showThinking"
    HIDE_THINKING = "hideThinking"
    SHOW_MESSAGE = "showMessage"


class MessageType(Enum):
    """Message types for server communication."""
    KERNEL_MESSAGE = "kernelMessage"
    LOAD_APP = "loadApp"
    APP_LOADED = "appLoaded"
    ERROR = "error"


@dataclass
class DisplayCommand:
    """Base display command class."""
    type: DisplayCommandType
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {"type": self.type.value}


@dataclass
class TextBubbleCommand(DisplayCommand):
    """Text bubble command matching the Swift implementation."""
    text: str
    is_user: bool
    timestamp: datetime
    
    def __init__(self, text: str, is_user: bool):
        super().__init__(DisplayCommandType.TEXT_BUBBLE)
        self.text = text
        self.is_user = is_user
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "text": self.text,
            "isUser": self.is_user,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ShowThinkingCommand(DisplayCommand):
    """Show thinking command matching the Swift implementation."""
    
    def __init__(self):
        super().__init__(DisplayCommandType.SHOW_THINKING)


@dataclass
class HideThinkingCommand(DisplayCommand):
    """Hide thinking command matching the Swift implementation."""
    
    def __init__(self):
        super().__init__(DisplayCommandType.HIDE_THINKING)


def create_display_command_json(command: DisplayCommand) -> str:
    """Create JSON string from display command."""
    return json.dumps(command.to_dict())


class WebSocketMessage(BaseModel):
    """WebSocket message structure for FastAPI integration."""
    type: str
    kernel_message: Optional[Dict[str, Any]] = None
    app_code: Optional[str] = None
    app_name: Optional[str] = None
    success: Optional[bool] = None
    message: Optional[str] = None
    
    def get_kernel_message(self) -> Optional[KernelMessage]:
        """Extract KernelMessage from the dictionary."""
        if self.kernel_message:
            return KernelMessage.from_dict(self.kernel_message)
        return None 