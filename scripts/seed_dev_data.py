"""One-off script: seed mock data into MongoDB for local development."""
import asyncio
import json
from pathlib import Path

from src.database import init_db


async def main() -> None:
    await init_db()
    mock_dir = Path(__file__).parents[1] / "mock_data"
    for f in mock_dir.glob("*.json"):
        data = json.loads(f.read_text())
        print(f"Loaded {f.name}: {list(data.keys())}")
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
