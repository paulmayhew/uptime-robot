# components/site_uptime_monitor.py

import asyncio
import logging
import traceback
from typing import Dict, Tuple

import motor.motor_asyncio
from aiohttp import ClientSession, ClientTimeout
from pydantic import HttpUrl

from components.slack_notifier import SlackNotifier
from utils.config import Settings

logging.basicConfig(
    filename="uptime.log",
    encoding="utf-8",
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] %(message)s",
)
log = logging.getLogger(__name__)


class MongoDBUrlManager:
    def __init__(self, settings: Settings):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
        self.db = self.client[settings.MONGODB_DB]
        self.url_collection = self.db['monitored_urls']
        self.timestamp_collection = self.db['monitored_tables']
        self.site_status_collection = self.db['site_status']

    async def get_urls(self):
        urls = await self.url_collection.find().to_list(length=None)
        return [self._validate_url(url['url']) for url in urls]

    async def get_site_status(self, url: str) -> bool:
        """Get the current status of a site (True if up, False if down)"""
        status = await self.site_status_collection.find_one({'url': url})
        return status['is_up'] if status else True

    async def update_site_status(self, url: str, is_up: bool):
        """Update the status of a site"""
        await self.site_status_collection.update_one(
            {'url': url},
            {'$set': {'url': url, 'is_up': is_up}},
            upsert=True
        )

    @staticmethod
    def _validate_url(url: str) -> HttpUrl:
        if not url.startswith(('http://', 'https://')):
            url = f'http://{url}'
        return HttpUrl(url)


async def send_request(
        url: HttpUrl,
        session: ClientSession,
        settings: Settings,
        url_manager: MongoDBUrlManager,
        retries: int,
) -> Tuple[int, bool]:
    """
    Send a HEAD request to the given URL and notify only when status changes.
    Returns the number of retries and whether the site is up.

    Params
    ------
    url: :class:`pydantic.HttpUrl`
        The URL to monitor
    session: :class:`aiohttp.ClientSession`
        The aiohttp ClientSession object
    settings: :class:`config.Settings`
        The settings object
    url_manager: :class:`MongoDBUrlManager`
        The URL manager instance for tracking site status
    retries: :class:`int`
        The number of retries

    Returns
    -------
    Tuple[int, bool]: The number of retries and whether the site is up
    """
    url_str = str(url)
    was_up = await url_manager.get_site_status(url_str)
    is_up = False

    try:
        async with session.head(str(url), allow_redirects=True) as response:
            if response.status == 200:
                is_up = True
                if not was_up:  # Only notify if site was previously down
                    log.info(f"Site '{response.url}' has been restored")
                    await SlackNotifier(
                        HttpUrl(str(response.url)),
                        is_table=False,
                        settings=settings,
                        is_restored=True
                    )
                    await url_manager.update_site_status(url_str, True)
                return retries, True

            # Site is down
            log.info(f"Site '{response.url}' with response status '{response.status}'")
            if was_up:  # Only notify if site just went down
                await SlackNotifier(
                    HttpUrl(str(response.url)),
                    is_table=False,
                    settings=settings,
                    is_restored=False
                )
                await url_manager.update_site_status(url_str, False)

    except Exception as monitor_error:
        log.error(f"Failed to monitor site '{url}': {monitor_error}")
        if was_up:  # Only notify if site just went down
            stacktrace = traceback.format_exc()
            await SlackNotifier(
                url,
                is_table=False,
                settings=settings,
                stacktrace=stacktrace,
                is_restored=False
            )
            await url_manager.update_site_status(url_str, False)
        retries += 1

    return retries, is_up


async def monitor_links(url: HttpUrl, settings: Settings, url_manager: MongoDBUrlManager):
    """
    Monitors the specified URL by sending periodic HTTP requests.
    Uses different intervals based on site status.

    Params
    ------
    url: :class:`pydantic.HttpUrl`
        The URL to be monitored
    settings: :class:`config.Settings`
        Configuration settings for the monitoring process
    url_manager: :class:`MongoDBUrlManager`
        The URL manager instance for tracking site status
    """
    retries = 0
    max_retries = settings.REQUEST_RETRIES
    timeout = ClientTimeout(total=settings.REQUEST_TIMEOUT)

    async with ClientSession(timeout=timeout) as session:
        while retries < max_retries:
            retries, is_up = await send_request(url, session, settings, url_manager, retries)

            # Use shorter interval if site is down
            interval = (
                settings.MONITOR_INTERVAL if is_up
                else settings.DOWN_MONITOR_INTERVAL
            )

            if not is_up:
                log.info(
                    f"Site {url} is down, checking again in "
                    f"{settings.DOWN_MONITOR_INTERVAL} seconds"
                )

            await asyncio.sleep(interval)


async def spawn_site_monitors(
        url_manager: MongoDBUrlManager,
        store: Dict[str, asyncio.Task],
        settings: Settings,
):
    urls = await url_manager.get_urls()
    current_links = set(store.keys())

    for url in urls:
        url_str = str(url)
        if url_str not in store:
            task = asyncio.create_task(
                monitor_links(url, settings, url_manager),
                name=url_str
            )
            store[url_str] = task
            current_links.discard(url_str)

    for link in current_links:
        task = store.pop(link)
        task.cancel()


async def monitor_urls():
    settings = Settings()
    url_manager = MongoDBUrlManager(settings)
    store: Dict[str, asyncio.Task] = {}

    await spawn_site_monitors(url_manager, store, settings)

    while True:
        await asyncio.sleep(settings.MONITOR_INTERVAL)
        await spawn_site_monitors(url_manager, store, settings)


if __name__ == "__main__":
    try:
        asyncio.run(monitor_urls())
    except KeyboardInterrupt:
        log.info("Monitoring stopped by user.")
    except Exception as e:
        log.error(f"Monitoring failed: {e}")
