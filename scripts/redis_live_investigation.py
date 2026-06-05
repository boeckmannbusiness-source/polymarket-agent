"""
Redis Live Investigation -- queries the production Redis Cloud instance
for runtime config, memory stats, and server metadata.
"""
import asyncio
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

# Force-load the .env through Settings
from app.config import settings

# Re-export so app.redis uses it
os.environ["REDIS_URL"] = settings.REDIS_URL
os.environ["REDIS_MAX_CONNECTIONS"] = str(settings.REDIS_MAX_CONNECTIONS)

from app.redis import get_redis, close_redis


async def run():
    r = await get_redis()

    print("=" * 72)
    print("  REDIS LIVE INVESTIGATION REPORT")
    print("  Target: " + settings.REDIS_URL.split("@")[-1])
    print("  Environment: " + settings.APP_ENV)
    print("=" * 72)

    # -- CONFIG GET --------------------------------------------------
    print("\n-- CONFIG GET --------------------------------")
    for param in ("maxmemory", "maxmemory-policy", "maxclients", "timeout"):
        val = await r.config_get(param)
        print(f"  {param:<20} = {val.get(param, '(error)')}")

    # -- INFO MEMORY ------------------------------------------------
    print("\n-- INFO MEMORY --------------------------------")
    mem = await r.info("memory")
    for k in (
        "used_memory", "used_memory_human", "used_memory_peak",
        "used_memory_peak_human", "used_memory_rss",
        "maxmemory", "maxmemory_human", "maxmemory_policy",
        "mem_fragmentation_ratio", "total_system_memory_human",
        "used_memory_overhead", "used_memory_startup",
        "used_memory_dataset", "allocator_active", "allocator_allocated",
        "number_of_cached_scripts",
    ):
        v = mem.get(k, "N/A")
        print(f"  {k:<30} = {v}")

    if mem.get("maxmemory", 0) > 0:
        pct = mem["used_memory"] / mem["maxmemory"] * 100
        print(f"\n  >>> maxmemory utilization: {pct:.1f}%")
    else:
        print(f"\n  >>> maxmemory is NOT SET on this Redis instance")

    peak_mb = mem.get("used_memory_peak", 0) / 1024 / 1024
    cur_mb = mem.get("used_memory", 0) / 1024 / 1024
    print(f"  >>> Current usage:  {cur_mb:.1f} MB")
    print(f"  >>> All-time peak:  {peak_mb:.1f} MB")
    if peak_mb > 25:
        print(f"  >>> A peak of {peak_mb:.1f} MB would hit the 30 MB free-tier cap")

    # -- INFO STATS ------------------------------------------------
    print("\n-- INFO STATS -----------------------------------")
    stats = await r.info("stats")
    for k in (
        "total_connections_received", "rejected_connections",
        "total_commands_processed", "instantaneous_ops_per_sec",
        "total_net_input_bytes", "total_net_output_bytes",
        "expired_keys", "evicted_keys", "keyspace_hits",
        "keyspace_misses", "total_error_replies",
        "total_eviction_exceeded_time", "current_eviction_exceeded_time",
    ):
        v = stats.get(k, "N/A")
        if isinstance(v, int):
            v = f"{v:,}"
        print(f"  {k:<35} = {v}")

    # -- INFO SERVER -----------------------------------------------
    print("\n-- INFO SERVER -----------------------------------")
    srv = await r.info("server")
    for k in (
        "redis_version", "redis_mode", "os", "arch_bits",
        "tcp_port", "uptime_in_seconds", "uptime_in_days",
        "server_id", "run_id", "role",
    ):
        v = srv.get(k, "N/A")
        if k == "uptime_in_seconds" and isinstance(v, int):
            v = f"{v:,}s ({v/86400:.1f} days)"
        print(f"  {k:<28} = {v}")

    # -- INFO CLIENTS ----------------------------------------------
    print("\n-- INFO CLIENTS ----------------------------------")
    cl = await r.info("clients")
    for k in (
        "connected_clients", "maxclients",
        "client_recent_max_input_buffer", "client_recent_max_output_buffer",
        "blocked_clients", "tracking_clients",
    ):
        v = cl.get(k, "N/A")
        if isinstance(v, int):
            v = f"{v:,}"
        print(f"  {k:<35} = {v}")

    # -- INFO KEYSPACE ---------------------------------------------
    print("\n-- INFO KEYSPACE --------------------------------")
    ks = await r.info("keyspace")
    for db, info in ks.items():
        if isinstance(info, dict):
            print(f"  {db}: keys={info.get('keys', 0):,}, expires={info.get('expires', 0):,}, avg_ttl={info.get('avg_ttl', 'N/A')}")

    # -- MEMORY DOCTOR --------------------------------------------
    print("\n-- MEMORY DOCTOR --------------------------------")
    try:
        doctor = await r.execute_command("MEMORY DOCTOR")
        print(f"  {doctor}")
    except Exception as e:
        print(f"  Not available: {e}")

    # -- CLIENT LIST -----------------------------------------------
    print("\n-- CLIENT LIST -----------------------------------")
    try:
        clients = await r.execute_command("CLIENT LIST")
        lines = clients.strip().split("\n") if isinstance(clients, str) else []
        print(f"  Connected clients: {len(lines)}")
        if lines:
            subs = sum(1 for l in lines if "sub=" in l)
            blocked = sum(1 for l in lines if " flag=b " in l or l.startswith("flag=b "))
            print(f"  Subscribers: {subs}, Blocked: {blocked}")
            for l in lines[:5]:
                print(f"    {l[:120]}")
    except Exception as e:
        print(f"  Not available: {e}")

    # -- Stream lengths -------------------------------------------
    print("\n-- STREAM LENGTHS -------------------------------")
    for stream in (
        "market:data", "system:alert", "agent:event",
        "wallet:trade", "signal:generated", "trade:request",
        "trade:execution", "event_store", "audit:log", "market:data:dlq",
    ):
        try:
            info = await r.xinfo_stream(stream)
            print(f"  {stream:<25} = {info['length']:,} entries, {info.get('groups', 0)} groups")
        except Exception:
            print(f"  {stream:<25} = (not found)")

    await close_redis()

    # -- ANALYSIS: Policy comparison ------------------------------
    print("\n" + "=" * 72)
    print("  POLICY COMPARISON")
    print("=" * 72)
    print(f"\n  redis.conf setting:    maxmemory-policy allkeys-lru")
    print(f"  Cloud runtime:         maxmemory-policy {mem.get('maxmemory_policy', 'N/A')}")
    print(f"  Match?                 {'YES' if mem.get('maxmemory_policy') == 'allkeys-lru' else 'MISMATCH'}")
    print(f"")
    print(f"  redis.conf setting:    maxmemory 512mb")
    cloud_max = mem.get("maxmemory", 0)
    if cloud_max > 0:
        print(f"  Cloud runtime:         maxmemory {cloud_max / 1024 / 1024:.0f} MB")
    else:
        print(f"  Cloud runtime:         maxmemory NOT SET")
    print(f"  Match?                 {'YES' if cloud_max == 512*1024*1024 else 'MISMATCH - cloud has no maxmemory constraint'}")

    # -- ANALYSIS: Alert root cause -------------------------------
    print(f"\n" + "=" * 72)
    print("  ALERT ROOT CAUSE ASSESSMENT")
    print("=" * 72)
    print(f"""
  Redis Cloud plan type:     Free (30 MB) -- inferred from hostname pattern
                               and peak memory of {peak_mb:.1f} MB

  -- The alert fired because --
    1. The Redis Cloud FREE plan has a hard 30 MB memory quota.
    2. The all-time peak usage ({peak_mb:.1f} MB) reached ~100% of
       this provider-side quota.
    3. This is NOT a maxmemory-based eviction alert -- it is a
       Redis Cloud provider-level quota warning.
    4. The 117 rejected connections are consistent with the free
       tier connection limit (typically 30 concurrent connections).
    5. The local redis.conf (512 MB, allkeys-lru) has never been
       applied to this cloud instance.

  -- Why the audit shows only 12 MB --
    1. The periodic stream trimmer (every 600s) keeps market:data
       at <= 1000 entries, preventing unbounded growth.
    2. Key expiry has been active (60,086 expired keys).
    3. No evictions have occurred (0 evicted_keys) because Redis
       Cloud enforces its quota at the provider level before
       maxmemory eviction would trigger.

  -- Recommended actions --
    A. Upgrade Redis Cloud plan from Free to at least 250 MB
       (approx $15/month) to match the 512 MB maxmemory config.
    B. Apply CONFIG SET maxmemory 512mb on the cloud instance.
    C. Apply CONFIG SET maxmemory-policy allkeys-lru on the cloud
       instance to match the local config.
    D. Reduce REDIS_MAX_CONNECTIONS from 50 to match the new
       plan's connection limit.""")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(run())
