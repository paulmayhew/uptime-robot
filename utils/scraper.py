# utils/scraper.py

import logging
from typing import Optional

from bs4 import BeautifulSoup

logging.basicConfig(
    filename="uptime.log",
    encoding="utf-8",
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] %(message)s",
)
log = logging.getLogger(__name__)


async def extract_stacktrace(response_text: str) -> Optional[str]:
    """
    Extract stacktrace information from HTML response if available.
    Looks for stacktrace in blockquote elements or specific error sections.

    Args:
        response_text: HTML content from the response

    Returns:
        Extracted stacktrace or None if not found
    """
    try:
        soup = BeautifulSoup(response_text, 'html.parser')

        # Look for stacktrace in blockquote elements
        blockquotes = soup.find_all('blockquote')
        for blockquote in blockquotes:
            if 'cfthrow' in blockquote.text or 'error' in blockquote.text.lower():
                # Clean up the text (remove extra whitespace and normalize line endings)
                stacktrace = '\n'.join(line.strip() for line in blockquote.text.splitlines() if line.strip())
                return stacktrace

        # Alternatively look for common error containers
        error_containers = soup.find_all(['div', 'pre'], class_=['error', 'stacktrace', 'exception'])
        for container in error_containers:
            if container.text.strip():
                return container.text.strip()

        return None

    except Exception as e:
        log.error(f"Error parsing HTML for stacktrace: {e}")
        return None
