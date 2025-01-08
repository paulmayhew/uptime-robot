# mysql_table_monitor.py

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from components.site_uptime_monitor import MongoDBUrlManager
from components.slack_notifier import SlackNotifier
from utils.config import Settings

log = logging.getLogger(__name__)


class DatabaseMonitor:
    _engine = None
    _async_session = None
    last_check_time: Optional[datetime] = None

    @classmethod
    async def get_session(cls, settings: Settings) -> AsyncSession:
        if not cls._engine:
            cls._engine = create_async_engine(
                settings.MYSQL_HOST,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            cls._async_session = sessionmaker(
                cls._engine, class_=AsyncSession, expire_on_commit=False
            )
        return cls._async_session()

    @classmethod
    async def close(cls):
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._async_session = None


async def check_for_new_rows(settings: Settings, url_manager: MongoDBUrlManager) -> bool:
    try:
        # Retrieve or create last check time from MongoDB
        last_check_doc = await url_manager.timestamp_collection.find_one({
            'table_name': settings.MYSQL_TABLE_NAME
        })

        current_time = datetime.now(timezone.utc)
        last_check = (last_check_doc['last_check_time'] if last_check_doc
                      else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))

        last_check_formatted = last_check.strftime('%Y-%m-%d %H:%M:%S')

        async with await DatabaseMonitor.get_session(settings) as session:
            columns = settings.MYSQL_TABLE_COLUMNS

            row_count_query = text(settings.MYSQL_SELECT_QUERY)
            new_row_count = (await session.execute(row_count_query,
                                                   {"last_check": last_check_formatted})).scalar_one()

            if new_row_count > 0:
                details_query = text(settings.MYSQL_DETAILS_QUERY)
                new_rows = (await session.execute(details_query,
                                                  {"last_check": last_check_formatted})).fetchall()

                # Update last check time in MongoDB
                await url_manager.timestamp_collection.update_one(
                    {'table_name': settings.MYSQL_TABLE_NAME},
                    {'$set': {'last_check_time': current_time}},
                    upsert=True
                )

                row_details = "\n".join(
                    f"• {column.replace('_', ' ').title()}: {getattr(r, column, 'N/A')}"
                    for r in new_rows
                    for column in columns.split(',')
                )

                log.info(f"[{settings.MYSQL_TABLE_NAME}] Found {new_row_count} new rows")
                await SlackNotifier(
                    link=settings.MYSQL_TABLE_NAME,
                    settings=settings,
                    stacktrace=f"New rows added:\n{row_details}",
                    auto_close=True
                )
                return True

            # Update last check time even if no new rows
            await url_manager.timestamp_collection.update_one(
                {'table_name': settings.MYSQL_TABLE_NAME},
                {'$set': {'last_check_time': current_time}},
                upsert=True
            )
            return False

    except Exception as e:
        error_message = f"Error checking for new rows: {str(e)}"
        log.error(error_message)
        await SlackNotifier(
            link=settings.MYSQL_TABLE_NAME,
            settings=settings,
            stacktrace=error_message,
            auto_close=True
        )
        return False


async def monitor_sql_table(settings: Settings):
    log.info(f"Starting {settings.MYSQL_TABLE_NAME} monitor")
    url_manager = MongoDBUrlManager(settings)
    while True:
        try:
            await check_for_new_rows(settings, url_manager)
        except Exception as e:
            log.error(f"Error in monitor loop: {str(e)}")

        await asyncio.sleep(settings.MONITOR_INTERVAL)


async def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings()

    try:
        await monitor_sql_table(settings)
    except Exception as e:
        log.exception(f"Monitoring failed {e}")
    finally:
        await DatabaseMonitor.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Monitoring stopped by user.")
