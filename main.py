import asyncio
import logging
from typing import Optional

import aiohttp
from pydantic import HttpUrl

from config import Settings

log = logging.getLogger(__name__)


class SlackNotifier:
    """
    A class used to handle sending notifications to Slack using webhooks. This class provides
    methods to manage the HTTP session and send messages.

    Attributes
    ----------
    _session: Optional[aiohttp.ClientSession]
        A private class attribute to store the HTTP session instance.
    """

    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session is not None and not cls._session.closed:
            await cls._session.close()
            cls._session = None


async def send_slack_message(
        payload: dict,
        settings: Settings,
        auto_close_session: bool,
):
    """
    Sends a message to Slack using the provided webhook URL.

    Params
    ------
    payload: dict
        The message payload to be sent to Slack.
    settings: Settings
        The settings object containing Slack configuration.
    auto_close_session: bool
        Whether to automatically close the HTTP session after sending.

    Raises
    ------
    aiohttp.ClientError
        If sending the message fails after the specified number of retries.
    """
    session = await SlackNotifier.get_session()
    retries = settings.REQUEST_RETRIES

    for retry in range(retries):
        try:
            async with session.post(
                    settings.SLACK_WEBHOOK_URL,
                    json=payload,
                    timeout=settings.REQUEST_TIMEOUT
            ) as response:
                if response.status == 200:
                    break
                else:
                    log.error(f"Failed to send Slack message. Status: {response.status}")

            await asyncio.sleep(2 ** retry)
        except aiohttp.ClientError as e:
            log.error(f"Failed to send Slack message: {e}")
            await asyncio.sleep(2 ** retry)
    else:
        log.error(f"Failed to send Slack message after {retries} retries")

    if auto_close_session:
        await SlackNotifier.close_session()


async def notify(
        link: HttpUrl,
        settings: Settings,
        *,
        auto_close: bool = False,
        stacktrace: str = "",
):
    """
    Sends a notification to Slack when a site is down.

    Params
    ------
    link: HttpUrl
        The URL of the site that is down.
    settings: Settings
        The settings object containing configuration.
    auto_close: bool, default=False
        Whether to automatically close the session after sending.
    stacktrace: str, default=""
        The stack trace to include in the message, if any.
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Hey {settings.NAME}! :wave:\nThe site {str(link)} is unavailable, please investigate!"
            }
        }
    ]

    if stacktrace:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```{stacktrace}```"
            }
        })

    payload = {
        "blocks": blocks,
        "text": f"Site Down Alert - {str(link)}"
    }

    await send_slack_message(payload, settings, auto_close)


if __name__ == "__main__":
    settings = Settings()
    asyncio.run(notify(HttpUrl("https://example.com"), settings, auto_close=True))
