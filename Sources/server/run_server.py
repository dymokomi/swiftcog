#!/usr/bin/env python3
"""
Simple startup script for the SwiftCog Python server.
This script sets up the environment and runs the server with proper error handling.
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main server
from main import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1) 