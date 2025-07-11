"""
Memory storage implementation for persistent memory in SwiftCog.
"""
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path


class MemoryStorage:
    """
    A simple file-based storage system for persistent memory.
    Uses JSON for human-readable storage that can be easily inspected.
    """
    
    def __init__(self, storage_path: str = "memory_storage.json"):
        """
        Initialize the memory storage.
        
        Args:
            storage_path: Path to the JSON file where memory will be stored
        """
        self.storage_path = Path(storage_path)
        self._memory: Dict[str, Any] = {}
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """Load memory data from disk if the file exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self._memory = json.load(f)
                print(f"MemoryStorage: Loaded {len(self._memory)} items from {self.storage_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"MemoryStorage: Error loading from {self.storage_path}: {e}")
                self._memory = {}
        else:
            print(f"MemoryStorage: No existing storage found at {self.storage_path}, starting fresh")
            self._memory = {}
    
    def _save_to_disk(self) -> None:
        """Save memory data to disk."""
        try:
            # Create directory if it doesn't exist
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._memory, f, indent=2, ensure_ascii=False)
            print(f"MemoryStorage: Saved {len(self._memory)} items to {self.storage_path}")
        except IOError as e:
            print(f"MemoryStorage: Error saving to {self.storage_path}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from memory.
        
        Args:
            key: The key to look up
            default: Default value if key doesn't exist
            
        Returns:
            The value associated with the key, or default if not found
        """
        return self._memory.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in memory and save to disk.
        
        Args:
            key: The key to set
            value: The value to store
        """
        self._memory[key] = value
        self._save_to_disk()
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Update memory with multiple key-value pairs and save to disk.
        
        Args:
            data: Dictionary of key-value pairs to update
        """
        self._memory.update(data)
        self._save_to_disk()
    
    def append_to_list(self, key: str, value: Any) -> None:
        """
        Append a value to a list in memory. Creates the list if it doesn't exist.
        
        Args:
            key: The key for the list
            value: The value to append
        """
        if key not in self._memory:
            self._memory[key] = []
        elif not isinstance(self._memory[key], list):
            # If the key exists but isn't a list, convert it to a list
            self._memory[key] = [self._memory[key]]
        
        self._memory[key].append(value)
        self._save_to_disk()
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all memory data.
        
        Returns:
            A copy of all memory data
        """
        return self._memory.copy()
    
    def clear(self) -> None:
        """Clear all memory data and save to disk."""
        self._memory.clear()
        self._save_to_disk()
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from memory and save to disk.
        
        Args:
            key: The key to delete
            
        Returns:
            True if the key was deleted, False if it didn't exist
        """
        if key in self._memory:
            del self._memory[key]
            self._save_to_disk()
            return True
        return False
    
    def keys(self) -> Dict[str, Any].keys:
        """Get all keys in memory."""
        return self._memory.keys()
    
    def size(self) -> int:
        """Get the number of items in memory."""
        return len(self._memory)
    
    def __contains__(self, key: str) -> bool:
        """Check if a key exists in memory."""
        return key in self._memory
    
    def __str__(self) -> str:
        """String representation of the storage."""
        return f"MemoryStorage({self.storage_path}): {len(self._memory)} items" 