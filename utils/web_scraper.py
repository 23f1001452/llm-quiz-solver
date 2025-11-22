import httpx
import re
import base64
from bs4 import BeautifulSoup


class WebScraper:
    """
    Robust scraper used in the quiz solver:
    - Handles raw HTML and base64-encoded HTML.
    - Extracts visible text.
    - Detects quiz secret strings with several fallback patterns.
    """

    async def fetch(self, url: str) -> str:
        """Fetch raw bytes from a URL."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        return resp.content

    def _decode_content(self, raw: bytes) -> str:
        """
        Decode page content.
        If < is not present, it is likely base64-encoded HTML.
        """
        try:
            if b"<" not in raw:
                decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
                return decoded
            return raw.decode("utf-8", errors="ignore")
        except Exception:
            return raw.decode("utf-8", errors="ignore")

    def _extract_visible_text(self, html: str) -> str:
        """Extract clean visible text using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator=" ", strip=True)

    def _extract_secret(self, text: str) -> str:
        """
        Extract secret codes (uppercase/lowercase alphanumeric).
        Quiz secrets usually appear as 6–20 char tokens.
        """

        # 1) Direct alphanumeric code
        match = re.search(r"\b[A-Za-z0-9]{5,30}\b", text)
        if match:
            return match.group(0)

        # 2) Patterns like "SECRET: s3crEt9"
        match = re.search(
            r"[Ss]ecret[^A-Za-z0-9]*([A-Za-z0-9]{4,30})",
            text,
        )
        if match:
            return match.group(1)

        # 3) Patterns like "The code is xyz123"
        match = re.search(
            r"[Cc]ode[^A-Za-z0-9]*([A-Za-z0-9]{4,30})",
            text,
        )
        if match:
            return match.group(1)

        return "UNKNOWN"

    async def scrape_text(self, url: str) -> str:
        """
        High-level method:
        - Fetch URL
        - Decode (HTML or base64)
        - Extract text
        - Extract secret token
        """
        raw = await self.fetch(url)
        html = self._decode_content(raw)
        text = self._extract_visible_text(html)

        secret = self._extract_secret(text)
        return secret
