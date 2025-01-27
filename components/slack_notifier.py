import asyncio
import logging
from typing import Optional, Generator, List

import aiohttp

from utils.config import Settings

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

    def __init__(self, link: str, is_table: bool, settings: Settings, *, auto_close: bool = False,
                 stacktrace: str = "", users_to_notify: List[str] = None, is_restored: bool = False):
        self.link = link
        self.is_table: bool = is_table
        self.settings = settings
        self.auto_close = auto_close
        self.stacktrace = stacktrace
        self.users_to_notify = ["U054ETQ0E", "USERA6XFF"]
        self.is_restored = is_restored

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

    def _format_user_mentions(self) -> str:
        """Format user IDs into Slack mentions."""
        if not self.users_to_notify:
            return ""
        mentions = " ".join(f"<@{user_id}>" for user_id in self.users_to_notify)
        return f"{mentions} "

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
        if session.closed:
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

    async def send_table_update_notification(self):
        user_mentions = self._format_user_mentions()
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{user_mentions}*{self.settings.MYSQL_TABLE_NAME} "
                            f"Update Alert*\n{self.link} has new entries!"
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
            "text": f"{user_mentions}{self.settings.MYSQL_TABLE_NAME} Update Alert"
        }

        await self.send_slack_message(payload)

    async def send_site_down_notification(self):
        user_mentions = self._format_user_mentions()

        if self.is_restored:
            message = f"{user_mentions}*Site Restored Alert*\nSite is back online: {self.link} 🎉"
            title = f"Site Restored Alert - {self.link}"
        else:
            message = f"{user_mentions}*Site Monitoring Alert*\nSite is down: {self.link} ❌"
            title = f"Site Down Alert - {self.link}"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
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
            "text": title
        }

        await self.send_slack_message(payload)

    async def send_notification(self):
        if self.is_table:
            await self.send_table_update_notification()
        else:
            await self.send_site_down_notification()

        if self.auto_close:
            await self.close_session()
