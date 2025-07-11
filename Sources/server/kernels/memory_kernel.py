"""
Memory kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional, Dict, Any, List
import ray
from datetime import datetime
from swiftcog_types import KernelID, KernelMessage, TextMessage, GazeMessage
from .base_kernel import BaseKernel
from .memory_storage import MemoryStorage

"""
Memory organization:

Working memory:
1. Current dialog history (for now last 10 messages) and everything later
should be collapsed into a summary 
2. Current person who is speaking 
3. Goals

Long term memory:
1. Facts that are remembered arranged hierarchically
2. Visual memory of people (facial data)
3. Long term goals
"""

@ray.remote
class MemoryKernel(BaseKernel):
    """Memory kernel implementation with persistent storage."""
    
    def __init__(self, custom_handler: Optional[Callable] = None, storage_path: str = "memory_storage.json"):
        super().__init__(KernelID.MEMORY, custom_handler)
        self.storage = MemoryStorage(storage_path)
        self._initialize_memory_structure()
    
    def _initialize_memory_structure(self) -> None:
        """Initialize the memory structure if it doesn't exist."""
        # Working memory initialization
        if "working_memory" not in self.storage:
            self.storage.set("working_memory", {
                "dialog_history": [],
                "current_speaker": None,
                "current_goals": [],
                "session_start_time": datetime.now().isoformat()
            })
        
        # Long term memory initialization
        if "long_term_memory" not in self.storage:
            self.storage.set("long_term_memory", {
                "facts": {},
                "visual_memory": {},
                "long_term_goals": [],
                "conversation_summaries": []
            })
        
        # Statistics and metadata
        if "metadata" not in self.storage:
            self.storage.set("metadata", {
                "total_messages_processed": 0,
                "last_active": datetime.now().isoformat(),
                "kernel_version": "1.0.0"
            })
    
    def _update_metadata(self) -> None:
        """Update metadata with current timestamp and increment message count."""
        metadata = self.storage.get("metadata", {})
        metadata["total_messages_processed"] = metadata.get("total_messages_processed", 0) + 1
        metadata["last_active"] = datetime.now().isoformat()
        self.storage.set("metadata", metadata)
    
    def _store_dialog_message(self, message: KernelMessage) -> None:
        """Store a message in the dialog history."""
        working_memory = self.storage.get("working_memory", {})
        dialog_history = working_memory.get("dialog_history", [])
        
        # Create a dialog entry
        dialog_entry = {
            "timestamp": datetime.now().isoformat(),
            "source_kernel": message.source_kernel_id.value,
            "message_type": type(message).__name__,
            "content": None
        }
        
        if isinstance(message, TextMessage):
            dialog_entry["content"] = message.content
        elif isinstance(message, GazeMessage):
            dialog_entry["content"] = f"looking_at_screen: {message.looking_at_screen}"
        else:
            dialog_entry["content"] = str(message)
        
        dialog_history.append(dialog_entry)
        
        # Keep only the last 10 messages in working memory
        if len(dialog_history) > 10:
            # Move older messages to long-term memory summary
            self._archive_old_messages(dialog_history[:-10])
            dialog_history = dialog_history[-10:]
        
        working_memory["dialog_history"] = dialog_history
        self.storage.set("working_memory", working_memory)
    
    def _archive_old_messages(self, old_messages: List[Dict]) -> None:
        """Archive old messages to long-term memory."""
        if not old_messages:
            return
        
        long_term_memory = self.storage.get("long_term_memory", {})
        summaries = long_term_memory.get("conversation_summaries", [])
        
        # Create a summary of the archived messages
        summary = {
            "timestamp": datetime.now().isoformat(),
            "message_count": len(old_messages),
            "time_range": {
                "start": old_messages[0]["timestamp"],
                "end": old_messages[-1]["timestamp"]
            },
            "summary": f"Archived {len(old_messages)} messages from conversation",
            "messages": old_messages  # Store full messages for now; could summarize later
        }
        
        summaries.append(summary)
        long_term_memory["conversation_summaries"] = summaries
        self.storage.set("long_term_memory", long_term_memory)
    
    def _store_fact(self, fact: str, category: str = "general") -> None:
        """Store a fact in long-term memory."""
        long_term_memory = self.storage.get("long_term_memory", {})
        facts = long_term_memory.get("facts", {})
        
        if category not in facts:
            facts[category] = []
        
        fact_entry = {
            "content": fact,
            "timestamp": datetime.now().isoformat(),
            "confidence": 1.0  # Could be adjusted based on source
        }
        
        facts[category].append(fact_entry)
        long_term_memory["facts"] = facts
        self.storage.set("long_term_memory", long_term_memory)
    
    def set_current_speaker(self, speaker: str) -> None:
        """Set the current speaker in working memory."""
        working_memory = self.storage.get("working_memory", {})
        working_memory["current_speaker"] = speaker
        self.storage.set("working_memory", working_memory)
        print(f"MemoryKernel: Current speaker set to: {speaker}")
    
    def add_goal(self, goal: str, is_long_term: bool = False) -> None:
        """Add a goal to memory."""
        if is_long_term:
            long_term_memory = self.storage.get("long_term_memory", {})
            goals = long_term_memory.get("long_term_goals", [])
            goals.append({
                "goal": goal,
                "timestamp": datetime.now().isoformat(),
                "status": "active"
            })
            long_term_memory["long_term_goals"] = goals
            self.storage.set("long_term_memory", long_term_memory)
            print(f"MemoryKernel: Added long-term goal: {goal}")
        else:
            working_memory = self.storage.get("working_memory", {})
            goals = working_memory.get("current_goals", [])
            goals.append({
                "goal": goal,
                "timestamp": datetime.now().isoformat(),
                "status": "active"
            })
            working_memory["current_goals"] = goals
            self.storage.set("working_memory", working_memory)
            print(f"MemoryKernel: Added current goal: {goal}")
    
    def get_recent_context(self) -> Dict[str, Any]:
        """Get recent context for other kernels."""
        working_memory = self.storage.get("working_memory", {})
        return {
            "current_speaker": working_memory.get("current_speaker"),
            "recent_messages": working_memory.get("dialog_history", [])[-3:],  # Last 3 messages
            "active_goals": working_memory.get("current_goals", [])
        }
    
    async def receive(self, message: KernelMessage) -> None:
        """Process and store memory-related information."""
        # Store the message in dialog history
        self._store_dialog_message(message)
        
        # Process different message types
        if isinstance(message, TextMessage):
            content = message.content
            
            # Log based on source kernel
            if message.source_kernel_id == KernelID.LEARNING:
                print(f"MemoryKernel: Storing learning content: {content}")
                self._store_fact(content, "learning")
            elif message.source_kernel_id == KernelID.SENSING:
                print(f"MemoryKernel: Storing sensing content: {content}")
                self._store_fact(content, "sensing")
            elif message.source_kernel_id == KernelID.EXECUTIVE:
                print(f"MemoryKernel: Storing executive content: {content}")
                # Executive messages might contain goals or decisions
                if "goal" in content.lower():
                    self.add_goal(content)
                else:
                    self._store_fact(content, "executive")
            elif message.source_kernel_id == KernelID.SENSING_INTERFACE:
                print(f"MemoryKernel: Storing sensing interface content: {content}")
                self._store_fact(content, "sensing_interface")
            else:
                print(f"MemoryKernel: Storing content from {message.source_kernel_id.value}: {content}")
                self._store_fact(content, message.source_kernel_id.value)
            
        elif isinstance(message, GazeMessage):
            # Store gaze information
            gaze_info = f"looking_at_screen: {message.looking_at_screen}"
            print(f"MemoryKernel: Storing gaze info from {message.source_kernel_id.value}: {gaze_info}")
            self._store_fact(gaze_info, "gaze_tracking")
            
        else:
            print(f"MemoryKernel: Storing message type {type(message)} from {message.source_kernel_id.value}")
            self._store_fact(str(message), "misc")
        
        # Update metadata
        self._update_metadata()
        
        # Print storage stats
        print(f"MemoryKernel: {self.storage}") 