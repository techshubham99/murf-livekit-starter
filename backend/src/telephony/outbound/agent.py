"""
Outbound Agent Entrypoint Wrapper for ShikshaMitra AI

Reuses the main ShikshaMitra Agent implementation in src/agent.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend root is in sys.path when executed directly
backend_root = Path(__file__).resolve().parent.parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from livekit.agents import cli
from src.agent import server

if __name__ == "__main__":
    cli.run_app(server)
