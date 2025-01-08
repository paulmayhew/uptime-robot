# components/site_uptime_monitor.py

import asyncio
import logging
import traceback

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

    async def get_urls(self):
        urls = await self.url_collection.find().to_list(length=None)
        return [self._validate_url(url['url']) for url in urls]

    @staticmethod
    def _validate_url(url: str) -> HttpUrl:
        # Prepend http:// if no scheme is present
        if not url.startswith(('http://', 'https://')):
            url = f'http://{url}'
        return HttpUrl(url)


async def send_request(
        url: HttpUrl,
        session: ClientSession,
        settings: Settings,
        retries: int,
) -> int:
    """
    Send a HEAD request to the given URL and notify if the response status is not 200.
    If the request fails, notify the user and retry. Return the number of retries.

    Params
    ------
    url: :class:`pydantic.HttpUrl`
        The URL to monitor
    session: :class:`aiohttp.ClientSession`
        The aiohttp ClientSession object
    settings: :class:`config.Settings`
        The settings object
    retries: :class:`int`
        The number of retries

    Returns
    -------
    The number of retries
    """

    try:
        async with session.head(str(url), allow_redirects=True) as response:
            if response.status == 200:
                return retries

            log.info(f"Site '{response.url}' with response status '{response.status}'")
            await SlackNotifier(HttpUrl(str(response.url)), settings)

    except Exception as monitor_error:
        log.error(f"Failed to monitor site '{url}': {monitor_error}")
        stacktrace = traceback.format_exc()
        await SlackNotifier(url, settings, stacktrace=stacktrace)
        retries += 1

    return retries


async def monitor_links(url: HttpUrl, settings: Settings):
    """
    Monitors the specified URL by sending periodic HTTP requests.

    Params
    ------
    url: :class:`pydantic.HttpUrl`
        The URL to be monitored
    settings: :class:`config.Settings`
        Configuration settings for the monitoring process, including request retries,
        timeout, and monitor interval

    Returns
    -------
    None
    """

    retries = 0
    max_retries = settings.REQUEST_RETRIES
    timeout = ClientTimeout(total=settings.REQUEST_TIMEOUT)
    async with ClientSession(timeout=timeout) as session:
        while retries < max_retries:
            retries = await send_request(url, session, settings, retries)
            await asyncio.sleep(settings.MONITOR_INTERVAL)


async def spawn_site_monitors(
        url_manager: MongoDBUrlManager,
        store: dict[str, asyncio.Task],
        settings: Settings,
):
    urls = await url_manager.get_urls()
    current_links = set(store.keys())

    for url in urls:
        url_str = str(url)
        if url_str not in store:
            task = asyncio.create_task(monitor_links(url, settings), name=url_str)
            store[url_str] = task
            current_links.discard(url_str)

    for link in current_links:
        task = store.pop(link)
        task.cancel()


async def monitor_urls():
    settings = Settings()
    url_manager = MongoDBUrlManager(settings)
    store: dict[str, asyncio.Task] = {}

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
