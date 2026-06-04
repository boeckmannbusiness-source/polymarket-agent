"""Dump all DB tables to stdout as JSON. Run inside Fly.io container via: fly ssh console -C "python /app/scripts/fly_export.py" > neon_dump.json"""

import asyncio
import json
import os
import sys

import asyncpg


def serialize(val):
    if isinstance(val, (bytes, bytearray, memoryview)):
        return bytes(val).hex()
    elif hasattr(val, 'isoformat'):
        return val.isoformat()
    elif isinstance(val, (dict, list)):
        return json.dumps(val)
    return val


async def main():
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        tables = [
            r["table_name"]
            for r in await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )
        ]

        dump = {"_meta": {"table_count": len(tables), "tables": tables}}

        for table in tables:
            rows = await conn.fetch(f"SELECT * FROM public.{table} ORDER BY 1")
            data = [{k: serialize(v) for k, v in dict(r).items()} for r in rows]
            dump[table] = data

        json.dump(dump, sys.stdout, default=str, ensure_ascii=False, indent=2)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
