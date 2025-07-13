"""
Learning kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional
import ray
from swiftcog_types import KernelID, KernelMessage, TextMessage, PersonPresenceMessage, ConceptCreationRequest, ConversationMessage
from .base_kernel import BaseKernel


@ray.remote
class LearningKernel(BaseKernel):
    """Learning kernel implementation matching the Swift version."""
    
    def __init__(self, custom_handler: Optional[Callable] = None):
        super().__init__(KernelID.LEARNING, custom_handler)
    
    async def _person_percept_exists(self, person_id: str) -> bool:
        """Check if a person percept already exists by querying MemoryKernel."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            exists = await memory_kernel.check_percept_exists.remote(person_id)
            return exists
        except ValueError:
            print("Error: MemoryKernel not found")
            return False
    
    async def _request_person_percept_creation(self, person_id: str) -> None:
        """Request creation of a new person percept concept."""
        concept_data = {
            "person_id": person_id,
            "percept_type": "person_presence",
            "description": f"Person {person_id} detected"
        }
        
        request = ConceptCreationRequest(
            source_kernel_id=KernelID.LEARNING,
            concept_type="percept",
            concept_data=concept_data
        )
        
        # Send request to MemoryKernel
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            await memory_kernel.receive.remote(request)
            print(f"LearningKernel: Requested creation of person percept for {person_id}")
        except ValueError:
            print("Error: MemoryKernel not found")
    
    async def _update_person_percept_context(self, person_id: str) -> None:
        """Update an existing person percept to link to current context."""
        try:
            memory_kernel = ray.get_actor("MemoryKernel")
            updated = await memory_kernel.update_person_percept_context.remote(person_id)
            if updated:
                print(f"LearningKernel: Updated context for existing person percept {person_id}")
            else:
                print(f"LearningKernel: Failed to update context for person percept {person_id}")
        except ValueError:
            print("Error: MemoryKernel not found")
    
    async def receive(self, message: KernelMessage) -> None:
        """Default handler that processes learning and forwards directly to Memory."""
        if isinstance(message, TextMessage):
            content = message.content
            print(f"LearningKernel: Learning from {content}")
            
            # Hardcoded connection: Learning -> Memory
            try:
                # Create a new TextMessage with LearningKernel as the source
                forwarded_message = TextMessage(
                    source_kernel_id=KernelID.LEARNING,
                    content=content
                )
                
                memory_kernel = ray.get_actor("MemoryKernel")
                await memory_kernel.receive.remote(forwarded_message)
                print("LearningKernel -> MemoryKernel")
            except ValueError:
                print("Error: MemoryKernel not found")
                
        elif isinstance(message, PersonPresenceMessage):
            print(f"LearningKernel: Processing person presence - present: {message.is_present}, person_id: {message.person_id}")
            
            # Only process if person is present and we have a person_id
            if message.is_present and message.person_id:
                # Check if person percept already exists via MemoryKernel
                if not await self._person_percept_exists(message.person_id):
                    print(f"LearningKernel: Person percept for {message.person_id} not found, requesting creation")
                    await self._request_person_percept_creation(message.person_id)
                else:
                    print(f"LearningKernel: Person percept for {message.person_id} already exists, updating context")
                    await self._update_person_percept_context(message.person_id)
            else:
                print("LearningKernel: Person not present or no person_id provided")
                
        elif isinstance(message, ConversationMessage):
            print(f"LearningKernel: Processing conversation message from {message.speaker}: {message.content[:100]}...")
            
            # Forward to MemoryKernel for storage
            try:
                memory_kernel = ray.get_actor("MemoryKernel")
                await memory_kernel.receive.remote(message)
                print("LearningKernel -> MemoryKernel (conversation)")
            except ValueError:
                print("Error: MemoryKernel not found")
                
        else:
            print(f"LearningKernel: Unsupported message type: {type(message)}")
            return 