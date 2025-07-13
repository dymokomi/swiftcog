#!/usr/bin/env python3
"""
Utility script to inspect the ConceptGraph storage file.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

def format_timestamp(timestamp_float):
    """Format timestamp for better readability."""
    try:
        dt = datetime.fromtimestamp(timestamp_float)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return str(timestamp_float)

def print_concept(concept_data, indent=0):
    """Print a concept with proper formatting."""
    prefix = "  " * indent
    ctype = concept_data.get('ctype', 'unknown')
    label = concept_data.get('label', 'No label')
    data = concept_data.get('data', {})
    meta = concept_data.get('meta', {})
    activation = concept_data.get('activation', 0.0)
    
    print(f"{prefix}[{ctype.upper()}] {label}")
    
    # Show creation time
    if 'created' in meta:
        created = format_timestamp(meta['created'])
        print(f"{prefix}  Created: {created}")
    
    # Show activation if > 0
    if activation > 0:
        print(f"{prefix}  Activation: {activation:.3f}")
    
    # Show key data fields
    if data:
        important_fields = ['name', 'description', 'text', 'person_id', 'subject', 'predicate', 'value', 'object']
        for field in important_fields:
            if field in data:
                value = data[field]
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                print(f"{prefix}  {field}: {value}")
    
    print()

def print_relations(edges_data, concepts_by_id, indent=0):
    """Print relationships between concepts."""
    prefix = "  " * indent
    
    # Group relations by type
    relations_by_type = {}
    for edge in edges_data:
        rel_type = edge.get('relation', 'unknown')
        if rel_type not in relations_by_type:
            relations_by_type[rel_type] = []
        relations_by_type[rel_type].append(edge)
    
    for rel_type, edges in relations_by_type.items():
        print(f"{prefix}{rel_type.upper()} relations ({len(edges)}):")
        for edge in edges[:5]:  # Show first 5
            source = edge.get('source', 'unknown')
            target = edge.get('target', 'unknown')
            
            source_label = concepts_by_id.get(source, {}).get('label', source[:8])
            target_label = concepts_by_id.get(target, {}).get('label', target[:8])
            
            print(f"{prefix}  {source_label} -> {target_label}")
        
        if len(edges) > 5:
            print(f"{prefix}  ... and {len(edges) - 5} more")
        print()

def inspect_concept_graph(storage_path="concept_graph.json"):
    """Inspect the ConceptGraph storage file."""
    storage_file = Path(storage_path)
    
    if not storage_file.exists():
        print(f"ConceptGraph storage file not found: {storage_path}")
        print("The file will be created when the memory kernel first runs.")
        return
    
    try:
        with open(storage_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
    except Exception as e:
        print(f"Error reading ConceptGraph storage file: {e}")
        return
    
    print(f"ConceptGraph Inspection - {storage_path}")
    print("=" * 50)
    
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])
    
    print(f"Total concepts: {len(nodes)}")
    print(f"Total relations: {len(edges)}")
    print()
    
    # Create concept lookup for relations
    concepts_by_id = {node.get('id'): node for node in nodes}
    
    # Group concepts by type
    concepts_by_type = {}
    active_concepts = []
    
    for node in nodes:
        ctype = node.get('ctype', 'unknown')
        if ctype not in concepts_by_type:
            concepts_by_type[ctype] = []
        concepts_by_type[ctype].append(node)
        
        # Track active concepts
        if node.get('activation', 0) > 0:
            active_concepts.append(node)
    
    # Print concepts by type
    for ctype in sorted(concepts_by_type.keys()):
        concepts = concepts_by_type[ctype]
        print(f"{ctype.upper()} concepts ({len(concepts)}):")
        
        # Sort by creation time (newest first)
        concepts.sort(key=lambda c: c.get('meta', {}).get('created', 0), reverse=True)
        
        # Show first 3 concepts of each type
        for concept in concepts[:3]:
            print_concept(concept, indent=1)
        
        if len(concepts) > 3:
            print(f"  ... and {len(concepts) - 3} more {ctype} concepts")
        print()
    
    # Print active concepts
    if active_concepts:
        print(f"ACTIVE concepts ({len(active_concepts)}):")
        active_concepts.sort(key=lambda c: c.get('activation', 0), reverse=True)
        for concept in active_concepts[:5]:
            print_concept(concept, indent=1)
        print()
    
    # Print relations
    if edges:
        print("RELATIONS:")
        print_relations(edges, concepts_by_id, indent=1)
    
    # Print summary statistics
    print("SUMMARY:")
    for ctype, concepts in concepts_by_type.items():
        active_count = len([c for c in concepts if c.get('activation', 0) > 0])
        print(f"  {ctype}: {len(concepts)} total ({active_count} active)")

def main():
    """Main function."""
    storage_path = "concept_graph.json"
    
    if len(sys.argv) > 1:
        storage_path = sys.argv[1]
    
    inspect_concept_graph(storage_path)

if __name__ == "__main__":
    main() 