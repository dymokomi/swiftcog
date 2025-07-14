"""
Concept Graph implementation for SwiftCog.
A graph-based memory system that stores facts, goals, contexts, people, objects, and free-form notes.
"""
import json
import os
import threading
from dataclasses import dataclass, field, asdict
from uuid import uuid4
from time import time
from typing import Any, Dict, Optional, List, Callable, Union
from pathlib import Path

try:
    import networkx as nx
except ImportError:
    print("NetworkX not installed. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "networkx"])
    import networkx as nx


@dataclass
class Concept:
    """A unified concept node that can represent any type of information."""
    id: str = field(default_factory=lambda: str(uuid4()))
    ctype: str = "concept"  # person | object | goal | context | percept | conversation
    label: str = ""  # short human-readable name
    data: dict = field(default_factory=dict)  # numeric/text payload
    activation: float = 0.0  # working-memory strength
    meta: dict = field(default_factory=lambda: {
        "created": time(), 
        "updated": time(),
        "source": "internal", 
        "surprise": 0.0, 
        "confidence": 1.0, 
        "boredom": 0.0
    })
    
    def to_dict(self) -> dict:
        """Convert concept to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Concept':
        """Create concept from dictionary."""
        return cls(**data)


class ConceptGraph:
    """A graph-based memory system using concepts and relations."""
    
    def __init__(self, storage_path: str = "concept_graph.json"):
        """Initialize the concept graph."""
        self.storage_path = Path(storage_path)
        self.G = nx.MultiDiGraph()  # allow multi-edges for different predicates
        self._lock = threading.RLock()
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """Load concept graph from disk if the file exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load nodes
                for node_data in data.get("nodes", []):
                    concept = Concept.from_dict(node_data)
                    self.G.add_node(concept.id, obj=concept)
                
                # Load edges
                for edge_data in data.get("edges", []):
                    self.G.add_edge(
                        edge_data["source"],
                        edge_data["target"],
                        key=edge_data["relation"],
                        **edge_data.get("attributes", {})
                    )
                
                print(f"ConceptGraph: Loaded {len(self.G.nodes)} concepts and {len(self.G.edges)} relations from {self.storage_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"ConceptGraph: Error loading from {self.storage_path}: {e}")
                self.G = nx.MultiDiGraph()
        else:
            print(f"ConceptGraph: No existing storage found at {self.storage_path}, starting fresh")
            self.G = nx.MultiDiGraph()
    
    def _save_to_disk(self) -> None:
        """Save concept graph to disk."""
        try:
            # Create directory if it doesn't exist
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serialize nodes
            nodes_data = []
            for node_id, node_data in self.G.nodes(data=True):
                if "obj" not in node_data:
                    print(f"Warning: Node {node_id} missing 'obj' key. Data: {node_data}")
                    continue
                concept = node_data["obj"]
                nodes_data.append(concept.to_dict())
            
            # Serialize edges
            edges_data = []
            for source, target, key, attr in self.G.edges(keys=True, data=True):
                edges_data.append({
                    "source": source,
                    "target": target,
                    "relation": key,
                    "attributes": attr
                })
            
            data = {
                "nodes": nodes_data,
                "edges": edges_data
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"ConceptGraph: Saved {len(nodes_data)} concepts and {len(edges_data)} relations to {self.storage_path}")
        except IOError as e:
            print(f"ConceptGraph: Error saving to {self.storage_path}: {e}")
    
    # ----- CRUD operations -----
    def add(self, concept: Concept) -> None:
        """Add a concept to the graph."""
        with self._lock:
            self.G.add_node(concept.id, obj=concept)
            self._save_to_disk()
    
    def relate(self, src: str, dst: str, rel: str, attrs: Optional[Dict] = None) -> None:
        """Create a relationship between two concepts."""
        with self._lock:
            # Only create relationship if both nodes exist
            if src in self.G and dst in self.G:
                edge_attrs = attrs or {}
                edge_attrs["relation"] = rel
                self.G.add_edge(src, dst, **edge_attrs)
                self._save_to_disk()
            else:
                print(f"Warning: Cannot create relationship {rel} between {src} and {dst} - one or both nodes don't exist")
    
    def get(self, cid: str) -> Optional[Concept]:
        """Get a concept by ID."""
        if cid in self.G:
            return self.G.nodes[cid]["obj"]
        return None
    
    def update_concept(self, cid: str, updates: Dict[str, Any]) -> bool:
        """Update a concept's fields."""
        concept = self.get(cid)
        if concept:
            for key, value in updates.items():
                if hasattr(concept, key):
                    # Direct attribute update
                    setattr(concept, key, value)
                else:
                    # Store in data dict for non-direct attributes
                    concept.data[key] = value
            concept.meta["updated"] = time()
            self._save_to_disk()
            return True
        return False
    
    def delete_concept(self, cid: str) -> bool:
        """Delete a concept and all its relationships."""
        with self._lock:
            if cid in self.G:
                self.G.remove_node(cid)
                self._save_to_disk()
                return True
            return False
    
    # ----- Typed helpers -----
    def add_person(self, name: str, profile: Optional[Dict] = None) -> str:
        """Add a person concept."""
        person = Concept(
            ctype="person",
            label=name,
            data={"name": name, "profile": profile or {}},
            meta={"source": "input", "created": time(), "updated": time()}
        )
        self.add(person)
        return person.id
    
    def add_object(self, name: str, category: str = "general", props: Optional[Dict] = None) -> str:
        """Add an object concept."""
        obj = Concept(
            ctype="object",
            label=name,
            data={"name": name, "category": category, "props": props or {}},
            meta={"source": "input", "created": time(), "updated": time()}
        )
        self.add(obj)
        return obj.id
    
    def add_context(self, description: str, time_info: Optional[str] = None, location: Optional[str] = None) -> str:
        """Add a context concept."""
        context = Concept(
            ctype="context",
            label=description[:40],
            data={"description": description, "time": time_info, "location": location},
            meta={"source": "input", "created": time(), "updated": time()}
        )
        self.add(context)
        return context.id
    
    def add_goal(self, description: str, status: str = "open", context_id: Optional[str] = None) -> str:
        """Add a goal concept."""
        goal = Concept(
            ctype="goal",
            label=description[:40],
            data={"description": description, "status": status},
            meta={"source": "input", "created": time(), "updated": time()}
        )
        self.add(goal)
        if context_id:
            self.relate(goal.id, context_id, "inContext")
        return goal.id
    

    
    # ----- Search and retrieval -----
    def search_by_label(self, query_text: str, k: int = 5, filter_fn: Optional[Callable] = None) -> List[tuple]:
        """Find concepts by label text matching."""
        hits = []
        query_lower = query_text.lower()
        query_words = query_lower.split()
        
        for nid, data in self.G.nodes(data=True):
            c: Concept = data["obj"]
            if filter_fn and not filter_fn(c):
                continue
            
            # Simple text matching on label and key data fields
            score = 0.0
            
            # Check label - exact match gets higher score
            label_lower = c.label.lower()
            if query_lower in label_lower:
                score += 2.0
            else:
                # Check individual words
                for word in query_words:
                    if word in label_lower:
                        score += 0.5
            
            # Check key data fields
            for key, value in c.data.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    if query_lower in value_lower:
                        score += 1.5
                    else:
                        # Check individual words
                        for word in query_words:
                            if word in value_lower:
                                score += 0.3
            
            if score > 0:
                hits.append((nid, score, c))
        
        return sorted(hits, key=lambda t: t[1], reverse=True)[:k]
    
    def get_concepts_by_type(self, ctype: str) -> List[Concept]:
        """Get all concepts of a specific type."""
        concepts = []
        for nid, data in self.G.nodes(data=True):
            concept = data["obj"]
            if concept.ctype == ctype:
                concepts.append(concept)
        return concepts
    
    def get_related_concepts(self, cid: str, relation: Optional[str] = None) -> List[tuple]:
        """Get concepts related to a given concept."""
        if cid not in self.G:
            return []
        
        related = []
        for target in self.G.neighbors(cid):
            for key, attr in self.G[cid][target].items():
                if relation is None or key == relation:
                    concept = self.G.nodes[target]["obj"]
                    related.append((target, key, concept, attr))
        
        return related
    
    # ----- Working memory and metacognition -----
    def activate(self, cid: str, strength: float = 1.0) -> None:
        """Activate a concept in working memory."""
        concept = self.get(cid)
        if concept:
            concept.activation = strength
            concept.meta["updated"] = time()
            self._save_to_disk()
    
    def decay_activation(self, decay_rate: float = 0.1) -> None:
        """Decay activation for all concepts."""
        for nid, data in self.G.nodes(data=True):
            concept = data["obj"]
            concept.activation *= (1 - decay_rate)
            if concept.activation < 0.01:
                concept.activation = 0.0
        self._save_to_disk()
    
    def get_active_concepts(self, threshold: float = 0.1) -> List[Concept]:
        """Get concepts with activation above threshold."""
        active = []
        for nid, data in self.G.nodes(data=True):
            concept = data["obj"]
            if concept.activation >= threshold:
                active.append(concept)
        return sorted(active, key=lambda c: c.activation, reverse=True)
    
    def size(self) -> int:
        """Get the number of concepts in the graph."""
        return len(self.G.nodes)
    
    def __str__(self) -> str:
        """String representation of the concept graph."""
        return f"ConceptGraph({self.storage_path}): {len(self.G.nodes)} concepts, {len(self.G.edges)} relations" 