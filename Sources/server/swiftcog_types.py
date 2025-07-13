"""
Core types for the SwiftCog Python server implementation.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel
from abc import ABC, abstractmethod
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
class KernelMessage(ABC):
    """Abstract base class for all kernel messages."""
    id: str
    source_kernel_id: KernelID
    timestamp: datetime
    
    def __init__(self, source_kernel_id: KernelID, message_id: Optional[str] = None):
        self.id = message_id or str(uuid.uuid4())
        self.source_kernel_id = source_kernel_id
        self.timestamp = datetime.now()
    
    @abstractmethod
    def get_message_type(self) -> str:
        """Get the message type identifier."""
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        pass
    
    def get_base_dict(self) -> Dict[str, Any]:
        """Get base dictionary with common fields."""
        return {
            "id": self.id,
            "sourceKernelId": self.source_kernel_id.value,
            "timestamp": self.timestamp.isoformat(),
            "messageType": self.get_message_type()
        }


@dataclass
class GazeMessage(KernelMessage):
    """Message containing gaze tracking data."""
    looking_at_screen: bool
    feature_vector: Optional[list] = None
    feature_vector_dimensions: Optional[int] = None
    
    def __init__(self, source_kernel_id: KernelID, looking_at_screen: bool, 
                 feature_vector: Optional[list] = None, feature_vector_dimensions: Optional[int] = None,
                 message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.looking_at_screen = looking_at_screen
        self.feature_vector = feature_vector
        self.feature_vector_dimensions = feature_vector_dimensions
    
    def get_message_type(self) -> str:
        return "gazeData"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "lookingAtScreen": self.looking_at_screen
        })
        if self.feature_vector is not None:
            result["featureVector"] = self.feature_vector
            result["featureVectorDimensions"] = self.feature_vector_dimensions
        return result


@dataclass
class VoiceMessage(KernelMessage):
    """Message containing voice/speech data."""
    transcription: str
    confidence: Optional[float] = None
    
    def __init__(self, source_kernel_id: KernelID, transcription: str, confidence: Optional[float] = None, message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.transcription = transcription
        self.confidence = confidence
    
    def get_message_type(self) -> str:
        return "voiceData"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "transcription": self.transcription
        })
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result


@dataclass
class ThoughtMessage(KernelMessage):
    """Message containing thought/reasoning data."""
    content: str
    
    def __init__(self, source_kernel_id: KernelID, content: str, message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.content = content
    
    def get_message_type(self) -> str:
        return "thoughtData"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "content": self.content
        })
        return result


@dataclass
class UIMessage(KernelMessage):
    """Message containing UI-related data."""
    content: str
    
    def __init__(self, source_kernel_id: KernelID, content: str, message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.content = content
    
    def get_message_type(self) -> str:
        return "uiData"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "content": self.content
        })
        return result


@dataclass
class TextMessage(KernelMessage):
    """Message containing plain text data (for backward compatibility)."""
    content: str
    
    def __init__(self, source_kernel_id: KernelID, content: str, message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.content = content
    
    def get_message_type(self) -> str:
        return "textData"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "content": self.content,
            "payload": self.content  # For backward compatibility
        })
        return result


@dataclass
class PersonPresenceMessage(KernelMessage):
    """Message containing person presence detection results."""
    is_present: bool
    person_id: Optional[str] = None
    
    def __init__(self, source_kernel_id: KernelID, is_present: bool, person_id: Optional[str] = None, message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.is_present = is_present
        self.person_id = person_id
    
    def get_message_type(self) -> str:
        return "personPresence"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "isPresent": self.is_present
        })
        if self.person_id is not None:
            result["personId"] = self.person_id
        return result


@dataclass
class ConceptCreationRequest(KernelMessage):
    """Message requesting creation of a new concept in memory."""
    concept_type: str
    concept_data: Dict[str, Any]
    
    def __init__(self, source_kernel_id: KernelID, concept_type: str, concept_data: Dict[str, Any], message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.concept_type = concept_type
        self.concept_data = concept_data
    
    def get_message_type(self) -> str:
        return "conceptCreationRequest"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "conceptType": self.concept_type,
            "conceptData": self.concept_data
        })
        return result


@dataclass
class ConversationMessage(KernelMessage):
    """Message containing conversation data to be stored in memory."""
    speaker: str  # "user" or "ai"
    content: str
    store_in_memory: bool = True
    
    def __init__(self, source_kernel_id: KernelID, speaker: str, content: str, store_in_memory: bool = True, message_id: Optional[str] = None):
        super().__init__(source_kernel_id, message_id)
        self.speaker = speaker
        self.content = content
        self.store_in_memory = store_in_memory
    
    def get_message_type(self) -> str:
        return "conversationMessage"
    
    def to_dict(self) -> Dict[str, Any]:
        result = self.get_base_dict()
        result.update({
            "speaker": self.speaker,
            "content": self.content,
            "storeInMemory": self.store_in_memory
        })
        return result


def create_kernel_message_from_dict(data: Dict[str, Any]) -> KernelMessage:
    """Factory method to create the appropriate KernelMessage subclass from dictionary."""
    source_kernel_id = KernelID(data["sourceKernelId"])
    message_id = data.get("id")
    
    # Handle legacy format (with payload field)
    if "payload" in data and "messageType" not in data:
        # Try to parse payload as JSON to determine message type
        try:
            payload_data = json.loads(data["payload"])
            if payload_data.get("messageType") == "gazeData":
                return GazeMessage(
                    source_kernel_id=source_kernel_id,
                    looking_at_screen=payload_data.get("lookingAtScreen", False),
                    feature_vector=payload_data.get("featureVector"),
                    feature_vector_dimensions=payload_data.get("featureVectorDimensions"),
                    message_id=message_id
                )
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Default to TextMessage for backward compatibility
        return TextMessage(
            source_kernel_id=source_kernel_id,
            content=data["payload"],
            message_id=message_id
        )
    
    # Handle new structured format
    message_type = data.get("messageType", "textData")
    
    if message_type == "gazeData":
        return GazeMessage(
            source_kernel_id=source_kernel_id,
            looking_at_screen=data.get("lookingAtScreen", False),
            feature_vector=data.get("featureVector"),
            feature_vector_dimensions=data.get("featureVectorDimensions"),
            message_id=message_id
        )
    elif message_type == "voiceData":
        return VoiceMessage(
            source_kernel_id=source_kernel_id,
            transcription=data.get("transcription", ""),
            confidence=data.get("confidence"),
            message_id=message_id
        )
    elif message_type == "thoughtData":
        return ThoughtMessage(
            source_kernel_id=source_kernel_id,
            content=data.get("content", ""),
            message_id=message_id
        )
    elif message_type == "uiData":
        return UIMessage(
            source_kernel_id=source_kernel_id,
            content=data.get("content", ""),
            message_id=message_id
        )
    elif message_type == "personPresence":
        return PersonPresenceMessage(
            source_kernel_id=source_kernel_id,
            is_present=data.get("isPresent", False),
            person_id=data.get("personId"),
            message_id=message_id
        )
    elif message_type == "conceptCreationRequest":
        return ConceptCreationRequest(
            source_kernel_id=source_kernel_id,
            concept_type=data.get("conceptType", ""),
            concept_data=data.get("conceptData", {}),
            message_id=message_id
        )
    elif message_type == "conversationMessage":
        return ConversationMessage(
            source_kernel_id=source_kernel_id,
            speaker=data.get("speaker", "user"),
            content=data.get("content", ""),
            store_in_memory=data.get("storeInMemory", True),
            message_id=message_id
        )
    else:  # textData or unknown
        return TextMessage(
            source_kernel_id=source_kernel_id,
            content=data.get("content", data.get("payload", "")),
            message_id=message_id
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
            kernel_message=create_kernel_message_from_dict(data["kernelMessage"]) if "kernelMessage" in data else None,
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
            return create_kernel_message_from_dict(self.kernel_message)
        return None 