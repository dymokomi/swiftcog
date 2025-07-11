#!/usr/bin/env python3
"""
Utility script to inspect the memory storage file.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

def format_timestamp(timestamp_str):
    """Format timestamp for better readability."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str

def print_memory_section(title, data, indent=0):
    """Print a section of memory data with proper formatting."""
    prefix = "  " * indent
    print(f"{prefix}{title}:")
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                print(f"{prefix}  {key} ({len(value)} items):")
                for i, item in enumerate(value[-5:]):  # Show last 5 items
                    if isinstance(item, dict):
                        if 'timestamp' in item:
                            timestamp = format_timestamp(item['timestamp'])
                            content = item.get('content', item.get('goal', str(item)))
                            print(f"{prefix}    {i+1}. [{timestamp}] {content}")
                        else:
                            print(f"{prefix}    {i+1}. {item}")
                    else:
                        print(f"{prefix}    {i+1}. {item}")
                if len(value) > 5:
                    print(f"{prefix}    ... and {len(value) - 5} more items")
            elif isinstance(value, dict):
                print_memory_section(key, value, indent + 1)
            else:
                print(f"{prefix}  {key}: {value}")
    else:
        print(f"{prefix}  {data}")

def inspect_memory(storage_path="memory_storage.json"):
    """Inspect the memory storage file."""
    storage_file = Path(storage_path)
    
    if not storage_file.exists():
        print(f"Memory storage file not found: {storage_path}")
        print("The file will be created when the memory kernel first runs.")
        return
    
    try:
        with open(storage_file, 'r', encoding='utf-8') as f:
            memory_data = json.load(f)
    except Exception as e:
        print(f"Error reading memory storage file: {e}")
        return
    
    print(f"Memory Storage Inspection - {storage_path}")
    print("=" * 50)
    
    # Print metadata
    if 'metadata' in memory_data:
        metadata = memory_data['metadata']
        print(f"Total messages processed: {metadata.get('total_messages_processed', 0)}")
        print(f"Last active: {format_timestamp(metadata.get('last_active', 'Unknown'))}")
        print(f"Kernel version: {metadata.get('kernel_version', 'Unknown')}")
        print()
    
    # Print working memory
    if 'working_memory' in memory_data:
        print_memory_section("Working Memory", memory_data['working_memory'])
        print()
    
    # Print long-term memory
    if 'long_term_memory' in memory_data:
        print_memory_section("Long-term Memory", memory_data['long_term_memory'])
        print()
    
    # Print summary
    total_items = len(memory_data)
    print(f"Total memory sections: {total_items}")
    
    if 'working_memory' in memory_data:
        dialog_count = len(memory_data['working_memory'].get('dialog_history', []))
        goals_count = len(memory_data['working_memory'].get('current_goals', []))
        print(f"Working memory: {dialog_count} dialog entries, {goals_count} current goals")
    
    if 'long_term_memory' in memory_data:
        ltm = memory_data['long_term_memory']
        facts_count = sum(len(facts) for facts in ltm.get('facts', {}).values())
        summaries_count = len(ltm.get('conversation_summaries', []))
        lt_goals_count = len(ltm.get('long_term_goals', []))
        print(f"Long-term memory: {facts_count} facts, {summaries_count} summaries, {lt_goals_count} long-term goals")

def main():
    """Main function."""
    storage_path = "memory_storage.json"
    
    if len(sys.argv) > 1:
        storage_path = sys.argv[1]
    
    inspect_memory(storage_path)

if __name__ == "__main__":
    main() 