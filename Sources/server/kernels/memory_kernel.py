"""
Memory kernel implementation for the SwiftCog Python server.
"""
from typing import Callable, Optional, Dict, Any, List
import ray
from datetime import datetime
from swiftcog_types import KernelID, KernelMessage, TextMessage, GazeMessage, ConceptCreationRequest, ConversationMessage
from .base_kernel import BaseKernel
from tools.concept_graph import ConceptGraph, Concept

"""
Memory organization using ConceptGraph:

Working memory:
- Concepts with high activation levels
- Recent dialog history as note concepts
- Current goals as goal concepts
- Active context concepts

Long term memory:
- All concepts in the graph with low activation
- Facts as fact concepts
- People as person concepts
- Objects as object concepts
- Conversation summaries as note concepts
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
            
        else:
            print(f"MemoryKernel: Unknown concept type: {concept_type}")
    
    def _store_dialog_message(self, message: KernelMessage) -> str:
        """Store a message as a note concept in the graph."""
        # Create message content string
        content = None
        if isinstance(message, TextMessage):
            content = message.content
        elif isinstance(message, GazeMessage):
            content = f"looking_at_screen: {message.looking_at_screen}"
        else:
            content = str(message)
        
        # Create a note concept for the dialog message
        note_text = f"[{message.source_kernel_id.value}] {content}"
        note_id = self.concept_graph.add_note(note_text)
        
        # Link to current session context
        if self._current_session_id:
            self.concept_graph.relate(note_id, self._current_session_id, "inContext")
        
        # Activate the concept
        self.concept_graph.activate(note_id, strength=1.0)
        
        return note_id
    
    def _store_fact(self, fact: str, category: str = "general", source_kernel: str = "unknown") -> str:
        """Store a fact as a fact concept."""
        # Create a fact concept
        fact_id = self.concept_graph.add_fact(
            subj="system",  # Could be more specific
            pred=category,
            obj_or_val=fact
        )
        
        # Link to current session context
        if self._current_session_id:
            self.concept_graph.relate(fact_id, self._current_session_id, "inContext")
        
        # Create a source annotation
        source_note = f"Fact from {source_kernel}: {fact}"
        source_id = self.concept_graph.add_note(source_note)
        self.concept_graph.relate(fact_id, source_id, "source")
        
        return fact_id
    
    def set_current_speaker(self, speaker: str) -> str:
        """Set the current speaker by creating/updating a person concept."""
        # Try to find existing person concept
        people = self.concept_graph.get_concepts_by_type("person")
        person_id = None
        
        for person in people:
            if person.data.get("name") == speaker:
                person_id = person.id
                break
        
        if not person_id:
            # Create new person concept
            person_id = self.concept_graph.add_person(speaker)
        
        # Activate the person concept
        self.concept_graph.activate(person_id, strength=1.0)
        
        # Create a context note about current speaker
        speaker_note = f"Current speaker: {speaker}"
        note_id = self.concept_graph.add_note(speaker_note)
        
        if self._current_session_id:
            self.concept_graph.relate(note_id, self._current_session_id, "inContext")
        
        print(f"MemoryKernel: Current speaker set to: {speaker} (ID: {person_id})")
        return person_id
    
    def add_goal(self, goal: str, is_long_term: bool = False) -> str:
        """Add a goal concept to memory."""
        status = "active"
        context_id = None if is_long_term else self._current_session_id
        
        goal_id = self.concept_graph.add_goal(
            description=goal,
            status=status,
            context_id=context_id
        )
        
        # Activate the goal
        activation_strength = 0.5 if is_long_term else 1.0
        self.concept_graph.activate(goal_id, strength=activation_strength)
        
        goal_type = "long-term" if is_long_term else "current"
        print(f"MemoryKernel: Added {goal_type} goal: {goal} (ID: {goal_id})")
        return goal_id
    
    def get_recent_context(self) -> Dict[str, Any]:
        """Get recent context for other kernels."""
        # Get active concepts
        active_concepts = self.concept_graph.get_active_concepts(threshold=0.1)
        
        # Get recent messages (notes with high activation)
        recent_messages = []
        current_speaker = None
        active_goals = []
        
        for concept in active_concepts:
            if concept.ctype == "note":
                # Extract message info
                if "[" in concept.label and "]" in concept.label:
                    recent_messages.append({
                        "content": concept.data.get("text", ""),
                        "timestamp": concept.meta.get("created", 0),
                        "concept_id": concept.id
                    })
            elif concept.ctype == "person":
                current_speaker = concept.data.get("name")
            elif concept.ctype == "goal" and concept.data.get("status") == "active":
                active_goals.append({
                    "goal": concept.data.get("description", ""),
                    "timestamp": concept.meta.get("created", 0),
                    "concept_id": concept.id
                })
        
        # Sort by timestamp and get most recent
        recent_messages.sort(key=lambda x: x["timestamp"], reverse=True)
        active_goals.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "current_speaker": current_speaker,
            "recent_messages": recent_messages[:3],  # Last 3 messages
            "active_goals": active_goals[:5]  # Top 5 goals
        }
    
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
    
    def get_facts_about(self, subject: str) -> List[Dict[str, Any]]:
        """Get facts related to a subject."""
        facts = []
        
        # Search for facts mentioning the subject
        results = self.concept_graph.search_by_label(subject, k=10, filter_fn=lambda c: c.ctype == "fact")
        
        for concept_id, score, concept in results:
            fact_data = {
                "id": concept_id,
                "subject": concept.data.get("subject", ""),
                "predicate": concept.data.get("predicate", ""),
                "object": concept.data.get("object"),
                "value": concept.data.get("value"),
                "confidence": concept.meta.get("confidence", 1.0),
                "created": concept.meta.get("created", 0)
            }
            facts.append(fact_data)
        
        return facts
    
    def decay_memory(self, decay_rate: float = 0.1) -> None:
        """Decay activation for all concepts."""
        self.concept_graph.decay_activation(decay_rate)
        print(f"MemoryKernel: Applied decay rate {decay_rate} to all concepts")
    
    async def receive(self, message: KernelMessage) -> None:
        """Process and store memory-related information."""
        
        # Handle ConceptCreationRequest messages
        if isinstance(message, ConceptCreationRequest):
            self._handle_concept_creation_request(message)
            print(f"MemoryKernel: ConceptGraph has {self.concept_graph.size()} concepts")
            return
        
        # Handle ConversationMessage messages
        if isinstance(message, ConversationMessage):
            if message.store_in_memory:
                self.store_conversation_message(message.speaker, message.content)
                print(f"MemoryKernel: ConceptGraph has {self.concept_graph.size()} concepts")
            return
        
        # Store the message as a note concept
        note_id = self._store_dialog_message(message)
        
        # Process different message types
        if isinstance(message, TextMessage):
            content = message.content
            
            # Store as fact based on source kernel
            if message.source_kernel_id == KernelID.LEARNING:
                print(f"MemoryKernel: Storing learning content: {content}")
                fact_id = self._store_fact(content, "learning", "learning_kernel")
                self.concept_graph.relate(note_id, fact_id, "generates")
                
            elif message.source_kernel_id == KernelID.SENSING:
                print(f"MemoryKernel: Storing sensing content: {content}")
                fact_id = self._store_fact(content, "sensing", "sensing_kernel")
                self.concept_graph.relate(note_id, fact_id, "generates")
                
            elif message.source_kernel_id == KernelID.EXECUTIVE:
                print(f"MemoryKernel: Storing executive content: {content}")
                # Executive messages might contain goals or decisions
                if "goal" in content.lower():
                    goal_id = self.add_goal(content)
                    self.concept_graph.relate(note_id, goal_id, "generates")
                else:
                    fact_id = self._store_fact(content, "executive", "executive_kernel")
                    self.concept_graph.relate(note_id, fact_id, "generates")
                    
            elif message.source_kernel_id == KernelID.SENSING_INTERFACE:
                print(f"MemoryKernel: Storing sensing interface content: {content}")
                fact_id = self._store_fact(content, "sensing_interface", "sensing_interface")
                self.concept_graph.relate(note_id, fact_id, "generates")
                
            else:
                print(f"MemoryKernel: Storing content from {message.source_kernel_id.value}: {content}")
                fact_id = self._store_fact(content, message.source_kernel_id.value, message.source_kernel_id.value)
                self.concept_graph.relate(note_id, fact_id, "generates")
            
        elif isinstance(message, GazeMessage):
            # Store gaze information as a fact
            gaze_info = f"looking_at_screen: {message.looking_at_screen}"
            print(f"MemoryKernel: Storing gaze info from {message.source_kernel_id.value}: {gaze_info}")
            fact_id = self._store_fact(gaze_info, "gaze_tracking", message.source_kernel_id.value)
            self.concept_graph.relate(note_id, fact_id, "generates")
            
        else:
            print(f"MemoryKernel: Storing message type {type(message)} from {message.source_kernel_id.value}")
            fact_id = self._store_fact(str(message), "misc", message.source_kernel_id.value)
            self.concept_graph.relate(note_id, fact_id, "generates")
        
        # Print storage stats
        print(f"MemoryKernel: ConceptGraph has {self.concept_graph.size()} concepts")
        
        # Periodically decay memory activation
        import random
        if random.random() < 0.1:  # 10% chance to decay on each message
            self.decay_memory(decay_rate=0.05) 