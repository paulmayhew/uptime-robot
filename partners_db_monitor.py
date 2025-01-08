import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from notifier import SlackNotifier
from config import Settings

log = logging.getLogger(__name__)


class DatabaseMonitor:
    """
    A class to monitor MySQL partners table for new rows.
    """
    _engine = None
    _async_session = None
    last_check_time: Optional[datetime] = None

    @classmethod
    async def get_session(cls, settings: Settings) -> AsyncSession:
        """Get or create a database session."""
        if cls._engine is None:
            cls._engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            cls._async_session = sessionmaker(
                cls._engine, class_=AsyncSession, expire_on_commit=False
            )

        async with cls._async_session() as session:
            return session

    @classmethod
    async def close(cls):
        """Close the database engine."""
        if cls._engine is not None:
            await cls._engine.dispose()
            cls._engine = None
            cls._async_session = None


async def check_for_new_partners(settings: Settings) -> bool:
    """
    Check if new partners have been added to the partners table since last check.

    Returns:
        bool: True if new partners were found, False otherwise
    """
    try:
        session = await DatabaseMonitor.get_session(settings)

        # Get current time in UTC
        current_time = datetime.now(timezone.utc)

        # Query to check for new partners
        query = text("""
            SELECT COUNT(*) as new_partners
            FROM partners
            WHERE ins_partners > :last_check
        """)

        # If this is our first check, use a reasonable default time
        last_check = DatabaseMonitor.last_check_time or (
            current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        )

        result = await session.execute(query, {"last_check": last_check})
        row = result.one()
        new_partner_count = row[0]

        if new_partner_count > 0:
            # Get details of new partners for the notification
            details_query = text("""
                SELECT id_partners, label, key, full_name, ins_partners, domain 
                FROM partners 
                WHERE ins_partners > :last_check
                ORDER BY ins_partners DESC
            """)
            details_result = await session.execute(details_query, {"last_check": last_check})
            new_partners = details_result.fetchall()

            # Update last check time
            DatabaseMonitor.last_check_time = current_time

            # Format partner details for notification
            partner_details = "\n".join(
                f"• Partner {p.label} ({p.key})\n  - Full Name: {p.full_name}\n  "
                f"- Domain: {p.domain}\n  - Added: {p.ins_partners}"
                for p in new_partners
            )

            log.info(f"Found {new_partner_count} new partners")
            await SlackNotifier(
                link="Partners Table",
                settings=settings,
                stacktrace=f"New partners added:\n{partner_details}",
                auto_close=True
            )
            return True

        # Update last check time even if no new partners
        DatabaseMonitor.last_check_time = current_time
        return False

    except Exception as e:
        error_message = f"Error checking for new partners: {str(e)}"
        log.error(error_message)
        await SlackNotifier(
            link="Partners Table",
            settings=settings,
            stacktrace=error_message,
            auto_close=True
        )
        return False


async def monitor_partners(settings: Settings):
    """
    Continuously monitor the partners table for new entries.
    """
    log.info("Starting partners table monitor")
    while True:
        try:
            await check_for_new_partners(settings)
            await asyncio.sleep(settings.MONITOR_INTERVAL)

        except Exception as e:
            log.error(f"Error in monitor loop: {str(e)}")
            await asyncio.sleep(settings.MONITOR_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settings = Settings()

    try:
        asyncio.run(monitor_partners(settings))
    finally:
        asyncio.run(DatabaseMonitor.close())
