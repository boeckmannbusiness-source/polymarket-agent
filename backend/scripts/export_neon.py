"""Export all data from Neon database to JSON files via asyncpg."""

import asyncio
import json
import os
from pathlib import Path

import asyncpg

DUMP_DIR = Path(__file__).resolve().parent.parent.parent / "data_dump"

NEON_DSN = os.environ.get(
    "NEON_DATABASE_URL",
    "postgresql://neondb_owner:npg_0fdsGe6JLgUP@ep-hidden-breeze-alnjfgr2.c-3.eu-central-1.aws.neon.tech/neondb"
)


def serialize(val):
    if isinstance(val, (bytes, bytearray)):
        return val.hex()
    elif isinstance(val, memoryview):
        return bytes(val).hex()
    elif hasattr(val, 'isoformat'):
        return val.isoformat()
    elif isinstance(val, dict):
        return json.dumps(val)
    elif isinstance(val, list):
        return json.dumps(val)
    return val


async def export_table(conn, table_name: str, dump_dir: Path):
    print(f"  Exporting {table_name}...")
    rows = await conn.fetch(f"SELECT * FROM public.{table_name} ORDER BY 1")
    data = [{k: serialize(v) for k, v in dict(row).items()} for row in rows]
    filepath = dump_dir / f"{table_name}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, default=str, ensure_ascii=False)
    print(f"    {len(data)} rows -> {filepath.name}")


async def main():
    dump_dir = DUMP_DIR
    dump_dir.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(NEON_DSN)
    try:
        tables = [
            r["table_name"]
            for r in await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )
        ]
        print(f"Found {len(tables)} tables: {', '.join(tables)}")

        for table in tables:
            try:
                await export_table(conn, table, dump_dir)
            except Exception as e:
                print(f"  ERROR exporting {table}: {e}")
    finally:
        await conn.close()

    print(f"\nDone! Data exported to {dump_dir}")


if __name__ == "__main__":
    asyncio.run(main())
