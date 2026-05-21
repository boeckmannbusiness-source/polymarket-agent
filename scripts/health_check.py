"""Quick health check for all system components."""
import asyncio
import httpx

from app.config import settings
from app.core.logging import setup_logging, logger


async def check_endpoint(client: httpx.AsyncClient, name: str, url: str) -> bool:
    try:
        r = await client.get(url, timeout=5.0)
        if r.status_code == 200:
            logger.info("health_ok", component=name)
            return True
        logger.warning("health_fail", component=name, status=r.status_code)
    except Exception as e:
        logger.error("health_error", component=name, error=str(e))
    return False


async def main():
    setup_logging()
    logger.info("running_health_check")

    async with httpx.AsyncClient() as client:
        checks = [
            ("FastAPI", f"http://localhost:{settings.APP_PORT}/health"),
            ("Ping", f"http://localhost:{settings.APP_PORT}/api/v1/ping"),
        ]

        results = await asyncio.gather(*[check_endpoint(client, n, u) for n, u in checks])

        healthy = sum(results)
        total = len(results)
        logger.info("health_summary", healthy=healthy, total=total)

        if healthy == total:
            logger.info("all_systems_operational")
        else:
            logger.warning("some_checks_failed", healthy=healthy, total=total)


if __name__ == "__main__":
    asyncio.run(main())
