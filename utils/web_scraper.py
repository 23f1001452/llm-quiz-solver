# ============================================================================
# utils/web_scraper.py - Web Scraping Utilities
# ============================================================================

import httpx
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Web scraping utilities
    """
    
    import re
from bs4 import BeautifulSoup
import base64

class WebScraper:
    async def scrape_text(self, url: str) -> str:
        """
        Fetches the page, decodes base64 if needed,
        and extracts the secret code using robust regex.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        content = resp.content

        # Detect and decode base64
        try:
            if b"<" not in content:
                # probably base64
                decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                html = decoded
            else:
                html = content.decode("utf-8", errors="ignore")
        except Exception:
            html = content.decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # Robust secret extraction:
        # Look for any uppercase alphanumeric code 5–20 chars
        match = re.search(r"\b[A-Z0-9]{5,20}\b", text)
        if match:
            return match.group(0)

        # If page uses "Secret:" pattern
        match = re.search(r"[Ss]ecret[^A-Za-z0-9]*([A-Za-z0-9]{4,30})", text)
        if match:
            return match.group(1)

        return "UNKNOWN"
    
    async def scrape_table(self, url: str) -> List[Dict]:
        """
        Scrape tables from URL
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')
            
            result = []
            for table in tables:
                rows = []
                headers = [th.get_text(strip=True) for th in table.find_all('th')]
                
                for tr in table.find_all('tr')[1:]:  # Skip header row
                    cells = [td.get_text(strip=True) for td in tr.find_all('td')]
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
        json: Optional[Dict] = None
    ) -> Dict:
        """
        Fetch data from API
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=json)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()