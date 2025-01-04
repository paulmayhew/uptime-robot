import asyncio
import logging
import os
import traceback
from pathlib import Path

import aiofiles
from aiohttp import ClientSession, ClientTimeout
from pydantic import HttpUrl, ValidationError
from watchfiles import awatch

from config import Settings
from notifier import Mailer, notify

logging.basicConfig(
    filename="uptime.log",
    encoding="utf-8",
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] %(message)s",
)
log = logging.getLogger(__name__)


async def send_request(
    url: HttpUrl,
    session: ClientSession,
    settings: Settings,
    retries: int,
) -> int:
    try:
        async with session.head(str(url), allow_redirects=True) as response:
            if response.status == 200:
                return retries

            log.info(f"Site '{response.url}' with response status '{response.status}'")
            await notify(HttpUrl(str(response.url)), settings)

    except Exception as e:
        log.error(f"Failed to monitor site '{url}': {e}")
        stacktrace = traceback.format_exc()
        await notify(url, settings, stacktrace=stacktrace)
        retries += 1

    return retries


async def monitor_links(url: HttpUrl, settings: Settings):
    retries = 0
    max_retries = settings.REQUEST_RETRIES
    timeout = ClientTimeout(total=settings.REQUEST_TIMEOUT)
    async with ClientSession(timeout=timeout) as session:
        while retries < max_retries:
            retries = await send_request(url, session, settings, retries)
            await asyncio.sleep(settings.MONITOR_INTERVAL)


async def spawn_site_monitors(
    file: Path,
    store: dict[str, asyncio.Task],
    settings: Settings,
):
    current_links = set(store.keys())

    async with aiofiles.open(file, "r") as f:
        async for line in f:
            line = line.strip()
            if not line or line in store:
                continue
            try:
                url = HttpUrl(line)
            except ValidationError:
                log.error(f"Invalid URL: {line}")
                continue
            task = asyncio.create_task(monitor_links(url, settings), name=line)
            store[line] = task
            current_links.discard(line)

    for link in current_links:
        task = store.pop(link)
        task.cancel()


async def monitor_file(file: Path):
    store: dict[str, asyncio.Task] = {}
    settings = Settings()

    if file.exists():
        await spawn_site_monitors(file, store, settings)
    else:
        os.makedirs(file.parent, exist_ok=True)
        file.touch()

    async for _ in awatch(file):
        await spawn_site_monitors(file, store, settings)

    for task in store.values():
        try:
            await task
        except asyncio.CancelledError:
            print(f"Task '{task.get_name()}' was cancelled")
            pass


if __name__ == "__main__":
    try:
        asyncio.run(monitor_file(Path("./monitor.txt")))
    except KeyboardInterrupt:
        ...
    except Exception as e:
        print(e)
    finally:
        asyncio.run(Mailer.close_client())
