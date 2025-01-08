import asyncio
import logging

from components.mysql_table_monitor import monitor_sql_table, DatabaseMonitor
from components.site_uptime_monitor import monitor_urls
from utils.config import Settings

logging.basicConfig(level=logging.INFO)


async def main():
    settings = Settings()

    try:
        await asyncio.gather(
            monitor_sql_table(settings),
            monitor_urls()
        )
    except Exception as e:
        logging.error(f"Monitoring failed: {e}")
    finally:
        await DatabaseMonitor.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user.")
