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
    
    # Remove edges associated with the concepts to remove, but be more nuanced
    # about preserving valuable knowledge connections
    filtered_edges = []
    removed_edges = 0
    
    # First pass: identify knowledge nodes and their connections
    knowledge_node_ids = {node.get('id') for node in filtered_nodes if node.get('ctype') == 'knowledge'}
    percept_node_ids = {node.get('id') for node in filtered_nodes if node.get('ctype') == 'percept'}
    
    for edge in edges:
        source = edge.get('source')
        target = edge.get('target')
        
        # Remove edge if BOTH source and target are concepts to remove
        if source in concepts_to_remove and target in concepts_to_remove:
            removed_edges += 1
            continue
            
        # Remove edge if it connects TO a concept to remove (but preserve valuable knowledge)
        if target in concepts_to_remove:
            # If source is knowledge connected to a percept/person, this might be important context
            # but we'll remove the context connection while preserving the knowledge node
            removed_edges += 1
            continue
            
        # Remove edge if it connects FROM a concept to remove  
        if source in concepts_to_remove:
            removed_edges += 1
            continue
            
        # Keep all other edges (connections between knowledge, percepts, etc.)
        filtered_edges.append(edge)
    
    # Second pass: remove knowledge nodes that are now orphaned 
    # (not connected to any percepts or other valuable nodes)
    connected_knowledge_ids = set()
    for edge in filtered_edges:
        source = edge.get('source')
        target = edge.get('target')
        
        # If knowledge is connected to a percept, keep it
        if source in knowledge_node_ids and target in percept_node_ids:
            connected_knowledge_ids.add(source)
        if target in knowledge_node_ids and source in percept_node_ids:
            connected_knowledge_ids.add(target)
        
        # Also keep knowledge connected to other knowledge (conceptual relationships)
        if source in knowledge_node_ids and target in knowledge_node_ids:
            connected_knowledge_ids.add(source)
            connected_knowledge_ids.add(target)
    
    # Remove orphaned knowledge nodes (those not connected to anything valuable)
    final_nodes = []
    orphaned_knowledge_count = 0
    
    for node in filtered_nodes:
        if node.get('ctype') == 'knowledge' and node.get('id') not in connected_knowledge_ids:
            # This knowledge node is orphaned, remove it
            orphaned_knowledge_count += 1
            print(f"🗑️  Removing orphaned knowledge: {node.get('label', 'Unknown')}")
            
            # Also remove any remaining edges to this orphaned node
            node_id = node.get('id')
            filtered_edges = [edge for edge in filtered_edges 
                            if edge.get('source') != node_id and edge.get('target') != node_id]
        else:
            final_nodes.append(node)
    
    # Update the graph data
    graph_data['nodes'] = final_nodes
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
        
        if orphaned_knowledge_count > 0:
            print(f"✅ Removed {orphaned_knowledge_count} orphaned knowledge concepts")
        
        print(f"✅ Removed {removed_edges} associated edges")
        print(f"✅ Kept {len(final_nodes)} concepts (knowledge, percepts, etc.)")
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