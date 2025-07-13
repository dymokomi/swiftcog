"""
Memory kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional, Dict, Any, List
import ray
from datetime import datetime
from swiftcog_types import KernelID, KernelMessage, TextMessage, GazeMessage, ConceptCreationRequest, ConversationMessage, GoalCreationRequest
from .base_kernel import BaseKernel
from tools.concept_graph import ConceptGraph, Concept

"""
Memory organization using ConceptGraph:

Working memory:
- Concepts with high activation levels
- Recent conversation messages as conversation concepts
- Active context concepts
- Current percepts as percept concepts

Long term memory:
- All concepts in the graph with low activation
- People as person concepts
- Objects as object concepts
- Historical conversation messages as conversation concepts
- Session contexts as context concepts
"""

@ray.remote
class MemoryKernel(BaseKernel):
    """Memory kernel implementation using ConceptGraph storage."""
    
    def __init__(self, custom_handler: Optional[Callable] = None, storage_path: str = "concept_graph.json"):
        super().__init__(KernelID.MEMORY, custom_handler)
        self.concept_graph = ConceptGraph(storage_path)
        self._current_session_id = None
        self._initialize_memory_structure()
    
    def _initialize_memory_structure(self) -> None:
        """Initialize the memory structure with basic concepts."""
        # Create a session context for this run
        session_description = f"Session started at {datetime.now().isoformat()}"
        self._current_session_id = self.concept_graph.add_context(
            description=session_description,
            time_info=datetime.now().isoformat()
        )
        
        print(f"MemoryKernel: Session context created with ID: {self._current_session_id}")
    
    # ----- Public methods for other kernels to access ConceptGraph -----
    
    def check_percept_exists(self, person_id: str) -> bool:
        """Check if a person percept already exists in the concept graph."""
        results = self.concept_graph.search_by_label(
            f"person percept {person_id}", 
            k=10,
            filter_fn=lambda c: c.ctype == "percept" and c.data.get("person_id") == person_id
        )
        return len(results) > 0
    
    def update_person_percept_context(self, person_id: str) -> bool:
        """Update an existing person percept to link to the current session context."""
        # Find the existing person percept
        results = self.concept_graph.search_by_label(
            f"person percept {person_id}", 
            k=10,
            filter_fn=lambda c: c.ctype == "percept" and c.data.get("person_id") == person_id
        )
        
        if not results:
            print(f"MemoryKernel: No existing percept found for person {person_id}")
            return False
            
        # Get the first (most relevant) percept
        percept_id, score, percept = results[0]
        
        # Remove old context links
        context_relations = []
        for _, target, data in self.concept_graph.G.edges(percept_id, data=True):
            if data.get("relation") == "inContext":
                context_relations.append((percept_id, target))
        
        # Remove old context relations
        for source, target in context_relations:
            self.concept_graph.G.remove_edge(source, target)
            print(f"MemoryKernel: Removed old context link from {source} to {target}")
        
        # Add new context link to current session
        if self._current_session_id:
            self.concept_graph.relate(percept_id, self._current_session_id, "inContext")
            print(f"MemoryKernel: Updated percept {percept_id} to link to current session context {self._current_session_id}")
        
        # Reactivate the percept since it's current
        self.concept_graph.activate(percept_id, strength=1.0)
        print(f"MemoryKernel: Reactivated percept {percept_id} for person {person_id}")
        
        return True
    
    def get_concepts_by_type(self, ctype: str) -> List[Dict[str, Any]]:
        """Get all concepts of a specific type (for other kernels)."""
        concepts = self.concept_graph.get_concepts_by_type(ctype)
        # Convert to serializable format
        return [
            {
                "id": c.id,
                "ctype": c.ctype,
                "label": c.label,
                "data": c.data,
                "activation": c.activation,
                "meta": c.meta
            }
            for c in concepts
        ]
    
    def search_concepts(self, query: str, limit: int = 5, concept_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search concepts using text matching (for other kernels)."""
        filter_fn = None
        if concept_type:
            filter_fn = lambda c: c.ctype == concept_type
        
        results = self.concept_graph.search_by_label(query, k=limit, filter_fn=filter_fn)
        
        formatted_results = []
        for concept_id, score, concept in results:
            result = {
                "id": concept_id,
                "type": concept.ctype,
                "label": concept.label,
                "data": concept.data,
                "score": score,
                "activation": concept.activation,
                "created": concept.meta.get("created", 0)
            }
            formatted_results.append(result)
        
        return formatted_results
    
    def update_concept(self, cid: str, updates: Dict[str, Any]) -> bool:
        """Update a concept's fields (for other kernels)."""
        return self.concept_graph.update_concept(cid, updates)
    
    def get_concept_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the concept graph (for other kernels)."""
        all_concepts = []
        for nid, data in self.concept_graph.G.nodes(data=True):
            all_concepts.append(data["obj"])
        
        concepts_by_type = {}
        active_count = 0
        
        for concept in all_concepts:
            ctype = concept.ctype
            if ctype not in concepts_by_type:
                concepts_by_type[ctype] = 0
            concepts_by_type[ctype] += 1
            
            if concept.activation > 0:
                active_count += 1
        
        return {
            "total_concepts": len(all_concepts),
            "total_relations": len(list(self.concept_graph.G.edges())),
            "concepts_by_type": concepts_by_type,
            "active_concepts": active_count
        }
    
    def store_conversation_message(self, speaker: str, content: str) -> str:
        """Store a conversation message in the concept graph (for other kernels)."""
        # Create a conversation concept
        conversation_concept = Concept(
            ctype="conversation",
            label=f"[{speaker}] {content[:50]}..." if len(content) > 50 else f"[{speaker}] {content}",
            data={
                "speaker": speaker,
                "content": content,
                "type": "conversation"
            }
        )
        
        self.concept_graph.add(conversation_concept)
        
        # Link to current session context
        if self._current_session_id:
            self.concept_graph.relate(conversation_concept.id, self._current_session_id, "inContext")
        
        # Activate the concept
        self.concept_graph.activate(conversation_concept.id, strength=1.0)
        
        print(f"MemoryKernel: Stored conversation message from {speaker}: {content[:100]}...")
        return conversation_concept.id
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history from the current session context (for other kernels)."""
        if not self._current_session_id:
            return []
        
        # Get all conversation concepts linked to current context
        conversation_concepts = []
        
        # Find all concepts related to current session
        for source, target, data in self.concept_graph.G.edges(data=True):
            concept_node = None
            
            # Check if source is linked to current session
            if target == self._current_session_id and data.get("relation") == "inContext":
                concept_node = source
            # Check if target is linked to current session  
            elif source == self._current_session_id and data.get("relation") == "inContext":
                concept_node = target
            
            if concept_node:
                # Get the concept
                concept_data = self.concept_graph.G.nodes[concept_node].get("obj")
                if concept_data and concept_data.ctype == "conversation":
                    conversation_concepts.append(concept_data)
        
        # Sort by creation time
        conversation_concepts.sort(key=lambda c: c.meta.get("created", 0))
        
        # Take the most recent ones
        recent_conversations = conversation_concepts[-limit:] if limit > 0 else conversation_concepts
        
        # Format for return
        formatted_history = []
        for concept in recent_conversations:
            formatted_history.append({
                "id": concept.id,
                "speaker": concept.data.get("speaker", "unknown"),
                "content": concept.data.get("content", ""),
                "timestamp": concept.meta.get("created", 0)
            })
        
        return formatted_history
    
    # ----- Internal methods -----
    
    def _handle_concept_creation_request(self, request: ConceptCreationRequest) -> None:
        """Handle request to create a new concept."""
        concept_type = request.concept_type
        concept_data = request.concept_data
        
        print(f"MemoryKernel: Creating concept of type '{concept_type}' with data: {concept_data}")
        
        if concept_type == "percept":
            # Create a percept concept
            percept_label = concept_data.get("description", f"Percept {concept_data.get('person_id', 'unknown')}")
            
            percept_concept = Concept(
                ctype="percept",
                label=percept_label,
                data=concept_data
            )
            
            self.concept_graph.add(percept_concept)
            print(f"MemoryKernel: Created percept concept with ID: {percept_concept.id}")
            
            # Link the percept to the current session context
            if self._current_session_id:
                self.concept_graph.relate(percept_concept.id, self._current_session_id, "inContext")
                print(f"MemoryKernel: Linked percept {percept_concept.id} to session context {self._current_session_id}")
            
            # Activate the percept concept since it's current
            self.concept_graph.activate(percept_concept.id, strength=1.0)
            
        elif concept_type == "knowledge":
            # Create a knowledge concept
            knowledge_label = concept_data.get("description", f"Knowledge: {concept_data.get('knowledge_type', 'unknown')}")
            
            knowledge_concept = Concept(
                ctype="knowledge",
                label=knowledge_label,
                data=concept_data
            )
            
            self.concept_graph.add(knowledge_concept)
            print(f"MemoryKernel: Created knowledge concept with ID: {knowledge_concept.id}")
            
            # Link the knowledge to the current session context
            if self._current_session_id:
                self.concept_graph.relate(knowledge_concept.id, self._current_session_id, "inContext")
                print(f"MemoryKernel: Linked knowledge {knowledge_concept.id} to session context {self._current_session_id}")
            
            # If this knowledge is linked to a person percept, create that relationship
            linked_person_percept = concept_data.get("linked_person_percept")
            if linked_person_percept:
                self.concept_graph.relate(knowledge_concept.id, linked_person_percept, "aboutPerson")
                print(f"MemoryKernel: Linked knowledge {knowledge_concept.id} to person percept {linked_person_percept}")
            
            # Activate the knowledge concept since it's current
            self.concept_graph.activate(knowledge_concept.id, strength=1.0)
            
        else:
            print(f"MemoryKernel: Unknown concept type: {concept_type}")
    
    def _handle_goal_creation_request(self, request: GoalCreationRequest) -> None:
        """Handle request to create a new goal."""
        print(f"MemoryKernel: Creating goal '{request.description}' with status '{request.status}'")
        
        # Use the concept graph's add_goal method
        goal_id = self.concept_graph.add_goal(
            description=request.description,
            status=request.status,
            context_id=request.context_id or self._current_session_id
        )
        
        print(f"MemoryKernel: Created goal with ID: {goal_id}")
        
        # Activate the goal concept since it's current
        self.concept_graph.activate(goal_id, strength=1.0)
    
    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memory using text matching."""
        results = self.concept_graph.search_by_label(query, k=limit)
        
        formatted_results = []
        for concept_id, score, concept in results:
            result = {
                "id": concept_id,
                "type": concept.ctype,
                "label": concept.label,
                "data": concept.data,
                "score": score,
                "activation": concept.activation,
                "created": concept.meta.get("created", 0)
            }
            formatted_results.append(result)
        
        return formatted_results
    
    def decay_memory(self, decay_rate: float = 0.1) -> None:
        """Decay activation for all concepts."""
        self.concept_graph.decay_activation(decay_rate)
        print(f"MemoryKernel: Applied decay rate {decay_rate} to all concepts")
    
    async def receive(self, message: KernelMessage) -> None:
        """Process and store memory-related information."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Handle ConceptCreationRequest messages
        if isinstance(message, ConceptCreationRequest):
            print(f"[{timestamp}] MemoryKernel: Processing ConceptCreationRequest")
            self._handle_concept_creation_request(message)
            print(f"MemoryKernel: ConceptGraph has {self.concept_graph.size()} concepts")
            return
        
        # Handle GoalCreationRequest messages
        if isinstance(message, GoalCreationRequest):
            print(f"[{timestamp}] MemoryKernel: Processing GoalCreationRequest")
            self._handle_goal_creation_request(message)
            print(f"MemoryKernel: ConceptGraph has {self.concept_graph.size()} concepts")
            return
        
        # Handle ConversationMessage messages
        if isinstance(message, ConversationMessage):
            print(f"[{timestamp}] MemoryKernel: Processing ConversationMessage from {message.speaker}")
            if message.store_in_memory:
                self.store_conversation_message(message.speaker, message.content)
                print(f"MemoryKernel: ConceptGraph has {self.concept_graph.size()} concepts")
            return
        
        # For any other message types, just log and ignore
        print(f"[{timestamp}] MemoryKernel: Ignoring unsupported message type: {type(message)} from {message.source_kernel_id.value}")
        
        # Periodically decay memory activation
        import random
        if random.random() < 0.1:  # 10% chance to decay on each message
            self.decay_memory(decay_rate=0.05) 