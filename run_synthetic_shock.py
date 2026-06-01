#!/usr/bin/env python3
"""Root-level entry point for synthetic market shock testing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from scripts.synthetic_market_shock import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
