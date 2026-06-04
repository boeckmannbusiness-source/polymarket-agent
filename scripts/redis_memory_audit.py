"""
Redis Memory Audit Script
=========================
Run: python -m scripts.redis_memory_audit

Generates a comprehensive report of Redis memory usage including:
- INFO memory, INFO stats, INFO keyspace
- MEMORY STATS, MEMORY DOCTOR
- Largest keys and key prefixes
- TTL coverage analysis
- Stream lengths and estimated memory

Output: console table + JSON report in data_dump/
"""

import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from app.redis import get_redis, close_redis


def _fmt_bytes(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    elif b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 ** 3:
        return f"{b / 1024 ** 2:.1f} MB"
    else:
        return f"{b / 1024 ** 3:.2f} GB"


class RedisAudit:
    def __init__(self):
        self.report: dict = {}

    async def run(self):
        r = await get_redis()
        logger = print

        logger("=" * 72)
        logger("  REDIS MEMORY AUDIT")
        logger(f"  Started: {datetime.now(timezone.utc).isoformat()}")
        logger("=" * 72)

        # ── INFO memory ──────────────────────────────────────────
        logger("\n[1/6] INFO memory ...")
        info_mem = await r.info("memory")
        self.report["info_memory"] = {
            k: v for k, v in info_mem.items()
            if isinstance(v, (int, float, str))
        }
        used = info_mem.get("used_memory", 0)
        peak = info_mem.get("used_memory_peak", 0)
        maxmem = info_mem.get("maxmemory", 0)
        rss = info_mem.get("used_memory_rss", 0)
        frag = info_mem.get("mem_fragmentation_ratio", 0)
        logger(f"  used_memory:          {_fmt_bytes(used)} ({used:,} B)")
        logger(f"  used_memory_rss:      {_fmt_bytes(rss)}")
        logger(f"  used_memory_peak:     {_fmt_bytes(peak)}")
        logger(f"  maxmemory:            {_fmt_bytes(maxmem)}" if maxmem else "  maxmemory:            not set")
        if maxmem:
            logger(f"  utilization:          {used / maxmem * 100:.1f}%")
        logger(f"  mem_fragmentation:    {frag:.2f}")
        logger(f"  lazy_free_pending:    {info_mem.get('lazy_free_pending_objects', 0):,}")

        # ── MEMORY STATS ─────────────────────────────────────────
        logger("\n[2/6] MEMORY STATS ...")
        try:
            mem_stats = await r.execute_command("MEMORY STATS")
            self.report["memory_stats_raw"] = mem_stats
            # mem_stats is a flat list: [key1, val1, key2, val2, ...]
            stats_dict = {}
            for i in range(0, len(mem_stats), 2):
                k = mem_stats[i]
                v = mem_stats[i + 1]
                if isinstance(k, bytes):
                    k = k.decode()
                if isinstance(v, bytes):
                    v = v.decode()
                stats_dict[k] = v
            self.report["memory_stats"] = stats_dict

            for key in ("peak.allocated", "total.allocated", "startup.allocated",
                        "dataset.bytes", "overhead.total", "keys.count"):
                val = stats_dict.get(key)
                if val is not None:
                    try:
                        val_num = int(val) if not isinstance(val, int) else val
                        logger(f"  {key}: {_fmt_bytes(val_num) if 'allocated' in key or 'bytes' in key or 'overhead' in key else f'{val_num:,}'}")
                    except (ValueError, TypeError):
                        logger(f"  {key}: {val}")
        except Exception as e:
            logger(f"  MEMORY STATS not available: {e}")

        # ── MEMORY DOCTOR ────────────────────────────────────────
        logger("\n[3/6] MEMORY DOCTOR ...")
        try:
            doctor = await r.execute_command("MEMORY DOCTOR")
            self.report["memory_doctor"] = doctor
            logger(f"  {doctor}")
        except Exception as e:
            logger(f"  MEMORY DOCTOR not available: {e}")

        # ── INFO stats ───────────────────────────────────────────
        logger("\n[4/6] INFO stats ...")
        info_stats = await r.info("stats")
        self.report["info_stats"] = {
            k: v for k, v in info_stats.items()
            if isinstance(v, (int, float, str))
        }
        logger(f"  total_connections_received: {info_stats.get('total_connections_received', 'N/A'):,}")
        logger(f"  total_commands_processed:   {info_stats.get('total_commands_processed', 'N/A'):,}")
        logger(f"  instantaneous_ops_per_sec:  {info_stats.get('instantaneous_ops_per_sec', 'N/A')}")
        logger(f"  total_net_input_bytes:      {_fmt_bytes(int(info_stats.get('total_net_input_bytes', 0)))}")
        logger(f"  total_net_output_bytes:     {_fmt_bytes(int(info_stats.get('total_net_output_bytes', 0)))}")
        logger(f"  expired_keys:               {info_stats.get('expired_keys', 'N/A'):,}")
        logger(f"  evicted_keys:               {info_stats.get('evicted_keys', 'N/A'):,}")
        logger(f"  keyspace_hits:              {info_stats.get('keyspace_hits', 'N/A'):,}")
        logger(f"  keyspace_misses:            {info_stats.get('keyspace_misses', 'N/A'):,}")

        # ── INFO keyspace ────────────────────────────────────────
        logger("\n[5/6] INFO keyspace ...")
        info_ks = await r.info("keyspace")
        self.report["info_keyspace"] = {}
        for db_name, db_info in info_ks.items():
            if isinstance(db_info, dict):
                self.report["info_keyspace"][db_name] = db_info
                logger(f"  {db_name}: keys={db_info.get('keys', 0):,}, "
                       f"expires={db_info.get('expires', 0):,}, "
                       f"avg_ttl={db_info.get('avg_ttl', 0):,}")

        # ── SCAN + per-prefix analysis ───────────────────────────
        logger("\n[6/6] Scanning keys (this may take a while) ...")

        prefix_stats: dict = defaultdict(lambda: {
            "count": 0, "total_bytes": 0, "sizes": [],
            "ttls": [], "no_ttl": 0, "types": defaultdict(int),
        })
        largest_keys: list = []
        no_ttl_keys: list = []
        total_scanned = 0
        cursor = 0
        scan_start = time.monotonic()

        while True:
            cursor, keys = await r.scan(cursor=cursor, count=500)
            if not keys:
                if cursor == 0:
                    break
                continue

            for key in keys:
                total_scanned += 1
                try:
                    ktype = await r.type(key)
                    mem = await r.execute_command("MEMORY USAGE", key) or 0
                    ttl = await r.ttl(key)
                    idle = await r.object("idletime", key)
                except Exception:
                    continue

                # Determine prefix
                decoded = key if isinstance(key, str) else key.decode()
                # Normalize prefix to first two colon-delimited parts or first word
                parts = decoded.split(":")
                if len(parts) >= 3:
                    prefix = f"{parts[0]}:{parts[1]}:*"
                elif len(parts) == 2:
                    prefix = f"{parts[0]}:{parts[1]}:*" if parts[1] else f"{parts[0]}:*"
                else:
                    prefix = f"{decoded}"

                ps = prefix_stats[prefix]
                ps["count"] += 1
                ps["total_bytes"] += mem
                ps["sizes"].append(mem)
                ps["types"][ktype] += 1
                if ttl >= 0:
                    ps["ttls"].append(ttl)
                else:
                    ps["no_ttl"] += 1
                    if mem > 1024:
                        no_ttl_keys.append((decoded, mem, ktype, idle))

                # Track largest individual keys
                largest_keys.append((decoded, mem, ktype, ttl, idle))

            if cursor == 0:
                break

        scan_elapsed = time.monotonic() - scan_start
        logger(f"  Scanned {total_scanned:,} keys in {scan_elapsed:.1f}s")

        # Sort largest keys
        largest_keys.sort(key=lambda x: x[1], reverse=True)
        largest_keys = largest_keys[:50]
        self.report["largest_keys"] = [
            {"key": k, "bytes": m, "type": t, "ttl": ttl_, "idle": i}
            for k, m, t, ttl_, i in largest_keys
        ]

        # Aggregate by prefix
        prefix_summary = []
        for prefix, ps in sorted(prefix_stats.items(), key=lambda x: x[1]["total_bytes"], reverse=True):
            sizes = ps["sizes"]
            avg_size = sum(sizes) / len(sizes) if sizes else 0
            avg_ttl = sum(ps["ttls"]) / len(ps["ttls"]) if ps["ttls"] else -1
            min_ttl = min(ps["ttls"]) if ps["ttls"] else -1
            dominant_type = max(ps["types"], key=ps["types"].get) if ps["types"] else "?"
            prefix_summary.append({
                "prefix": prefix,
                "count": ps["count"],
                "avg_size_bytes": round(avg_size, 0),
                "total_size_bytes": ps["total_bytes"],
                "total_size_human": _fmt_bytes(ps["total_bytes"]),
                "avg_ttl": round(avg_ttl, 1) if avg_ttl >= 0 else -1,
                "min_ttl": min_ttl,
                "no_ttl_count": ps["no_ttl"],
                "dominant_type": dominant_type,
                "no_ttl_pct": round(ps["no_ttl"] / ps["count"] * 100, 1) if ps["count"] else 0,
            })
        self.report["prefix_summary"] = prefix_summary

        # ── Stream analysis ──────────────────────────────────────
        logger("\n  Checking streams ...")
        stream_info = {}
        try:
            all_streams = []
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match="*", count=1000)
                for k in keys:
                    ktype = await r.type(k)
                    if ktype == "stream":
                        all_streams.append(k)
                if cursor == 0:
                    break
            for s in all_streams:
                try:
                    xi = await r.xinfo_stream(s)
                    stream_info[s if isinstance(s, str) else s.decode()] = {
                        "length": xi.get("length", 0),
                        "radix_tree_keys": xi.get("radix-tree-keys", 0),
                        "radix_tree_nodes": xi.get("radix-tree-nodes", 0),
                        "groups": xi.get("groups", 0),
                        "last_generated_id": xi.get("last-generated-id", ""),
                    }
                except Exception:
                    pass
        except Exception as e:
            logger(f"  Stream scan error: {e}")

        self.report["streams"] = stream_info
        if stream_info:
            logger(f"  Found {len(stream_info)} streams:")
            for sname, sinfo in sorted(stream_info.items(), key=lambda x: x[1]["length"], reverse=True):
                logger(f"    {sname}: {sinfo['length']:,} entries, "
                       f"{sinfo['groups']} groups, "
                       f"radix keys={sinfo['radix_tree_keys']}, "
                       f"radix nodes={sinfo['radix_tree_nodes']}")
        else:
            logger("  No streams found")

        # ── Print prefix table ───────────────────────────────────
        logger("\n")
        logger("=" * 120)
        logger(f"  PREFIX SUMMARY (sorted by total size, top {min(len(prefix_summary), 30)})")
        logger("=" * 120)
        header = f"{'Prefix':<32} {'Count':>8} {'Avg Size':>10} {'Total Size':>12} {'Avg TTL':>8} {'Min TTL':>8} {'No-TTL':>6} {'NoTTL%':>7} {'Type':>8}"
        logger(header)
        logger("-" * 120)
        for ps in prefix_summary[:30]:
            avg_ttl_str = f"{ps['avg_ttl']:.0f}s" if ps['avg_ttl'] >= 0 else "N/A"
            min_ttl_str = f"{ps['min_ttl']}s" if ps['min_ttl'] >= 0 else "N/A"
            logger(
                f"{ps['prefix']:<32} "
                f"{ps['count']:>8,} "
                f"{_fmt_bytes(ps['avg_size_bytes']):>10} "
                f"{ps['total_size_human']:>12} "
                f"{avg_ttl_str:>8} "
                f"{min_ttl_str:>8} "
                f"{ps['no_ttl_count']:>6} "
                f"{ps['no_ttl_pct']:>6.1f}% "
                f"{ps['dominant_type']:>8}"
            )
        if len(prefix_summary) > 30:
            logger(f"  ... and {len(prefix_summary) - 30} more prefixes")

        # ── Largest keys table ───────────────────────────────────
        logger("\n")
        logger("=" * 100)
        logger("  LARGEST INDIVIDUAL KEYS (top 20)")
        logger("=" * 100)
        header2 = f"{'Key':<50} {'Size':>10} {'Type':>8} {'TTL':>8} {'Idle':>8}"
        logger(header2)
        logger("-" * 100)
        for k, m, t, ttl_, idle in largest_keys[:20]:
            key_display = k if len(k) < 48 else k[:45] + "..."
            logger(f"{key_display:<50} {_fmt_bytes(m):>10} {t:>8} {ttl_:>8} {idle:>6}s")

        # ── Keys without TTL ─────────────────────────────────────
        logger("\n")
        logger(f"  KEYS WITHOUT TTL (count: {len(no_ttl_keys)}, showing those > 1 KB)")
        logger("-" * 80)
        if no_ttl_keys:
            no_ttl_keys.sort(key=lambda x: x[1], reverse=True)
            for k, m, t, idle in no_ttl_keys[:20]:
                logger(f"    {k:<48} {_fmt_bytes(m):>10} {t:>8} idle={idle}s")
        else:
            logger("  (none found)")
        logger(f"  Total keys without TTL: {sum(ps['no_ttl_count'] for ps in prefix_summary)}")

        # ── Estimated memory by subsystem ────────────────────────
        logger("\n")
        logger("  ESTIMATED MEMORY BY SUBSYSTEM")
        logger("-" * 80)

        subsystems = {
            "Streams (market:*, wallet:*, etc)": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("market:") or ps["prefix"].startswith("wallet:")
                or ps["prefix"].startswith("signal:") or ps["prefix"].startswith("trade:")
                or ps["prefix"].startswith("agent:") or ps["prefix"].startswith("system:")
                or ps["prefix"].startswith("audit:") or ps["prefix"].startswith("event_")
                or ps["prefix"].startswith("remote:")
            ),
            "Shadow Trading": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("shadow:")
            ),
            "Dedup Cache (dedup:event:*)": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("dedup:")
            ),
            "Circuit Breakers": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("circuit_breaker:")
            ),
            "Control Plane": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("control:")
            ),
            "Portfolio Cache (portfolio:*)": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("portfolio:")
            ),
            "Scheduler": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("scheduler:")
            ),
            "Incidents": sum(
                ps["total_size_bytes"] for ps in prefix_summary
                if ps["prefix"].startswith("incident")
            ),
        }
        for sub_name, sub_bytes in sorted(subsystems.items(), key=lambda x: x[1], reverse=True):
            pct = (sub_bytes / used * 100) if used else 0
            if sub_bytes > 0:
                logger(f"  {sub_name:<36} {_fmt_bytes(sub_bytes):>12}  {pct:>5.1f}%")

        # ── Summary ──────────────────────────────────────────────
        logger("\n")
        logger("=" * 72)
        logger("  AUDIT SUMMARY")
        logger("=" * 72)
        logger(f"  Keys scanned:         {total_scanned:,}")
        logger(f"  Unique prefixes:     {len(prefix_summary)}")
        logger(f"  Total sampled bytes: {_fmt_bytes(sum(ps['total_size_bytes'] for ps in prefix_summary))}")
        logger(f"  Keys without TTL:    {sum(ps['no_ttl_count'] for ps in prefix_summary):,}")
        if maxmem:
            logger(f"  Memory utilization:  {used / maxmem * 100:.1f}%")

        # Save report
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "data_dump",
            f"redis_memory_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_path = os.path.normpath(report_path)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        self.report["_meta"] = {
            "scanned_keys": total_scanned,
            "prefixes_found": len(prefix_summary),
            "scan_duration_seconds": round(scan_elapsed, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(report_path, "w") as f:
            json.dump(self.report, f, indent=2, default=str)
        logger(f"\n  Report saved to: {report_path}")
        logger("=" * 72)

        await close_redis()


if __name__ == "__main__":
    asyncio.run(RedisAudit().run())
