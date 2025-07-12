"""
Vector recognition system for gaze feature vectors.
Stores and recognizes 768-dimensional feature vectors with diversity management.
"""
import numpy as np
import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import uuid


@dataclass
class VectorGroup:
    """Represents a group of vectors with the same ID."""
    id: str
    vectors: List[np.ndarray]
    
    def __post_init__(self):
        """Ensure vectors are numpy arrays."""
        self.vectors = [np.array(v) if not isinstance(v, np.ndarray) else v for v in self.vectors]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'vectors': [vector.tolist() for vector in self.vectors]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VectorGroup':
        """Create VectorGroup from dictionary."""
        return cls(
            id=data['id'],
            vectors=[np.array(v) for v in data['vectors']]
        )


class VectorRecognition:
    """
    Vector recognition system that stores and matches 768-dimensional feature vectors.
    
    Features:
    - Distance-based matching with configurable threshold
    - Stores up to 10 diverse vectors per ID
    - Maximizes diversity when storing multiple vectors
    - Persistent storage to JSON file
    """
    
    def __init__(self, 
                 storage_file: str = "vector_storage.json",
                 threshold: float = 0.85,
                 max_vectors_per_id: int = 10,
                 expected_dimensions: int = 768):
        """
        Initialize the vector recognition system.
        
        Args:
            storage_file: Path to the JSON storage file
            threshold: Cosine similarity threshold for matching (0.0 to 1.0)
            max_vectors_per_id: Maximum number of vectors to store per ID
            expected_dimensions: Expected dimensionality of input vectors
        """
        self.storage_file = storage_file
        self.threshold = threshold
        self.max_vectors_per_id = max_vectors_per_id
        self.expected_dimensions = expected_dimensions
        
        # Dictionary mapping ID to VectorGroup
        self.vector_groups: Dict[str, VectorGroup] = {}
        
        # Load existing vectors if file exists
        self._load_vectors()
    
    def _load_vectors(self) -> None:
        """Load vectors from JSON storage file."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                
                # Handle different data formats
                if isinstance(data, dict):
                    if 'vector_groups' in data:
                        # New format with metadata
                        groups_data = data['vector_groups']
                        self.vector_groups = {
                            group_id: VectorGroup.from_dict(group_data)
                            for group_id, group_data in groups_data.items()
                        }
                    else:
                        # Legacy format - direct groups
                        self.vector_groups = {
                            group_id: VectorGroup.from_dict(group_data)
                            for group_id, group_data in data.items()
                        }
                
                print(f"VectorRecognition: Loaded {len(self.vector_groups)} vector groups from {self.storage_file}")
                
            except Exception as e:
                print(f"VectorRecognition: Error loading vectors: {e}")
                self.vector_groups = {}
        else:
            print(f"VectorRecognition: No existing storage file found, starting fresh")
            self.vector_groups = {}
    
    def _save_vectors(self) -> None:
        """Save vectors to JSON storage file."""
        try:
            # Create a structured JSON format
            data = {
                'metadata': {
                    'threshold': self.threshold,
                    'max_vectors_per_id': self.max_vectors_per_id,
                    'expected_dimensions': self.expected_dimensions,
                    'total_groups': len(self.vector_groups),
                    'total_vectors': sum(len(group.vectors) for group in self.vector_groups.values())
                },
                'vector_groups': {
                    group_id: group.to_dict()
                    for group_id, group in self.vector_groups.items()
                }
            }
            
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"VectorRecognition: Saved {len(self.vector_groups)} vector groups to {self.storage_file}")
            
        except Exception as e:
            print(f"VectorRecognition: Error saving vectors: {e}")
    
    def _cosine_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        # Normalize vectors
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return np.dot(vector1, vector2) / (norm1 * norm2)
    
    def _find_best_match(self, query_vector: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Find the best matching vector group for the query vector.
        
        Returns:
            Tuple of (best_id, best_similarity) or (None, 0.0) if no match above threshold
        """
        best_similarity = 0.0
        best_id = None
        
        for group_id, group in self.vector_groups.items():
            # Calculate similarity with each vector in the group
            for vector in group.vectors:
                similarity = self._cosine_similarity(query_vector, vector)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_id = group_id
        
        # Return match only if above threshold
        if best_similarity >= self.threshold:
            return best_id, best_similarity
        else:
            return None, best_similarity
    
    def _calculate_diversity_score(self, new_vector: np.ndarray, existing_vectors: List[np.ndarray]) -> float:
        """
        Calculate diversity score for a new vector against existing vectors.
        Higher score means more diverse (further from existing vectors).
        """
        if not existing_vectors:
            return 1.0
            
        # Calculate minimum distance to any existing vector
        min_similarity = float('inf')
        for existing_vector in existing_vectors:
            similarity = self._cosine_similarity(new_vector, existing_vector)
            min_similarity = min(min_similarity, similarity)
        
        # Convert similarity to distance (diversity score)
        return 1.0 - min_similarity
    
    def _add_vector_to_group(self, group: VectorGroup, new_vector: np.ndarray) -> None:
        """
        Add a new vector to a group, maintaining diversity and size limits.
        """
        if len(group.vectors) < self.max_vectors_per_id:
            # Room for more vectors, just add it
            group.vectors.append(new_vector.copy())
        else:
            # Need to replace a vector to maintain diversity
            # Find the vector that, when replaced, maximizes overall diversity
            best_replacement_idx = -1
            best_diversity_gain = -1.0
            
            for i, existing_vector in enumerate(group.vectors):
                # Calculate diversity if we replace this vector
                temp_vectors = group.vectors.copy()
                temp_vectors[i] = new_vector
                
                # Calculate total diversity of this configuration
                total_diversity = 0.0
                for j, vec1 in enumerate(temp_vectors):
                    for k, vec2 in enumerate(temp_vectors):
                        if j != k:
                            total_diversity += 1.0 - self._cosine_similarity(vec1, vec2)
                
                if total_diversity > best_diversity_gain:
                    best_diversity_gain = total_diversity
                    best_replacement_idx = i
            
            # Replace the vector that gives the best diversity
            if best_replacement_idx >= 0:
                group.vectors[best_replacement_idx] = new_vector.copy()
    
    def recognize_vector(self, feature_vector: List[float]) -> str:
        """
        Recognize a feature vector and return its ID.
        
        Args:
            feature_vector: List of floats representing the feature vector
            
        Returns:
            String ID of the recognized or newly created vector group
        """
        # Convert to numpy array and validate
        vector = np.array(feature_vector)
        
        if len(vector) != self.expected_dimensions:
            raise ValueError(f"Expected {self.expected_dimensions} dimensions, got {len(vector)}")
        
        # Find best match
        best_id, best_similarity = self._find_best_match(vector)
        
        if best_id is not None:
            # Found a match, add this vector to the group for diversity
            self._add_vector_to_group(self.vector_groups[best_id], vector)
            print(f"VectorRecognition: Matched existing ID {best_id} with similarity {best_similarity:.4f}")
            
            # Save updated vectors
            self._save_vectors()
            return best_id
        else:
            # No match found, create new group
            new_id = str(uuid.uuid4())
            self.vector_groups[new_id] = VectorGroup(id=new_id, vectors=[vector.copy()])
            
            print(f"VectorRecognition: Created new ID {new_id} (best similarity was {best_similarity:.4f}, threshold is {self.threshold:.4f})")
            
            # Save vectors
            self._save_vectors()
            return new_id
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector storage."""
        total_vectors = sum(len(group.vectors) for group in self.vector_groups.values())
        
        return {
            'total_groups': len(self.vector_groups),
            'total_vectors': total_vectors,
            'threshold': self.threshold,
            'max_vectors_per_id': self.max_vectors_per_id,
            'expected_dimensions': self.expected_dimensions
        }
    
    def list_groups(self) -> List[Dict]:
        """List all vector groups with their statistics."""
        groups = []
        for group_id, group in self.vector_groups.items():
            groups.append({
                'id': group_id,
                'vector_count': len(group.vectors),
                'avg_similarity': self._calculate_avg_internal_similarity(group.vectors)
            })
        return groups
    
    def _calculate_avg_internal_similarity(self, vectors: List[np.ndarray]) -> float:
        """Calculate average similarity between vectors in a group."""
        if len(vectors) < 2:
            return 1.0
            
        total_similarity = 0.0
        count = 0
        
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                total_similarity += self._cosine_similarity(vectors[i], vectors[j])
                count += 1
        
        return total_similarity / count if count > 0 else 1.0
