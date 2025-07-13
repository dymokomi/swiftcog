#!/usr/bin/env python3
"""
Cleanup utility for SwiftCog server startup.
Handles --forget and --clean operations to reset memory and logs.
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from typing import List, Dict, Any

def forget_all():
    """
    Delete concept_graph.json and clear everything in logs folder recursively.
    This completely resets the memory and logs.
    """
    current_dir = Path(__file__).parent
    
    # Delete concept_graph.json
    concept_graph_path = current_dir / "concept_graph.json"
    if concept_graph_path.exists():
        concept_graph_path.unlink()
        print("✅ Deleted concept_graph.json")
    else:
        print("ℹ️  concept_graph.json not found (already clean)")
    
    # Clear logs folder recursively
    logs_path = current_dir / "logs"
    if logs_path.exists():
        shutil.rmtree(logs_path)
        logs_path.mkdir()  # Recreate empty logs directory
        print("✅ Cleared logs folder")
    else:
        print("ℹ️  logs folder not found (creating empty one)")
        logs_path.mkdir()
    
    print("🧹 Forget operation completed - all memory and logs cleared")

def clean_conversations():
    """
    Remove conversation, goal, and context type concepts from memory and clean up associated edges.
    This preserves knowledge but removes session-related concepts.
    """
    current_dir = Path(__file__).parent
    concept_graph_path = current_dir / "concept_graph.json"
    
    if not concept_graph_path.exists():
        print("ℹ️  concept_graph.json not found - nothing to clean")
        return
    
    try:
        # Load the concept graph
        with open(concept_graph_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading concept_graph.json: {e}")
        return
    
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])
    
    # Find concept IDs to remove (conversation, goal, context)
    concepts_to_remove = set()
    filtered_nodes = []
    removal_counts = {"conversation": 0, "goal": 0, "context": 0}
    
    for node in nodes:
        node_type = node.get('ctype')
        if node_type in ['conversation', 'goal', 'context']:
            concepts_to_remove.add(node.get('id'))
            removal_counts[node_type] += 1
            print(f"🗑️  Removing {node_type}: {node.get('label', 'Unknown')}")
        else:
            filtered_nodes.append(node)
    
    # Remove edges associated with the concepts to remove
    filtered_edges = []
    removed_edges = 0
    
    for edge in edges:
        source = edge.get('source')
        target = edge.get('target')
        
        # Keep edge only if neither source nor target is a concept to remove
        if source not in concepts_to_remove and target not in concepts_to_remove:
            filtered_edges.append(edge)
        else:
            removed_edges += 1
    
    # Update the graph data
    graph_data['nodes'] = filtered_nodes
    graph_data['edges'] = filtered_edges
    
    # Save the cleaned graph
    try:
        with open(concept_graph_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        
        # Report what was removed
        total_removed = sum(removal_counts.values())
        for ctype, count in removal_counts.items():
            if count > 0:
                print(f"✅ Removed {count} {ctype} concepts")
        
        print(f"✅ Removed {removed_edges} associated edges")
        print(f"✅ Kept {len(filtered_nodes)} concepts (knowledge, percepts, etc.)")
        print("🧹 Clean operation completed - session concepts removed")
        
    except Exception as e:
        print(f"❌ Error saving cleaned concept_graph.json: {e}")
        return

def main():
    """Main function to handle cleanup operations."""
    parser = argparse.ArgumentParser(description="SwiftCog Memory Cleanup Utility")
    parser.add_argument("--forget", action="store_true", 
                       help="Delete concept_graph.json and clear logs folder")
    parser.add_argument("--clean", action="store_true", 
                       help="Remove conversation, goal, and context concepts and associated edges")
    
    args = parser.parse_args()
    
    if not args.forget and not args.clean:
        print("❌ No cleanup operation specified")
        print("Usage: python cleanup.py [--forget] [--clean]")
        print("  --forget: Delete all memory and logs")
        print("  --clean:  Remove session concepts (conversations, goals, contexts)")
        return
    
    if args.forget and args.clean:
        print("❌ Cannot use --forget and --clean together")
        print("Choose one operation:")
        print("  --forget: Complete reset (deletes everything)")
        print("  --clean:  Remove session concepts (conversations, goals, contexts)")
        return
    
    print("🧹 SwiftCog Memory Cleanup")
    print("=" * 30)
    
    if args.forget:
        print("🗑️  Performing FORGET operation...")
        print("⚠️  This will delete ALL memory and logs!")
        forget_all()
    
    if args.clean:
        print("🗑️  Performing CLEAN operation...")
        print("ℹ️  This will remove session concepts (conversations, goals, contexts)")
        clean_conversations()

if __name__ == "__main__":
    main() 