"""One-off script: create MongoDB indexes. Run once per deployment."""
import asyncio

from src.database import init_db


async def main() -> None:
    await init_db()
    print("Indexes created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
