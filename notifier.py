import asyncio
import logging
from typing import Optional, Generator

import aiohttp

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

    def __init__(self, link: str, settings: Settings, *, auto_close: bool = False, stacktrace: str = ""):
        self.link = link
        self.settings = settings
        self.auto_close = auto_close
        self.stacktrace = stacktrace

    def __await__(self) -> Generator:
        """Make the class awaitable."""

        async def _notify():
            await self.send_notification()

        return _notify().__await__()

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

    async def send_slack_message(self, payload: dict):
        """
        Sends a message to Slack using the provided webhook URL.

        Params
        ------
        payload: dict
            The message payload to be sent to Slack.

        Raises
        ------
        aiohttp.ClientError
            If sending the message fails after the specified number of retries.
        """
        session = await self.get_session()
        retries = getattr(self.settings, 'REQUEST_RETRIES', 3)

        for retry in range(retries):
            try:
                async with session.post(self.settings.SLACK_WEBHOOK_URL, json=payload) as response:
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

    async def send_notification(self):
        """
        Sends a notification to Slack.
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Partner Monitor Alert*\n{self.link} has updates!"
                }
            }
        ]

        if self.stacktrace:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{self.stacktrace}```"
                }
            })

        payload = {
            "blocks": blocks,
            "text": f"Partner Monitor Alert - {self.link}"
        }

        await self.send_slack_message(payload)

        if self.auto_close:
            await self.close_session()


if __name__ == "__main__":
    settings = Settings()


    async def test():
        await SlackNotifier("Partners Table", settings, auto_close=True, stacktrace="Test message")


    asyncio.run(test())
