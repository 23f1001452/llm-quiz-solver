# ========================================================================
# utils/web_scraper.py - FIXED Web Scraping Utilities
# ========================================================================

import httpx
import base64
import logging
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Web scraping utilities used by QuizSolver
    """

    async def scrape_text(self, url: str) -> str:
        """
        Fetch page HTML (base64 or normal), extract visible text,
        then detect secret codes with robust regex.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)

        content = resp.content

        # ----- Base64 decode if needed -----
        try:
            if b"<" not in content:
                # Probably base64
                decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                html = decoded
            else:
                html = content.decode("utf-8", errors="ignore")
        except Exception:
            html = content.decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # ----- Detect secret codes -----
        # Accept uppercase, lowercase, and digits  (QUIZ SECRETS OFTEN LOOK LIKE "f2Ab9")
        match = re.search(r"\b[A-Za-z0-9]{4,30}\b", text)
        if match:
            return match.group(0)

        # Look for "Secret: CODE"
        match = re.search(r"[Ss]ecret[^A-Za-z0-9]*([A-Za-z0-9]{4,30})", text)
        if match:
            return match.group(1)

        return "UNKNOWN"

    async def scrape_table(self, url: str) -> List[Dict]:
        """
        Scrape tables from HTML
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table")

        result = []
        for table in tables:
            rows = []
            headers = [th.get_text(strip=True) for th in table.find_all("th")]

            for tr in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                if cells:
                    if headers:
                        rows.append(dict(zip(headers, cells)))
                    else:
                        rows.append(cells)

            result.append(rows)

        return result

    async def fetch_api(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Dict:
        """
        Standardized API request wrapper
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                resp = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                resp = await client.post(url, headers=headers, json=json)
            else:
                raise ValueError(f"Unsupported method: {method}")

            resp.raise_for_status()
            return resp.json()
